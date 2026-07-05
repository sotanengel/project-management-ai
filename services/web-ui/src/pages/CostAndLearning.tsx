import { useQuery } from "@tanstack/react-query";
import { getCostSummary } from "../api/client";
import styles from "./CostAndLearning.module.css";

function formatJpy(value: number): string {
  return value.toLocaleString("ja-JP");
}

function progressClass(status: string): string {
  if (status === "exceeded") {
    return styles.progressExceeded;
  }
  if (status === "warning") {
    return styles.progressWarning;
  }
  return styles.progressOk;
}

/**
 * コスト消化率・学習進捗画面(FR-UI-08)。
 *
 * 学習進捗はE8-8完了後に実APIへ接続予定。本イシュー時点では
 * モックデータ表示のみ(E8 API未実装のため)。
 */
export function CostAndLearning() {
  const summaryQuery = useQuery({
    queryKey: ["costs", "summary"],
    queryFn: () => getCostSummary(),
  });

  const summary = summaryQuery.data;
  const ratioPercent = summary
    ? Math.min(summary.consumption_ratio * 100, 100)
    : 0;

  return (
    <div className={styles.container}>
      <h1>コスト / 学習状況</h1>

      <section className={styles.section}>
        <h2>月次コスト消化率</h2>
        {summaryQuery.isError && (
          <p className={styles.error} role="alert">
            コストサマリの取得に失敗しました
          </p>
        )}
        {summary && (
          <>
            <div
              className={styles.progressTrack}
              data-testid="cost-progress-bar"
              data-status={summary.budget_status}
              role="progressbar"
              aria-valuenow={ratioPercent}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className={`${styles.progressFill} ${progressClass(summary.budget_status)}`}
                style={{ width: `${ratioPercent}%` }}
              />
            </div>
            <div className={styles.summaryRow}>
              <span>
                消化: ¥{formatJpy(summary.total_spend_jpy)} / ¥
                {formatJpy(summary.budget_monthly_jpy)}
              </span>
              <span>
                {ratioPercent.toFixed(1)}% ({summary.period})
              </span>
            </div>
            {summary.by_model.length > 0 && (
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>モデル</th>
                    <th>呼び出し数</th>
                    <th>コスト(円)</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.by_model.map((entry) => (
                    <tr key={entry.key}>
                      <td>{entry.key}</td>
                      <td>{entry.call_count}</td>
                      <td>{formatJpy(entry.total_cost_jpy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </section>

      <section className={styles.section}>
        <h2>自己学習ループ進捗</h2>
        <div className={styles.placeholder} data-testid="learning-placeholder">
          E8(自己学習ループ)の評価ゲートAPIは未実装のため、現時点では
          プレースホルダ表示です。E8-8完了後に実データへ接続します。
          <br />
          直近ジョブ: 未実行 / 評価ゲート: —
        </div>
      </section>
    </div>
  );
}
