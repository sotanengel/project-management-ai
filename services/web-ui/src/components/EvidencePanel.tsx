import { Link } from "react-router-dom";
import styles from "./EvidencePanel.module.css";

export interface EvidencePanelProps {
  /** `x_evidence`拡張フィールド(E5-8)の配列。 */
  evidence: Array<Record<string, unknown>>;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** 根拠(evidence)を人間可読に表示するパネル(FR-UI-04)。KB出典/PMDF参照/データ根拠の3種別に対応する。 */
export function EvidencePanel({ evidence }: EvidencePanelProps) {
  if (evidence.length === 0) {
    return <p className={styles.empty}>根拠情報がありません</p>;
  }

  return (
    <ul className={styles.list}>
      {evidence.map((item, index) => {
        const source = asString(item.source);
        return (
          <li key={index} className={styles.item}>
            {source === "kb" && (
              <div>
                <span className={styles.badge}>KB出典</span>
                <p className={styles.domain}>{asString(item.domain)}</p>
                {Boolean(item.framework) && (
                  <p className={styles.meta}>
                    フレームワーク: {asString(item.framework)}
                  </p>
                )}
                {Boolean(item.excerpt) && (
                  <p className={styles.excerpt}>{asString(item.excerpt)}</p>
                )}
              </div>
            )}
            {source === "pmdf" && (
              <div>
                <span className={styles.badge}>PMDF参照</span>
                <p>
                  <Link
                    to={`/documents/${asString(item.kind)}/${asString(item.id)}`}
                  >
                    {asString(item.kind)}:{asString(item.id)}
                  </Link>
                </p>
              </div>
            )}
            {source === "data" && (
              <div>
                <span className={styles.badge}>データ根拠</span>
                <p>{asString(item.description)}</p>
                {item.data !== undefined && (
                  <pre className={styles.dataValue}>
                    {JSON.stringify(item.data, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
