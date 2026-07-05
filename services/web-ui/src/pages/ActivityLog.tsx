import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditRecords, listChatTasks } from "../api/client";
import type { AuditLogSearchFilters } from "../components/AuditLogSearch";
import { AuditLogSearch } from "../components/AuditLogSearch";
import { EvidencePanel } from "../components/EvidencePanel";
import styles from "./ActivityLog.module.css";

const STATUS_LABELS: Record<string, string> = {
  pending: "受付済み",
  running: "実行中",
  done: "完了",
  failed: "失敗",
};

function extractModel(
  result: Record<string, unknown> | null | undefined,
): string | null {
  const model = result?.model;
  return typeof model === "string" ? model : null;
}

function extractEvidence(
  result: Record<string, unknown> | null | undefined,
): Array<Record<string, unknown>> {
  const evidence = result?.x_evidence;
  return Array.isArray(evidence)
    ? (evidence as Array<Record<string, unknown>>)
    : [];
}

/** エージェント活動ログ画面(FR-UI-04)。実行中/完了タスク一覧・根拠表示・監査ログ検索。 */
export function ActivityLog() {
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);
  const [auditFilters, setAuditFilters] =
    useState<AuditLogSearchFilters | null>(null);

  const tasksQuery = useQuery({
    queryKey: ["chat", "tasks"],
    queryFn: () => listChatTasks(),
  });

  const auditQuery = useQuery({
    queryKey: ["audit", "records", auditFilters],
    queryFn: () =>
      listAuditRecords(
        auditFilters
          ? {
              actor: auditFilters.actor || undefined,
              action: auditFilters.action || undefined,
              kind: auditFilters.kind || undefined,
              dateFrom: auditFilters.dateFrom || undefined,
              dateTo: auditFilters.dateTo || undefined,
            }
          : undefined,
      ),
  });

  const tasks = tasksQuery.data ?? [];
  const auditRecords = auditQuery.data ?? [];

  return (
    <div className={styles.container}>
      <h1>エージェント活動ログ</h1>

      <section className={styles.section}>
        <h2>タスク一覧</h2>
        {tasks.length === 0 ? (
          <p className={styles.empty}>タスクがありません</p>
        ) : (
          <ul className={styles.taskList}>
            {tasks.map((task) => {
              const isExpanded = expandedTaskId === task.id;
              const result = task.result as Record<string, unknown> | null;
              return (
                <li key={task.id} className={styles.taskItem}>
                  <button
                    type="button"
                    className={styles.taskHeader}
                    onClick={() =>
                      setExpandedTaskId(isExpanded ? null : task.id)
                    }
                  >
                    <span className={styles.taskStatus}>
                      {STATUS_LABELS[task.status] ?? task.status}
                    </span>
                    <span>{task.message}</span>
                    {task.intent && (
                      <span className={styles.taskIntent}>{task.intent}</span>
                    )}
                  </button>

                  {isExpanded && (
                    <div className={styles.taskDetail}>
                      <p>
                        使用モデル:{" "}
                        <strong>{extractModel(result) ?? "不明"}</strong>
                      </p>
                      {task.error && (
                        <p className={styles.taskError}>エラー: {task.error}</p>
                      )}
                      <h3>根拠</h3>
                      <EvidencePanel evidence={extractEvidence(result)} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h2>監査ログ</h2>
        <AuditLogSearch onSearch={setAuditFilters} />

        {auditRecords.length === 0 ? (
          <p className={styles.empty}>該当する監査ログがありません</p>
        ) : (
          <table className={styles.auditTable}>
            <thead>
              <tr>
                <th>日時</th>
                <th>actor</th>
                <th>操作</th>
                <th>対象</th>
              </tr>
            </thead>
            <tbody>
              {auditRecords.map((record, index) => (
                <tr key={index}>
                  <td>{record.timestamp}</td>
                  <td>{record.actor}</td>
                  <td>{record.action}</td>
                  <td>
                    {record.target_kind}:{record.target_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
