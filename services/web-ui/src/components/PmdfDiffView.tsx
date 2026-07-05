import { useQuery } from "@tanstack/react-query";
import { getPmdfEntity } from "../api/client";
import styles from "./PmdfDiffView.module.css";

export interface PmdfDiffViewProps {
  kind: string;
  /** 対象エンティティのid。新規作成起案(対象がまだ存在しない)の場合は`null`。 */
  entityId: string | null;
  /** 起案内容(変更後の値)。フィールド単位で現在値と比較する。 */
  draft: Record<string, unknown> | null;
}

interface FieldDiff {
  field: string;
  before: unknown;
  after: unknown;
}

function formatValue(value: unknown): string {
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

function computeFieldDiffs(
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

/**
 * PMDFエンティティの変更前後(現在値 vs 起案内容)をフィールド単位で
 * diff表示するコンポーネント(FR-UI-02)。
 *
 * `entityId`が`null`(新規作成起案)の場合は現在値取得をスキップし、
 * 全フィールドを「新規」として表示する。
 */
export function PmdfDiffView({ kind, entityId, draft }: PmdfDiffViewProps) {
  const entityQuery = useQuery({
    queryKey: ["pmdf", kind, entityId],
    queryFn: () =>
      getPmdfEntity<Record<string, unknown>>(kind, entityId as string),
    enabled: entityId !== null,
  });

  if (entityId !== null && entityQuery.isLoading) {
    return <p data-testid="diff-loading">読み込み中...</p>;
  }

  if (entityId !== null && entityQuery.isError) {
    return (
      <p className={styles.error} data-testid="diff-error">
        対象エンティティの取得に失敗しました。
      </p>
    );
  }

  if (draft === null || draft === undefined) {
    return (
      <p className={styles.empty} data-testid="diff-empty">
        起案内容がありません(差分情報が記録されていません)。
      </p>
    );
  }

  const diffs = computeFieldDiffs(entityQuery.data, draft);

  if (diffs.length === 0) {
    return (
      <p className={styles.empty} data-testid="diff-empty">
        現在値との差分はありません。
      </p>
    );
  }

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
            <td className={styles.before}>{formatValue(diff.before)}</td>
            <td className={styles.after}>{formatValue(diff.after)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
