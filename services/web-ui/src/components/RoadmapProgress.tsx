import type { RoadmapItem, RoadmapItemStatus } from "../api/pmdfTypes";
import styles from "./RoadmapProgress.module.css";

const STATUS_LABELS: Record<RoadmapItemStatus, string> = {
  planned: "計画中",
  in_progress: "進行中",
  done: "完了",
  cancelled: "中止",
};

const STATUS_ORDER: RoadmapItemStatus[] = [
  "planned",
  "in_progress",
  "done",
  "cancelled",
];

export function RoadmapProgress({ items }: { items: RoadmapItem[] }) {
  const counts = STATUS_ORDER.reduce<Record<RoadmapItemStatus, number>>(
    (acc, status) => {
      acc[status] = items.filter((item) => item.status === status).length;
      return acc;
    },
    { planned: 0, in_progress: 0, done: 0, cancelled: 0 },
  );

  const completionRate =
    items.length === 0 ? 0 : Math.round((counts.done / items.length) * 100);

  return (
    <section className={styles.container} aria-label="ロードマップ進捗">
      <h2>ロードマップ進捗</h2>
      <p className={styles.rate} data-testid="roadmap-completion-rate">
        完了率: {completionRate}%
      </p>
      <ul className={styles.statusList}>
        {STATUS_ORDER.map((status) => (
          <li key={status} data-testid={`roadmap-status-${status}`}>
            <span>{STATUS_LABELS[status]}</span>
            <strong>{counts[status]}</strong>
          </li>
        ))}
      </ul>
    </section>
  );
}
