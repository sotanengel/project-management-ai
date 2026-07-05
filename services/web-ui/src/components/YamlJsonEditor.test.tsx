import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { YamlJsonEditor } from "./YamlJsonEditor";

describe("YamlJsonEditor", () => {
  it("有効なJSONを入力すると、onChangeにパース済みオブジェクトが渡される", () => {
    const handleChange = vi.fn();
    render(
      <YamlJsonEditor
        value={{ title: "元のタイトル" }}
        onChange={handleChange}
      />,
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, {
      target: { value: '{"title": "新しいタイトル"}' },
    });

    expect(handleChange).toHaveBeenCalled();
    const lastCall = handleChange.mock.calls.at(-1);
    expect(lastCall?.[0]).toEqual({ title: "新しいタイトル" });
    expect(lastCall?.[1]).toBeNull();
  });

  it("不正なJSON入力時はパースエラーメッセージを表示し、onChangeには値nullとエラーを渡す", () => {
    const handleChange = vi.fn();
    render(
      <YamlJsonEditor
        value={{ title: "元のタイトル" }}
        onChange={handleChange}
      />,
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "{title: invalid" } });

    expect(screen.getByTestId("editor-parse-error")).toBeInTheDocument();
    const lastCall = handleChange.mock.calls.at(-1);
    expect(lastCall?.[0]).toBeNull();
    expect(lastCall?.[1]).not.toBeNull();
  });

  it("外部から渡されたスキーマエラー一覧をインライン表示する", () => {
    render(
      <YamlJsonEditor
        value={{ title: "タイトル" }}
        onChange={vi.fn()}
        schemaErrors={[
          "スキーマ検証エラー: 'acceptance_criteria' is a required property",
        ]}
      />,
    );

    expect(
      screen.getByText(
        "スキーマ検証エラー: 'acceptance_criteria' is a required property",
      ),
    ).toBeInTheDocument();
  });
});
