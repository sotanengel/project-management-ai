import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPmdfEntity, getPmdfEntityHistory } from "../api/client";
import { computeFullSnapshotDiffs, FieldDiffTable } from "./FieldDiffTable";
import styles from "./VersionDiff.module.css";

export interface VersionDiffProps {
  kind: string;
  entityId: string;
}

/**
 * Git履歴(E3-2)ベースの版一覧から任意の2版を選択し、フィールド単位で
 * diff表示するコンポーネント(FR-UI-03)。`PmdfDiffView`のdiffテーブルを
 * 再利用する。
 */
export function VersionDiff({ kind, entityId }: VersionDiffProps) {
  const historyQuery = useQuery({
    queryKey: ["pmdf", kind, entityId, "history"],
    queryFn: () => getPmdfEntityHistory(kind, entityId),
  });

  const history = historyQuery.data ?? [];
  const [fromRef, setFromRef] = useState<string>("");
  const [toRef, setToRef] = useState<string>("");

  const effectiveFrom = fromRef || history[1]?.commit_hash || "";
  const effectiveTo = toRef || history[0]?.commit_hash || "";

  const canCompare = history.length >= 2;

  const fromQuery = useQuery({
    queryKey: ["pmdf", kind, entityId, "ref", effectiveFrom],
    queryFn: () =>
      getPmdfEntity<Record<string, unknown>>(kind, entityId, effectiveFrom),
    enabled: canCompare && effectiveFrom !== "",
  });

  const toQuery = useQuery({
    queryKey: ["pmdf", kind, entityId, "ref", effectiveTo],
    queryFn: () =>
      getPmdfEntity<Record<string, unknown>>(kind, entityId, effectiveTo),
    enabled: canCompare && effectiveTo !== "",
  });

  if (historyQuery.isLoading) {
    return <p>読み込み中...</p>;
  }

  if (historyQuery.isError) {
    return (
      <p className={styles.error} data-testid="version-diff-error">
        履歴の取得に失敗しました。
      </p>
    );
  }

  if (history.length < 2) {
    return <p className={styles.empty}>比較できる版がまだありません</p>;
  }

  const diffs =
    fromQuery.data && toQuery.data
      ? computeFullSnapshotDiffs(fromQuery.data, toQuery.data)
      : [];

  return (
    <div className={styles.container}>
      <div className={styles.selectors}>
        <label>
          比較元
          <select
            data-testid="version-select-from"
            value={effectiveFrom}
            onChange={(event) => setFromRef(event.target.value)}
          >
            {history.map((entry) => (
              <option key={entry.commit_hash} value={entry.commit_hash}>
                {entry.committed_at} ({entry.message})
              </option>
            ))}
          </select>
        </label>
        <label>
          比較先
          <select
            data-testid="version-select-to"
            value={effectiveTo}
            onChange={(event) => setToRef(event.target.value)}
          >
            {history.map((entry) => (
              <option key={entry.commit_hash} value={entry.commit_hash}>
                {entry.committed_at} ({entry.message})
              </option>
            ))}
          </select>
        </label>
      </div>

      {diffs.length === 0 ? (
        <p className={styles.empty}>選択した2版に差分はありません。</p>
      ) : (
        <FieldDiffTable diffs={diffs} />
      )}
    </div>
  );
}
