import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getPmdfEntity, listPmdfEntities } from "../api/client";
import { PMDF_KINDS, type PmdfKind } from "../api/pmdfTypes";
import { EntityView } from "../components/entity-views/EntityView";
import { VersionDiff } from "../components/VersionDiff";
import styles from "./DocumentViewer.module.css";

const KIND_LABELS: Record<PmdfKind, string> = {
  product: "プロダクト",
  stakeholder: "ステークホルダー",
  persona: "ペルソナ",
  objective: "目標(OKR)",
  metric: "メトリクス",
  roadmap_item: "ロードマップ項目",
  story: "ストーリー",
  experiment: "実験",
  decision: "Decision Record",
  release: "リリース",
  risk: "リスク",
  initiative: "施策",
  report: "レポート",
  approval: "承認記録",
};

/** エンティティの一覧表示用タイトルを、kindに応じた代表フィールドから抽出する。 */
function displayTitle(entity: Record<string, unknown>): string {
  const candidates = [
    "title",
    "name",
    "theme",
    "objective",
    "event",
    "charter",
    "background",
    "target",
  ];
  for (const key of candidates) {
    const value = entity[key];
    if (typeof value === "string" && value.length > 0) {
      return value;
    }
  }
  return String(entity.id);
}

/** ドキュメントビューア画面(FR-UI-03)。PMDF全14種のkind別レンダリング+版間diff。 */
export function DocumentViewer() {
  const params = useParams<{ kind?: string; id?: string }>();
  const navigate = useNavigate();
  const selectedKind = (params.kind as PmdfKind | undefined) ?? null;
  const selectedId = params.id ?? null;

  const listQuery = useQuery({
    queryKey: ["pmdf", selectedKind, "list"],
    queryFn: () =>
      listPmdfEntities<Record<string, unknown>>(selectedKind as string),
    enabled: selectedKind !== null && selectedId === null,
  });

  const entityQuery = useQuery({
    queryKey: ["pmdf", selectedKind, selectedId],
    queryFn: () =>
      getPmdfEntity<Record<string, unknown>>(
        selectedKind as string,
        selectedId as string,
      ),
    enabled: selectedKind !== null && selectedId !== null,
  });

  return (
    <div className={styles.container}>
      <h1>ドキュメントビューア</h1>

      <label className={styles.kindSelectLabel}>
        種別
        <select
          value={selectedKind ?? ""}
          onChange={(event) => navigate(`/documents/${event.target.value}`)}
        >
          <option value="" disabled>
            選択してください
          </option>
          {PMDF_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {KIND_LABELS[kind]}
            </option>
          ))}
        </select>
      </label>

      {selectedKind && selectedId === null && (
        <ul className={styles.list}>
          {(listQuery.data ?? []).map((entity) => (
            <li key={String(entity.id)}>
              <button
                type="button"
                className={styles.listItemButton}
                onClick={() =>
                  navigate(`/documents/${selectedKind}/${String(entity.id)}`)
                }
              >
                {displayTitle(entity)}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedKind && selectedId !== null && (
        <div className={styles.detail}>
          {entityQuery.isLoading && <p>読み込み中...</p>}
          {entityQuery.isError && (
            <p className={styles.error} data-testid="document-viewer-error">
              指定されたエンティティが見つかりませんでした(
              {selectedKind}:{selectedId})。
            </p>
          )}
          {entityQuery.data && (
            <>
              <EntityView entity={entityQuery.data} />
              <div className={styles.versionSection}>
                <h2>版間diff</h2>
                <VersionDiff kind={selectedKind} entityId={selectedId} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
