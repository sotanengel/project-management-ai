import type { Decision } from "../../api/pmdfTypes";
import styles from "./entityViews.module.css";

/** `decision`(Decision Record)エンティティの人間可読ビュー(FR-UI-03)。 */
export function DecisionView({ entity }: { entity: Decision }) {
  return (
    <div data-testid="entity-view">
      <div className={styles.section}>
        <h3>背景</h3>
        <p>{entity.background}</p>
      </div>

      <div className={styles.section}>
        <h3>選択肢</h3>
        {entity.options.map((option) => (
          <div
            key={option.name}
            className={
              option.name === entity.chosen_option
                ? `${styles.optionCard} ${styles.chosen}`
                : styles.optionCard
            }
          >
            <strong>{option.name}</strong>
            {option.name === entity.chosen_option && " (採用)"}
            {option.description && <p>{option.description}</p>}
            {option.pros && option.pros.length > 0 && (
              <p>長所: {option.pros.join(", ")}</p>
            )}
            {option.cons && option.cons.length > 0 && (
              <p>短所: {option.cons.join(", ")}</p>
            )}
          </div>
        ))}
      </div>

      <div className={styles.section}>
        <h3>採用案</h3>
        <p>{entity.chosen_option}</p>
      </div>

      <div className={styles.section}>
        <h3>根拠</h3>
        <p>{entity.rationale}</p>
      </div>

      {entity.rejected_reasons.length > 0 && (
        <div className={styles.section}>
          <h3>却下理由</h3>
          <ul className={styles.list}>
            {entity.rejected_reasons.map((rejected) => (
              <li key={rejected.option}>
                <strong>{rejected.option}</strong>
                <p>{rejected.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className={styles.section}>
        <h3>自律レベル</h3>
        <p>{entity.autonomy_level}</p>
      </div>
    </div>
  );
}
