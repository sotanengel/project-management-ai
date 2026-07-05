import { NavLink, Outlet } from "react-router-dom";
import { ApprovalBadge } from "./ApprovalBadge";
import { useAppState } from "../state/useAppState";
import styles from "./Layout.module.css";

const NAV_ITEMS: Array<{
  to: string;
  label: string;
  showApprovalBadge?: boolean;
}> = [
  { to: "/dashboard", label: "ダッシュボード" },
  { to: "/approvals", label: "承認キュー", showApprovalBadge: true },
  { to: "/documents", label: "ドキュメント" },
  { to: "/activity", label: "活動ログ" },
  { to: "/import-export", label: "Import-Export" },
  { to: "/agent-control", label: "エージェント制御" },
  { to: "/costs", label: "コスト" },
];

/** 全ページ共通のヘッダ・サイドナビを提供するレイアウト。 */
export function Layout() {
  const { isWsConnected } = useAppState();

  return (
    <div className={styles.layout}>
      <header className={styles.header}>
        <span className={styles.title}>PdM AI 監督UI</span>
        <span
          className={styles.wsStatus}
          data-testid="ws-status"
          title={
            isWsConnected
              ? "リアルタイム更新: 接続中"
              : "リアルタイム更新: 切断中"
          }
        >
          {isWsConnected ? "接続中" : "切断中"}
        </span>
      </header>
      <div className={styles.body}>
        <nav className={styles.nav} aria-label="メインナビゲーション">
          <ul>
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    isActive
                      ? `${styles.navLink} ${styles.navLinkActive}`
                      : styles.navLink
                  }
                >
                  <span>{item.label}</span>
                  {item.showApprovalBadge && <ApprovalBadge />}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className={styles.main}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
