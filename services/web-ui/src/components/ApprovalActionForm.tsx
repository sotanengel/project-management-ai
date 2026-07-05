import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { decideApproval } from "../api/client";
import styles from "./ApprovalActionForm.module.css";

export interface ApprovalActionFormProps {
  proposalId: string;
  /** 決定者(承認者)のstakeholder id。 */
  approver: string;
  /** 承認/差し戻し完了時に呼ばれるコールバック(一覧再取得等に使う)。 */
  onDecided?: () => void;
}

/**
 * 承認/差し戻しの操作フォーム(FR-UI-02)。
 *
 * 差し戻しは理由入力必須(未入力では送信ボタンを無効化する。E3-6の422検証と
 * 二重にUI側でもバリデーションする)。承認は確認ダイアログを経由する。
 */
export function ApprovalActionForm({
  proposalId,
  approver,
  onDecided,
}: ApprovalActionFormProps) {
  const [rejectReason, setRejectReason] = useState("");

  const decideMutation = useMutation({
    mutationFn: (params: {
      decision: "approved" | "rejected";
      reason: string;
    }) =>
      decideApproval(proposalId, {
        decision: params.decision,
        approver,
        reason: params.reason,
      }),
    onSuccess: () => {
      onDecided?.();
    },
  });

  function handleApprove() {
    const confirmed = window.confirm("この起案を承認します。よろしいですか?");
    if (!confirmed) {
      return;
    }
    decideMutation.mutate({ decision: "approved", reason: "承認" });
  }

  function handleReject() {
    if (rejectReason.trim().length === 0) {
      return;
    }
    decideMutation.mutate({ decision: "rejected", reason: rejectReason });
  }

  return (
    <div className={styles.container}>
      <button
        type="button"
        className={styles.approveButton}
        onClick={handleApprove}
        disabled={decideMutation.isPending}
      >
        承認
      </button>

      <div className={styles.rejectGroup}>
        <label htmlFor={`reject-reason-${proposalId}`}>差し戻し理由</label>
        <textarea
          id={`reject-reason-${proposalId}`}
          value={rejectReason}
          onChange={(event) => setRejectReason(event.target.value)}
          rows={2}
          className={styles.reasonInput}
        />
        <button
          type="button"
          className={styles.rejectButton}
          onClick={handleReject}
          disabled={
            rejectReason.trim().length === 0 || decideMutation.isPending
          }
        >
          差し戻し
        </button>
      </div>

      {decideMutation.isError && (
        <p className={styles.error} data-testid="decide-error">
          操作に失敗しました。
        </p>
      )}
    </div>
  );
}
