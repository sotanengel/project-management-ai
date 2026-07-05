import styles from "./PmdfDiffView.module.css";

export interface FieldDiff {
  field: string;
  before: unknown;
  after: unknown;
}

export function formatDiffValue(value: unknown): string {
  if (value === undefined) {
    return "(未設定)";
  }
  if (value === null) {
    return "(null)";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

/**
 * `before`と`after`(いずれも完全なエンティティのスナップショット)から
 * フィールド単位のdiffを計算する。どちらかにしか存在しないキーも含め、
 * 和集合で比較する(版間diff、`VersionDiff`向け)。
 */
export function computeFullSnapshotDiffs(
  before: Record<string, unknown> | undefined,
  after: Record<string, unknown> | undefined,
): FieldDiff[] {
  const keys = new Set([
    ...Object.keys(before ?? {}),
    ...Object.keys(after ?? {}),
  ]);
  const diffs: FieldDiff[] = [];
  for (const field of keys) {
    const beforeValue = before ? before[field] : undefined;
    const afterValue = after ? after[field] : undefined;
    if (JSON.stringify(beforeValue) !== JSON.stringify(afterValue)) {
      diffs.push({ field, before: beforeValue, after: afterValue });
    }
  }
  return diffs;
}

/**
 * 現在値(`current`)と起案内容(`draft`、変更予定フィールドのみを含む
 * 部分オブジェクト)からフィールド単位のdiffを計算する。`draft`に含まれる
 * キーのみを比較対象とする(承認キューのPMDF diff表示、`PmdfDiffView`向け)。
 */
export function computeDraftDiffs(
  current: Record<string, unknown> | undefined,
  draft: Record<string, unknown>,
): FieldDiff[] {
  const diffs: FieldDiff[] = [];
  for (const [field, after] of Object.entries(draft)) {
    const before = current ? current[field] : undefined;
    if (JSON.stringify(before) !== JSON.stringify(after)) {
      diffs.push({ field, before, after });
    }
  }
  return diffs;
}

/** フィールド単位のdiffを色分け表示するテーブル(FR-UI-02/FR-UI-03共通)。 */
export function FieldDiffTable({ diffs }: { diffs: FieldDiff[] }) {
  return (
    <table className={styles.table} data-testid="diff-table">
      <thead>
        <tr>
          <th>フィールド</th>
          <th>変更前</th>
          <th>変更後</th>
        </tr>
      </thead>
      <tbody>
        {diffs.map((diff) => (
          <tr
            key={diff.field}
            data-testid={`diff-field-${diff.field}`}
            className={styles.row}
          >
            <td className={styles.fieldName}>{diff.field}</td>
            <td className={styles.before}>{formatDiffValue(diff.before)}</td>
            <td className={styles.after}>{formatDiffValue(diff.after)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
