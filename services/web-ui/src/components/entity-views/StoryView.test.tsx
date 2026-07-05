import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StoryView } from "./StoryView";
import type { Story } from "../../api/pmdfTypes";

const STORY: Story = {
  kind: "story",
  id: "story-01",
  title: "検索機能の改善",
  as_a: "ユーザーとして",
  i_want: "検索結果を絞り込みたい",
  so_that: "目的の情報に早くたどり着けるようにしたい",
  acceptance_criteria: [
    "フィルタUIが表示される",
    "絞り込み結果が即時反映される",
  ],
  priority: { method: "RICE", score: 8.5 },
  status: "ready",
};

describe("StoryView", () => {
  it("ユーザーストーリー形式(As a/I want/So that)と受入基準を表示する", () => {
    render(<StoryView entity={STORY} />);

    expect(screen.getByText("ユーザーとして")).toBeInTheDocument();
    expect(screen.getByText("検索結果を絞り込みたい")).toBeInTheDocument();
    expect(
      screen.getByText("目的の情報に早くたどり着けるようにしたい"),
    ).toBeInTheDocument();
    expect(screen.getByText("フィルタUIが表示される")).toBeInTheDocument();
    expect(screen.getByText(/RICE/)).toBeInTheDocument();
  });
});
