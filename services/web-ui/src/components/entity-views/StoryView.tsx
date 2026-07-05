import type { Story } from "../../api/pmdfTypes";
import styles from "./entityViews.module.css";

/** `story`エンティティの人間可読ビュー(FR-UI-03)。 */
export function StoryView({ entity }: { entity: Story }) {
  return (
    <div data-testid="entity-view">
      <div className={styles.section}>
        <h3>ユーザーストーリー</h3>
        <p>
          <strong>{entity.as_a}</strong>
        </p>
        <p>{entity.i_want}</p>
        <p>{entity.so_that}</p>
      </div>

      <div className={styles.section}>
        <h3>受入基準</h3>
        <ul className={styles.list}>
          {entity.acceptance_criteria.map((criterion, index) => (
            <li key={index}>{criterion}</li>
          ))}
        </ul>
      </div>

      <div className={styles.section}>
        <h3>優先順位</h3>
        <p>
          <span className={styles.badge}>{entity.priority.method}</span>{" "}
          {entity.priority.score !== undefined &&
            entity.priority.score !== null &&
            `スコア: ${entity.priority.score}`}
        </p>
      </div>

      <div className={styles.section}>
        <h3>ステータス</h3>
        <p>{entity.status}</p>
      </div>
    </div>
  );
}
