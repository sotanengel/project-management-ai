import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listApprovals } from "../api/client";
import { inferKindFromId } from "../api/pmdfTypes";
import { PmdfDiffView } from "../components/PmdfDiffView";
import { ApprovalActionForm } from "../components/ApprovalActionForm";
import { useAppState } from "../state/useAppState";
import styles from "./Approvals.module.css";

/** 承認キュー画面(FR-UI-02)。L1起案(`proposed`状態)の一覧・PMDF diff・承認/差し戻し操作。 */
export function Approvals() {
  const { pendingApprovalCount } = useAppState();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const proposalsQuery = useQuery({
    queryKey: ["approvals", "pending", pendingApprovalCount],
    queryFn: () => listApprovals("pending"),
  });

  const proposals = proposalsQuery.data ?? [];

  function handleDecided() {
    void queryClient.invalidateQueries({ queryKey: ["approvals"] });
  }

  return (
    <div className={styles.container}>
      <h1>承認キュー</h1>

      {proposalsQuery.isLoading && <p>読み込み中...</p>}

      {!proposalsQuery.isLoading && proposals.length === 0 && (
        <p className={styles.empty}>承認待ちの起案はありません</p>
      )}

      <ul className={styles.list}>
        {proposals.map((proposal) => {
          const isExpanded = expandedId === proposal.id;
          const kind = inferKindFromId(proposal.target);
          return (
            <li key={proposal.id} className={styles.item}>
              <div className={styles.itemHeader}>
                <span className={styles.target}>対象: {proposal.target}</span>
                <span className={styles.proposer}>
                  起案者: {proposal.proposer}
                </span>
                <button
                  type="button"
                  className={styles.toggleButton}
                  onClick={() => setExpandedId(isExpanded ? null : proposal.id)}
                >
                  {isExpanded ? "閉じる" : "詳細"}
                </button>
              </div>

              {isExpanded && (
                <div className={styles.detail}>
                  {kind ? (
                    <PmdfDiffView
                      kind={kind}
                      entityId={proposal.target}
                      draft={
                        (proposal.draft as Record<string, unknown> | null) ??
                        null
                      }
                    />
                  ) : (
                    <p className={styles.error}>
                      対象の種別を特定できませんでした(id: {proposal.target})
                    </p>
                  )}
                  <ApprovalActionForm
                    proposalId={proposal.id}
                    approver={proposal.proposer}
                    onDecided={handleDecided}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
