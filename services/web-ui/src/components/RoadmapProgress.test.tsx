import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RoadmapProgress } from "./RoadmapProgress";
import type { RoadmapItem } from "../api/pmdfTypes";

function makeItem(status: RoadmapItem["status"], id: string): RoadmapItem {
  return {
    kind: "roadmap_item",
    id,
    product: "product-01",
    theme: "テーマ",
    period: "2026-Q3",
    status,
  };
}

describe("RoadmapProgress", () => {
  it("ステータス別の件数集計を表示する", () => {
    const items: RoadmapItem[] = [
      makeItem("planned", "r-1"),
      makeItem("planned", "r-2"),
      makeItem("in_progress", "r-3"),
      makeItem("done", "r-4"),
      makeItem("done", "r-5"),
      makeItem("done", "r-6"),
      makeItem("cancelled", "r-7"),
    ];
    render(<RoadmapProgress items={items} />);

    expect(screen.getByTestId("roadmap-status-planned")).toHaveTextContent("2");
    expect(screen.getByTestId("roadmap-status-in_progress")).toHaveTextContent(
      "1",
    );
    expect(screen.getByTestId("roadmap-status-done")).toHaveTextContent("3");
    expect(screen.getByTestId("roadmap-status-cancelled")).toHaveTextContent(
      "1",
    );
  });

  it("完了率を表示する(done件数 / 全件数)", () => {
    const items: RoadmapItem[] = [
      makeItem("done", "r-1"),
      makeItem("planned", "r-2"),
      makeItem("planned", "r-3"),
      makeItem("planned", "r-4"),
    ];
    render(<RoadmapProgress items={items} />);
    expect(screen.getByTestId("roadmap-completion-rate")).toHaveTextContent(
      "25%",
    );
  });

  it("件数が0件でもエラーにならない", () => {
    render(<RoadmapProgress items={[]} />);
    expect(screen.getByTestId("roadmap-completion-rate")).toHaveTextContent(
      "0%",
    );
  });
});
