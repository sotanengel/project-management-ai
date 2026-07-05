import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GenericEntityView } from "./GenericEntityView";

describe("GenericEntityView", () => {
  it("キー・値の汎用表示でトップレベルフィールドを表示する", () => {
    render(
      <GenericEntityView
        entity={{
          kind: "stakeholder",
          id: "stakeholder-01",
          name: "山田太郎",
          role: "スポンサー",
          influence: "high",
        }}
      />,
    );

    expect(screen.getByText("name")).toBeInTheDocument();
    expect(screen.getByText("山田太郎")).toBeInTheDocument();
    expect(screen.getByText("role")).toBeInTheDocument();
    expect(screen.getByText("スポンサー")).toBeInTheDocument();
    expect(screen.getByText("influence")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("kind/id/provenance/attachmentsは汎用表と別に見出しで表示する", () => {
    render(
      <GenericEntityView
        entity={{
          kind: "persona",
          id: "persona-01",
          name: "ペルソナA",
        }}
      />,
    );

    expect(screen.getByText(/persona-01/)).toBeInTheDocument();
  });

  it("オブジェクト・配列値はJSON文字列として表示する", () => {
    render(
      <GenericEntityView
        entity={{
          kind: "initiative",
          id: "initiative-01",
          charter: "刷新プロジェクト",
          wbs: [{ id: "wbs-1", name: "設計" }],
        }}
      />,
    );

    expect(screen.getByText(/設計/)).toBeInTheDocument();
  });
});
