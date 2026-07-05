import type { BundleDiffEntry, ImportResolution } from "../api/client";
import styles from "./ConflictResolver.module.css";

export interface ConflictResolverProps {
  /** `diff_type === "conflict"`のエンティティ一覧。 */
  conflicts: BundleDiffEntry[];
  /** id→選択済みの解決方針。 */
  resolutions: Record<string, ImportResolution>;
  onResolve: (id: string, resolution: ImportResolution) => void;
  /** 手動編集導線(押下されたエンティティのdiffを渡す)。省略時はボタンを表示しない。 */
  onManualEdit?: (conflict: BundleDiffEntry) => void;
}

/**
 * バンドルimportの競合(同一idで既存側と取込側の値が異なるエンティティ)を
 * 「取込側/既存側」の2者択一で解決するUI(FR-EX-05)。
 *
 * 選択後にE7-7の`YamlJsonEditor`を開いて手動編集する導線(`onManualEdit`)も
 * 提供する(「2者択一+手動編集」要件)。
 */
export function ConflictResolver({
  conflicts,
  resolutions,
  onResolve,
  onManualEdit,
}: ConflictResolverProps) {
  if (conflicts.length === 0) {
    return null;
  }

  return (
    <div className={styles.container} data-testid="conflict-resolver">
      {conflicts.map((conflict) => {
        const selected = resolutions[conflict.id];
        return (
          <div key={conflict.id} className={styles.item}>
            <div className={styles.itemHeader}>
              競合: {conflict.kind}/{conflict.id}
            </div>
            <table className={styles.fieldTable}>
              <thead>
                <tr>
                  <th>フィールド</th>
                  <th>既存側</th>
                  <th>取込側</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(conflict.field_diffs).map(([field, diff]) => (
                  <tr key={field}>
                    <th>{field}</th>
                    <td>{JSON.stringify(diff.current)}</td>
                    <td>{JSON.stringify(diff.incoming)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className={styles.actions}>
              <button
                type="button"
                aria-pressed={selected === "incoming"}
                className={
                  selected === "incoming"
                    ? `${styles.actionButton} ${styles.actionButtonSelected}`
                    : styles.actionButton
                }
                onClick={() => onResolve(conflict.id, "incoming")}
              >
                取込側を採用
              </button>
              <button
                type="button"
                aria-pressed={selected === "existing"}
                className={
                  selected === "existing"
                    ? `${styles.actionButton} ${styles.actionButtonSelected}`
                    : styles.actionButton
                }
                onClick={() => onResolve(conflict.id, "existing")}
              >
                既存側を維持
              </button>
              {onManualEdit && (
                <button
                  type="button"
                  className={styles.actionButton}
                  onClick={() => onManualEdit(conflict)}
                >
                  手動で編集
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
