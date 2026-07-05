import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, getPmdfEntity, updatePmdfEntity } from "../api/client";
import type { Story } from "../api/pmdfTypes";
import { YamlJsonEditor } from "../components/YamlJsonEditor";
import styles from "./EntityEditor.module.css";

type EditorMode = "form" | "yaml";

/**
 * storyエンティティ専用のフォーム編集(FR-UI-05)。
 *
 * PMDF全14 kindのうちフォーム編集を提供するのはstory(主要kind)のみとし、
 * それ以外はYAML/JSONエディタで編集する(イシュー要件「kind別フォーム
 * (story等の主要kind)+汎用YAML/JSONエディタ」)。
 */
function StoryForm({
  entity,
  onChange,
}: {
  entity: Story;
  onChange: (next: Record<string, unknown>) => void;
}) {
  const [newCriterion, setNewCriterion] = useState("");

  function updateField<K extends keyof Story>(key: K, value: Story[K]) {
    onChange({ ...entity, [key]: value });
  }

  function handleAddCriterion() {
    if (newCriterion.trim().length === 0) {
      return;
    }
    updateField("acceptance_criteria", [
      ...entity.acceptance_criteria,
      newCriterion,
    ]);
    setNewCriterion("");
  }

  return (
    <div data-testid="entity-editor-form">
      <div className={styles.field}>
        <label htmlFor="story-title">タイトル</label>
        <input
          id="story-title"
          value={entity.title ?? ""}
          onChange={(event) => updateField("title", event.target.value)}
        />
      </div>

      <div className={styles.field}>
        <label htmlFor="story-status">ステータス</label>
        <input
          id="story-status"
          value={entity.status ?? ""}
          onChange={(event) => updateField("status", event.target.value)}
        />
      </div>

      <div className={styles.field}>
        <span>受入基準</span>
        <ul className={styles.list}>
          {entity.acceptance_criteria.map((criterion, index) => (
            <li key={index}>{criterion}</li>
          ))}
        </ul>
        <div className={styles.addRow}>
          <label htmlFor="new-acceptance-criterion">新しい受入基準</label>
          <input
            id="new-acceptance-criterion"
            value={newCriterion}
            onChange={(event) => setNewCriterion(event.target.value)}
          />
          <button type="button" onClick={handleAddCriterion}>
            追加
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * PMDFエンティティの手動編集画面(FR-UI-05)。
 *
 * フォームモード(storyのみ専用フォームを提供)とYAML/JSONエディタ
 * モードを切り替えられる。保存は`PUT /pmdf/{kind}/{id}`を呼び、
 * actor(`user:<id>`)はapi-server側がJWTから解決するため人間の編集も
 * エージェント編集と同一のGit履歴+監査ログに記録される。
 */
export function EntityEditor() {
  const params = useParams<{ kind: string; id: string }>();
  const kind = params.kind as string;
  const id = params.id as string;
  const queryClient = useQueryClient();

  const [mode, setMode] = useState<EditorMode>("form");
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const entityQuery = useQuery({
    queryKey: ["pmdf", kind, id],
    queryFn: () => getPmdfEntity<Record<string, unknown>>(kind, id),
  });

  useEffect(() => {
    if (entityQuery.data && draft === null) {
      setDraft(entityQuery.data);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      updatePmdfEntity(kind, id, payload),
    onSuccess: (updated) => {
      setDraft(updated as Record<string, unknown>);
      void queryClient.invalidateQueries({ queryKey: ["pmdf", kind, id] });
    },
  });

  if (entityQuery.isLoading || draft === null) {
    return <p>読み込み中...</p>;
  }

  if (entityQuery.isError) {
    return (
      <p className={styles.error} data-testid="entity-editor-load-error">
        対象エンティティの取得に失敗しました。
      </p>
    );
  }

  const canSave = mode === "form" || parseError === null;

  function handleSave() {
    if (draft === null || !canSave) {
      return;
    }
    saveMutation.mutate(draft);
  }

  const errorMessage =
    saveMutation.isError && saveMutation.error instanceof ApiError
      ? typeof saveMutation.error.detail === "string"
        ? saveMutation.error.detail
        : JSON.stringify(saveMutation.error.detail)
      : saveMutation.isError
        ? "保存に失敗しました。"
        : null;

  return (
    <div className={styles.container}>
      <h1>
        エンティティ編集: {kind}/{id}
      </h1>

      <div className={styles.modeToggle}>
        <button
          type="button"
          className={
            mode === "form"
              ? `${styles.modeButton} ${styles.modeButtonActive}`
              : styles.modeButton
          }
          onClick={() => setMode("form")}
        >
          フォーム
        </button>
        <button
          type="button"
          className={
            mode === "yaml"
              ? `${styles.modeButton} ${styles.modeButtonActive}`
              : styles.modeButton
          }
          onClick={() => setMode("yaml")}
        >
          YAML/JSONエディタ
        </button>
      </div>

      {mode === "form" && kind === "story" && (
        <StoryForm entity={draft as unknown as Story} onChange={setDraft} />
      )}
      {mode === "form" && kind !== "story" && (
        <p>
          このkind({kind})にはフォーム編集は未対応です。YAML/JSON
          エディタを利用してください。
        </p>
      )}

      {mode === "yaml" && (
        <YamlJsonEditor
          value={draft}
          onChange={(parsed, error) => {
            setParseError(error);
            if (parsed !== null) {
              setDraft(parsed);
            }
          }}
        />
      )}

      <button
        type="button"
        className={styles.saveButton}
        onClick={handleSave}
        disabled={!canSave || saveMutation.isPending}
      >
        保存
      </button>

      {saveMutation.isSuccess && (
        <p className={styles.success} data-testid="entity-editor-success">
          保存しました。
        </p>
      )}
      {errorMessage && (
        <p className={styles.error} data-testid="entity-editor-error">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
