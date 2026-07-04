"""`pmdf` コマンドラインインターフェース(typer)。

`validate` / `export` / `import` / `convert` / `migrate` サブコマンドで
E2-1〜E2-8の機能を公開する(FR-DF-03)。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import jsonschema
import typer

from pmdf.bundle.export import ExportScope, export_bundle
from pmdf.bundle.import_ import Resolution, apply_bundle, diff_preview, validate_bundle
from pmdf.convert.csv_ import roadmap_item_to_csv, story_to_csv
from pmdf.convert.markdown import decision_to_markdown, report_to_markdown
from pmdf.io import dict_to_yaml, load_entity, save_entity, yaml_to_dict
from pmdf.migrate import MigrationNotFoundError, migrate_entity
from pmdf.models import Decision, Report, RoadmapItem, Story
from pmdf.models.common import PmdfBase
from pmdf.sanitize import load_sanitize_profile
from pmdf.schema_registry import SchemaNotFoundError, validate_entity

app = typer.Typer(help="PMDF (Product Management Data Format) CLI")


class DirectoryStore:
    """`base_dir`配下に1エンティティ1ファイル規約で書き込むシンプルなストア実装。

    `pmdf import`コマンド用の具象実装。E3のpmdf-store層は別途、より高機能な
    (Git永続化等の)実装で`PmdfStore`プロトコルを満たす想定。
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(self, entity: PmdfBase) -> None:
        save_entity(entity, self.base_dir)


def _iter_yaml_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.yaml"))


def _load_entities_from_dir(path: Path) -> list[PmdfBase]:
    return [load_entity(p) for p in _iter_yaml_files(path)]


@app.command()
def validate(path: Path) -> None:
    """ファイルまたはディレクトリ配下のPMDFエンティティをスキーマ検証する。"""
    if not path.exists():
        typer.echo(f"パスが存在しません: {path}", err=True)
        raise typer.Exit(code=1)

    files = _iter_yaml_files(path)
    has_error = False
    for file_path in files:
        try:
            data = yaml_to_dict(file_path.read_text(encoding="utf-8"))
            kind = data.get("kind") if isinstance(data, dict) else None
            validate_entity(data, kind=kind)
        except (jsonschema.exceptions.ValidationError, SchemaNotFoundError) as exc:
            has_error = True
            typer.echo(f"NG: {file_path}: {exc}", err=True)
            continue
        typer.echo(f"OK: {file_path}")

    if has_error:
        raise typer.Exit(code=1)


@app.command()
def export(
    input_dir: Path = typer.Argument(..., help="エンティティ格納ディレクトリ"),
    output: Path = typer.Option(..., "--output", help="出力先の*.pmdf.tar.gzパス"),
    product: list[str] = typer.Option([], "--product", help="対象プロダクトid(複数指定可)"),
    kind: list[str] = typer.Option([], "--kind", help="対象エンティティ種別(複数指定可)"),
    since: str | None = typer.Option(None, "--since", help="この日時以降(ISO8601)"),
    sanitize: Path | None = typer.Option(None, "--sanitize", help="サニタイズプロファイルYAML"),
) -> None:
    """エンティティ群をバンドル(`*.pmdf.tar.gz`)としてエクスポートする。"""
    entities = _load_entities_from_dir(input_dir)
    scope = ExportScope(
        product_ids=list(product) or None,
        kinds=list(kind) or None,
        since=datetime.fromisoformat(since) if since else None,
    )
    profile = load_sanitize_profile(sanitize) if sanitize is not None else None
    export_bundle(
        entities,
        scope,
        output,
        generated_env="cli",
        sanitize_profile=profile,
    )
    typer.echo(f"exported: {output}")


@app.command(name="import")
def import_bundle(
    bundle: Path = typer.Argument(..., help="インポート対象の*.pmdf.tar.gz"),
    store: Path = typer.Option(..., "--store", help="適用先ディレクトリ"),
    dry_run: bool = typer.Option(False, "--dry-run", help="適用せずプレビューのみ行う"),
    resolve: list[str] = typer.Option([], "--resolve", help="競合解決(形式: id=incoming|existing)"),
) -> None:
    """バンドルを検証し、差分プレビューの上でストアへ適用する。"""
    validation = validate_bundle(bundle)
    if not validation.is_valid:
        for error in validation.errors:
            typer.echo(f"NG: {error.relpath}: {error.message}", err=True)
        raise typer.Exit(code=1)

    existing_entities = _load_entities_from_dir(store) if store.exists() else []
    diffs = diff_preview(bundle, existing_entities)
    for diff in diffs:
        typer.echo(f"{diff.diff_type}: {diff.kind}/{diff.id}")
        for ref_error in diff.reference_errors:
            typer.echo(f"  参照エラー: {ref_error}", err=True)

    resolutions: dict[str, Resolution] = {}
    for item in resolve:
        entity_id, _, resolution = item.partition("=")
        if resolution not in ("incoming", "existing"):
            typer.echo(f"不正な--resolve指定です: {item!r}", err=True)
            raise typer.Exit(code=1)
        resolutions[entity_id] = resolution  # type: ignore[assignment]

    result = apply_bundle(bundle, resolutions, DirectoryStore(store), dry_run=dry_run)
    typer.echo(
        f"適用結果: applied={len(result.applied_ids)} skipped={len(result.skipped_ids)} "
        f"dry_run={result.dry_run}"
    )


@app.command()
def convert(
    input_path: Path = typer.Argument(..., help="変換元(ファイルまたはディレクトリ)"),
    output: Path = typer.Argument(..., help="変換結果の出力先"),
    to: str = typer.Option(..., "--to", help="csv または markdown"),
    kind: str = typer.Option(..., "--kind", help="対象kind"),
) -> None:
    """PMDFエンティティをCSV/Markdownへ変換する(FR-EX-06)。"""
    entities = _load_entities_from_dir(input_path)

    if to == "csv":
        if kind == "story":
            text = story_to_csv([e for e in entities if isinstance(e, Story)])
        elif kind == "roadmap_item":
            text = roadmap_item_to_csv([e for e in entities if isinstance(e, RoadmapItem)])
        else:
            typer.echo(f"csv変換は未対応のkindです: {kind}", err=True)
            raise typer.Exit(code=1)
    elif to == "markdown":
        if kind == "decision":
            parts = [decision_to_markdown(e) for e in entities if isinstance(e, Decision)]
        elif kind == "report":
            parts = [report_to_markdown(e) for e in entities if isinstance(e, Report)]
        else:
            typer.echo(f"markdown変換は未対応のkindです: {kind}", err=True)
            raise typer.Exit(code=1)
        text = "\n\n---\n\n".join(parts)
    else:
        typer.echo(f"--toは csv または markdown を指定してください: {to!r}", err=True)
        raise typer.Exit(code=1)

    output.write_text(text, encoding="utf-8")
    typer.echo(f"converted: {output}")


@app.command()
def migrate(
    path: Path = typer.Argument(..., help="マイグレーション対象のYAMLファイル"),
    from_version: str = typer.Option(..., "--from", help="現在のpmdf_version"),
    to_version: str = typer.Option(..., "--to", help="目標のpmdf_version"),
) -> None:
    """PMDFスキーマバージョンのマイグレーションを実行する(NFR-09)。"""
    data = yaml_to_dict(path.read_text(encoding="utf-8"))
    current_version = data.get("pmdf_version")
    if current_version != from_version:
        typer.echo(
            f"指定された--from({from_version})と実際のpmdf_version({current_version})が"
            "一致しません",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        migrated = migrate_entity(data, to_version)
    except MigrationNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    path.write_text(dict_to_yaml(migrated), encoding="utf-8")
    typer.echo(f"migrated: {path} ({from_version} -> {to_version})")


if __name__ == "__main__":
    app()
