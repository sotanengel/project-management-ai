import { useQuery } from "@tanstack/react-query";
import { getCostSummary, getLearningStatus } from "../api/client";
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

function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString("ja-JP");
}

/**
 * コスト消化率・学習進捗画面(FR-UI-08)。
 *
 * 学習進捗は`GET /learning/status`(E8-8)から取得する。自己学習ループが
 * 未実行の環境では「学習実績なし」の空状態を表示する。
 */
export function CostAndLearning() {
  const summaryQuery = useQuery({
    queryKey: ["costs", "summary"],
    queryFn: () => getCostSummary(),
  });

  const learningQuery = useQuery({
    queryKey: ["learning", "status"],
    queryFn: () => getLearningStatus(),
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

      <section className={styles.section} data-testid="learning-status">
        <h2>自己学習ループ進捗</h2>
        {learningQuery.isError && (
          <p className={styles.error} role="alert">
            学習状況の取得に失敗しました
          </p>
        )}
        {learningQuery.data && !learningQuery.data.has_activity && (
          <p className={styles.placeholder}>学習実績なし</p>
        )}
        {learningQuery.data?.latest_job && (
          <div className={styles.summaryRow}>
            <span>
              直近ジョブ: {learningQuery.data.latest_job.job_type} /{" "}
              {learningQuery.data.latest_job.status}(
              {formatTimestamp(learningQuery.data.latest_job.timestamp)})
            </span>
          </div>
        )}
        {learningQuery.data &&
          (learningQuery.data.gate_history ?? []).length > 0 && (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>日時</th>
                  <th>判定</th>
                  <th>指標</th>
                </tr>
              </thead>
              <tbody>
                {(learningQuery.data.gate_history ?? []).map((entry, index) => (
                  <tr key={`${entry.timestamp}-${index}`}>
                    <td>{formatTimestamp(entry.timestamp)}</td>
                    <td>{entry.decision ?? "—"}</td>
                    <td>{JSON.stringify(entry.metrics ?? {})}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </section>
    </div>
  );
}
