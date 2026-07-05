import { useState } from "react";
import styles from "./AuditLogSearch.module.css";

export interface AuditLogSearchFilters {
  actor: string;
  action: string;
  kind: string;
  dateFrom: string;
  dateTo: string;
}

export interface AuditLogSearchProps {
  onSearch: (filters: AuditLogSearchFilters) => void;
}

const INITIAL_FILTERS: AuditLogSearchFilters = {
  actor: "",
  action: "",
  kind: "",
  dateFrom: "",
  dateTo: "",
};

/** 監査ログ検索フィルタUI(FR-UI-04)。actor/操作種別/対象kind/期間で絞り込む。 */
export function AuditLogSearch({ onSearch }: AuditLogSearchProps) {
  const [filters, setFilters] =
    useState<AuditLogSearchFilters>(INITIAL_FILTERS);

  function updateField<K extends keyof AuditLogSearchFilters>(
    field: K,
    value: AuditLogSearchFilters[K],
  ) {
    setFilters((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <form
      className={styles.form}
      onSubmit={(event) => {
        event.preventDefault();
        onSearch(filters);
      }}
    >
      <label>
        actor
        <input
          value={filters.actor}
          onChange={(event) => updateField("actor", event.target.value)}
        />
      </label>
      <label>
        操作種別
        <input
          value={filters.action}
          onChange={(event) => updateField("action", event.target.value)}
        />
      </label>
      <label>
        対象種別
        <input
          value={filters.kind}
          onChange={(event) => updateField("kind", event.target.value)}
        />
      </label>
      <label>
        期間(from)
        <input
          type="datetime-local"
          value={filters.dateFrom}
          onChange={(event) => updateField("dateFrom", event.target.value)}
        />
      </label>
      <label>
        期間(to)
        <input
          type="datetime-local"
          value={filters.dateTo}
          onChange={(event) => updateField("dateTo", event.target.value)}
        />
      </label>
      <button type="submit" className={styles.searchButton}>
        検索
      </button>
    </form>
  );
}
