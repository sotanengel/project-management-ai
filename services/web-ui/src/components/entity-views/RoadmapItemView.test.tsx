import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoadmapItemView } from "./RoadmapItemView";
import type { RoadmapItem } from "../../api/pmdfTypes";

const ITEM: RoadmapItem = {
  kind: "roadmap_item",
  id: "roadmap-01",
  theme: "検索体験の刷新",
  period: "2026-Q3",
  status: "in_progress",
  objective: "obj-01",
};

describe("RoadmapItemView", () => {
  it("テーマ・期間・ステータスを表示する", () => {
    render(<RoadmapItemView entity={ITEM} />);

    expect(screen.getByText("検索体験の刷新")).toBeInTheDocument();
    expect(screen.getByText("2026-Q3")).toBeInTheDocument();
    expect(screen.getByText(/進行中|in_progress/)).toBeInTheDocument();
  });
});
