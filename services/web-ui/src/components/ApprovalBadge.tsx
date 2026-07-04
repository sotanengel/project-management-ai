import { useAppState } from "../state/useAppState";
import styles from "./ApprovalBadge.module.css";

/** 承認待ち件数を常時表示するバッジ(FR-UI-11)。0件時は非表示。 */
export function ApprovalBadge() {
  const { pendingApprovalCount } = useAppState();

  if (pendingApprovalCount <= 0) {
    return null;
  }

  return (
    <span
      className={styles.badge}
      data-testid="approval-badge"
      aria-label="承認待ち件数"
    >
      {pendingApprovalCount}
    </span>
  );
}
