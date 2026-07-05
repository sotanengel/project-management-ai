import { useQuery } from "@tanstack/react-query";
import { listApprovals } from "../api/client";
import styles from "./ApprovalHistory.module.css";

const STATUS_LABELS: Record<string, string> = {
  approved: "承認済み",
  rejected: "差し戻し",
};

/** 承認履歴画面(FR-UI-02)。過去の承認/差し戻し判断とその理由を一覧表示する。 */
export function ApprovalHistory() {
  const historyQuery = useQuery({
    queryKey: ["approvals", "history"],
    queryFn: () => listApprovals(),
  });

  const decided = (historyQuery.data ?? []).filter(
    (proposal) =>
      proposal.status === "approved" || proposal.status === "rejected",
  );

  return (
    <div className={styles.container}>
      <h1>承認履歴</h1>

      {historyQuery.isLoading && <p>読み込み中...</p>}

      {!historyQuery.isLoading && decided.length === 0 && (
        <p className={styles.empty}>承認履歴はまだありません</p>
      )}

      <ul className={styles.list}>
        {decided.map((proposal) => (
          <li key={proposal.id} className={styles.item}>
            <div className={styles.itemHeader}>
              <span
                className={
                  proposal.status === "approved"
                    ? styles.approved
                    : styles.rejected
                }
              >
                {STATUS_LABELS[proposal.status] ?? proposal.status}
              </span>
              <span className={styles.target}>対象: {proposal.target}</span>
              <span className={styles.approver}>
                決定者: {proposal.approver ?? "-"}
              </span>
            </div>
            {proposal.reason && (
              <p className={styles.reason}>{proposal.reason}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
