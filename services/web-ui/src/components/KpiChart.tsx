import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Metric } from "../api/pmdfTypes";
import styles from "./KpiChart.module.css";

function formatValue(value: number | null): string {
  return value === null ? "未計測" : value.toString();
}

export function KpiChart({ metric }: { metric: Metric }) {
  const series = metric.time_series ?? [];
  const chartData = series.map((point) => ({
    timestamp: point.timestamp.slice(0, 10),
    value: point.value,
  }));

  return (
    <section className={styles.container} aria-label={`KPI: ${metric.name}`}>
      <h2>{metric.name}</h2>
      <p className={styles.currentValue} data-testid="kpi-current-value">
        現在値: {formatValue(metric.current_value)}
      </p>
      {chartData.length > 0 ? (
        <div className={styles.chartWrapper}>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData}>
              <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#2f5bea"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className={styles.noData}>推移データがありません</p>
      )}
    </section>
  );
}
