import type { PmdfEntityBase } from "../../api/pmdfTypes";
import styles from "./entityViews.module.css";

const HIDDEN_FIELDS = new Set(["kind", "id", "pmdf_version"]);

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

/**
 * kind別の専用ビューを持たないエンティティ種別のための汎用キー値表示
 * (FR-UI-03: 「他は汎用キー値表示で可」)。
 */
export function GenericEntityView({ entity }: { entity: PmdfEntityBase }) {
  const fields = Object.entries(entity).filter(
    ([key]) => !HIDDEN_FIELDS.has(key),
  );

  return (
    <div data-testid="entity-view">
      <p className={styles.badge}>id: {entity.id}</p>
      <table className={styles.table}>
        <tbody>
          {fields.map(([key, value]) => (
            <tr key={key}>
              <th>{key}</th>
              <td>
                <pre>{formatValue(value)}</pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
