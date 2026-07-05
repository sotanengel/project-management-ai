import type { RoadmapItem } from "../../api/pmdfTypes";
import styles from "./entityViews.module.css";

const STATUS_LABELS: Record<string, string> = {
  planned: "計画中",
  in_progress: "進行中",
  done: "完了",
  cancelled: "中止",
};

/** `roadmap_item`エンティティの人間可読ビュー(FR-UI-03)。 */
export function RoadmapItemView({ entity }: { entity: RoadmapItem }) {
  return (
    <div data-testid="entity-view">
      <div className={styles.section}>
        <h3>テーマ</h3>
        <p>{entity.theme}</p>
      </div>

      <table className={styles.table}>
        <tbody>
          <tr>
            <th>期間</th>
            <td>{entity.period}</td>
          </tr>
          <tr>
            <th>ステータス</th>
            <td>{STATUS_LABELS[entity.status] ?? entity.status}</td>
          </tr>
          {entity.objective && (
            <tr>
              <th>関連目標</th>
              <td>{entity.objective}</td>
            </tr>
          )}
          {entity.dependencies && entity.dependencies.length > 0 && (
            <tr>
              <th>依存関係</th>
              <td>{entity.dependencies.join(", ")}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
