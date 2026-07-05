import { useEffect, useState } from "react";
import styles from "./YamlJsonEditor.module.css";

export interface YamlJsonEditorProps {
  /** 編集対象の値。JSON.stringifyで整形表示する(YAML変換は行わず、
   * JSONのシンタックスをそのままYAMLライクな軽量エディタとして扱う)。 */
  value: Record<string, unknown>;
  /**
   * テキスト変更のたびに呼ばれる。パース成功時は`(parsed, null)`、
   * 失敗時は`(null, errorMessage)`を渡す。
   */
  onChange: (
    parsed: Record<string, unknown> | null,
    parseError: string | null,
  ) => void;
  /** サーバー側スキーマ検証エラー等、外部から渡すエラー一覧。 */
  schemaErrors?: string[];
}

/**
 * PMDFエンティティをテキストで直接編集するための軽量エディタ(FR-UI-05)。
 *
 * 重量級のコードエディタライブラリ(monaco-editor等)は導入せず、
 * プレーンな`<textarea>` + JSON.parseによるリアルタイム構文検証のみを
 * 提供する(イシュー要件は「シンタックスハイライトは軽量ライブラリ1つまで」
 * であり必須ではないため)。
 */
export function YamlJsonEditor({
  value,
  onChange,
  schemaErrors,
}: YamlJsonEditorProps) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  // 外部から`value`が差し替えられた場合(初期ロード完了等)にテキストへ反映する。
  useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setParseError(null);
  }, [value]);

  function handleTextChange(nextText: string) {
    setText(nextText);
    try {
      const parsed = JSON.parse(nextText) as Record<string, unknown>;
      setParseError(null);
      onChange(parsed, null);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "JSONの構文が不正です";
      setParseError(message);
      onChange(null, message);
    }
  }

  return (
    <div className={styles.container}>
      <textarea
        className={
          parseError
            ? `${styles.textarea} ${styles.textareaInvalid}`
            : styles.textarea
        }
        value={text}
        onChange={(event) => handleTextChange(event.target.value)}
        spellCheck={false}
        aria-invalid={parseError !== null}
      />
      {parseError && (
        <p className={styles.error} data-testid="editor-parse-error">
          構文エラー: {parseError}
        </p>
      )}
      {schemaErrors && schemaErrors.length > 0 && (
        <ul className={styles.errorList} data-testid="editor-schema-errors">
          {schemaErrors.map((message, index) => (
            <li key={index} className={styles.error}>
              {message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
