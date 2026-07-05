import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DecisionView } from "./DecisionView";
import type { Decision } from "../../api/pmdfTypes";

const DECISION: Decision = {
  kind: "decision",
  id: "dec-01",
  background: "検索基盤の刷新が必要になった",
  options: [
    { name: "Elasticsearch導入", pros: ["高速"], cons: ["運用コスト増"] },
    { name: "現状維持", pros: ["コスト低"], cons: ["性能不足"] },
  ],
  chosen_option: "Elasticsearch導入",
  rationale: "性能要件を満たせるため",
  rejected_reasons: [{ option: "現状維持", reason: "性能不足のため却下" }],
  autonomy_level: "L1",
};

describe("DecisionView", () => {
  it("背景・選択肢・採用案・根拠・却下理由を表示する", () => {
    render(<DecisionView entity={DECISION} />);

    expect(
      screen.getByText("検索基盤の刷新が必要になった"),
    ).toBeInTheDocument();
    expect(screen.getByText("性能要件を満たせるため")).toBeInTheDocument();
    expect(screen.getAllByText("Elasticsearch導入").length).toBeGreaterThan(0);
    expect(screen.getByText("性能不足のため却下")).toBeInTheDocument();
  });
});
