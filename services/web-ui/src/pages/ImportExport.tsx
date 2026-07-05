import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  applyImportBundle,
  exportBundle,
  validateImportBundle,
  type BundleDiffEntry,
  type ImportResolution,
} from "../api/client";
import { ConflictResolver } from "../components/ConflictResolver";
import { YamlJsonEditor } from "../components/YamlJsonEditor";
import styles from "./ImportExport.module.css";

function parseCommaSeparated(value: string): string[] | undefined {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return items.length > 0 ? items : undefined;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Import/Export画面(FR-UI-06, FR-EX-05)。
 *
 * Export: プロダクト/種別のスコープを指定してバンドル(`*.pmdf.tar.gz`)を
 * ダウンロードする。
 * Import: バンドルをアップロードして差分プレビューを表示し、`conflict`
 * (同一idで値が異なる)エンティティは「取込側/既存側」の2者択一
 * (+手動編集導線)で解決してから適用する。
 */
export function ImportExport() {
  // --- Export ---
  const [productIdsInput, setProductIdsInput] = useState("");
  const [kindsInput, setKindsInput] = useState("");

  const exportMutation = useMutation({
    mutationFn: () =>
      exportBundle({
        product_ids: parseCommaSeparated(productIdsInput) ?? null,
        kinds: parseCommaSeparated(kindsInput) ?? null,
      }),
    onSuccess: (blob) => downloadBlob(blob, "bundle.pmdf.tar.gz"),
  });

  // --- Import ---
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [diffs, setDiffs] = useState<BundleDiffEntry[] | null>(null);
  const [resolutions, setResolutions] = useState<
    Record<string, ImportResolution>
  >({});
  const [manualEditTarget, setManualEditTarget] =
    useState<BundleDiffEntry | null>(null);
  const [manualEditDraft, setManualEditDraft] = useState<Record<
    string,
    unknown
  > | null>(null);

  const validateMutation = useMutation({
    mutationFn: (file: File) => validateImportBundle(file),
    onSuccess: (result) => {
      setDiffs(result.diffs);
      setResolutions({});
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => {
      if (selectedFile === null) {
        return Promise.reject(new Error("ファイルが選択されていません"));
      }
      return applyImportBundle(selectedFile, resolutions);
    },
  });

  const conflicts = (diffs ?? []).filter((d) => d.diff_type === "conflict");
  const unresolvedConflicts = conflicts.filter(
    (c) => resolutions[c.id] === undefined,
  );
  const canApply =
    diffs !== null &&
    unresolvedConflicts.length === 0 &&
    !applyMutation.isPending;

  function handleResolve(id: string, resolution: ImportResolution) {
    setResolutions((prev) => ({ ...prev, [id]: resolution }));
  }

  function handleManualEdit(conflict: BundleDiffEntry) {
    setManualEditTarget(conflict);
    setManualEditDraft(
      Object.fromEntries(
        Object.entries(conflict.field_diffs).map(([field, diff]) => [
          field,
          diff.incoming,
        ]),
      ),
    );
  }

  return (
    <div className={styles.container}>
      <h1>Import / Export</h1>

      <section className={styles.section}>
        <h2>Export</h2>
        <div className={styles.field}>
          <label htmlFor="export-product-ids">プロダクトID(カンマ区切り)</label>
          <input
            id="export-product-ids"
            value={productIdsInput}
            onChange={(event) => setProductIdsInput(event.target.value)}
            placeholder="未指定の場合は全プロダクト"
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="export-kinds">種別(カンマ区切り)</label>
          <input
            id="export-kinds"
            value={kindsInput}
            onChange={(event) => setKindsInput(event.target.value)}
            placeholder="未指定の場合は全種別"
          />
        </div>
        <button
          type="button"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
        >
          エクスポート
        </button>
        {exportMutation.isError && (
          <p className={styles.error} data-testid="export-error">
            エクスポートに失敗しました。
          </p>
        )}
        {exportMutation.isSuccess && (
          <p className={styles.success}>ダウンロードしました。</p>
        )}
      </section>

      <section className={styles.section}>
        <h2>Import</h2>
        <div className={styles.field}>
          <label htmlFor="import-file">バンドルファイル</label>
          <input
            id="import-file"
            type="file"
            accept=".tar.gz"
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null;
              setSelectedFile(file);
              setDiffs(null);
            }}
          />
        </div>
        <button
          type="button"
          onClick={() => selectedFile && validateMutation.mutate(selectedFile)}
          disabled={selectedFile === null || validateMutation.isPending}
        >
          プレビュー
        </button>
        {validateMutation.isError && (
          <p className={styles.error} data-testid="import-validate-error">
            バンドルの検証に失敗しました。
          </p>
        )}

        {diffs !== null && (
          <div>
            <h3>差分プレビュー</h3>
            <ul className={styles.diffList}>
              {diffs.map((diff) => (
                <li key={diff.id} className={styles.diffItem}>
                  {diff.kind}/{diff.id}: {diff.diff_type}
                </li>
              ))}
            </ul>

            {conflicts.length > 0 && (
              <ConflictResolver
                conflicts={conflicts}
                resolutions={resolutions}
                onResolve={handleResolve}
                onManualEdit={handleManualEdit}
              />
            )}

            {manualEditTarget !== null && manualEditDraft !== null && (
              <div>
                <h4>
                  手動編集: {manualEditTarget.kind}/{manualEditTarget.id}
                </h4>
                {/*
                 * 注記: 現状のバンドル適用API(`POST /bundles/import/apply`)は
                 * `resolutions`としてid→"incoming"|"existing"の2者択一のみを
                 * 受け付け、任意の編集後コンテンツを直接適用する経路を提供
                 * していない(`pmdf.bundle.import_.apply_bundle`のシグネチャ
                 * 制約)。そのため、ここでの手動編集は取込内容の確認・
                 * 事前レビュー用途とし、「反映」操作は取込側採用
                 * (resolution="incoming")として扱う。編集した値そのものを
                 * 適用したい場合は、適用後にE7-7のEntityEditor(通常のPUT
                 * /pmdf/{kind}/{id})で追って修正する運用とする。
                 */}
                <YamlJsonEditor
                  value={manualEditDraft}
                  onChange={(parsed) => {
                    if (parsed !== null) {
                      setManualEditDraft(parsed);
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={() => {
                    handleResolve(manualEditTarget.id, "incoming");
                    setManualEditTarget(null);
                  }}
                >
                  内容を確認し取込側を採用
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={() => applyMutation.mutate()}
              disabled={!canApply}
            >
              適用
            </button>
          </div>
        )}

        {applyMutation.isError && (
          <p className={styles.error} data-testid="import-apply-error">
            適用に失敗しました。
          </p>
        )}
        {applyMutation.isSuccess && applyMutation.data && (
          <p className={styles.success} data-testid="import-apply-success">
            適用が完了しました(適用件数: {applyMutation.data.applied_ids.length}
            件、スキップ: {applyMutation.data.skipped_ids.length}件)。
          </p>
        )}
      </section>
    </div>
  );
}
