import type { Metric } from "../../api/pmdfTypes";
import { KpiChart } from "../KpiChart";
import styles from "./entityViews.module.css";

/** `metric`エンティティの人間可読ビュー(FR-UI-03)。既存のKpiChartを再利用する。 */
export function MetricView({ entity }: { entity: Metric }) {
  return (
    <div data-testid="entity-view">
      {entity.definition && (
        <div className={styles.section}>
          <p>{entity.definition}</p>
        </div>
      )}

      <table className={styles.table}>
        <tbody>
          <tr>
            <th>目標値</th>
            <td>{entity.target_value ?? "-"}</td>
          </tr>
          <tr>
            <th>閾値</th>
            <td>{entity.threshold_value ?? "-"}</td>
          </tr>
          <tr>
            <th>現在値</th>
            <td>{entity.current_value ?? "-"}</td>
          </tr>
        </tbody>
      </table>

      {entity.time_series && entity.time_series.length > 0 && (
        <div className={styles.section}>
          <h3>推移</h3>
          <KpiChart metric={entity} />
        </div>
      )}
    </div>
  );
}
