import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EntityView } from "./EntityView";
import { PMDF_KINDS } from "../../api/pmdfTypes";

function minimalEntityFor(kind: string): Record<string, unknown> {
  const base = { kind, id: `${kind}-01` };
  switch (kind) {
    case "story":
      return {
        ...base,
        title: "t",
        as_a: "a",
        i_want: "w",
        so_that: "s",
        acceptance_criteria: [],
        priority: { method: "RICE" },
        status: "draft",
      };
    case "decision":
      return {
        ...base,
        background: "b",
        options: [{ name: "opt" }],
        chosen_option: "opt",
        rationale: "r",
        rejected_reasons: [],
        autonomy_level: "L1",
      };
    case "roadmap_item":
      return { ...base, theme: "t", period: "2026-Q1", status: "planned" };
    case "metric":
      return {
        ...base,
        name: "m",
        target_value: 1,
        threshold_value: 0,
        current_value: 0.5,
      };
    case "product":
      return { ...base, name: "p", lifecycle_stage: "growth" };
    case "stakeholder":
      return { ...base, name: "s", role: "r", influence: "high" };
    case "persona":
      return { ...base, name: "p", jobs: [] };
    case "objective":
      return {
        ...base,
        objective: "o",
        key_results: [{ description: "kr", target_value: 1 }],
        period: "2026-Q1",
      };
    case "experiment":
      return {
        ...base,
        hypothesis: "h",
        design: "d",
        success_criteria: [],
        status: "planned",
      };
    case "release":
      return { ...base, name: "r", scope: [], go_no_go: "pending" };
    case "risk":
      return {
        ...base,
        event: "e",
        probability_score: 1,
        impact_score: 1,
        response_strategy: "accept",
        owner: "stakeholder-01",
      };
    case "initiative":
      return { ...base, charter: "c", approach: "hybrid" };
    case "report":
      return {
        ...base,
        period: "2026-Q1",
        health_assessment: "green",
        decisions_needed: [],
      };
    case "approval":
      return {
        ...base,
        target: "x",
        proposer: "p",
        approver: "a",
        decision: "approved",
        reason: "r",
      };
    default:
      return base;
  }
}

describe("EntityView", () => {
  it.each(PMDF_KINDS)("kind=%sを例外なくレンダリングする", (kind) => {
    const entity = minimalEntityFor(kind);
    render(<EntityView entity={entity} />);
    expect(screen.getByTestId("entity-view")).toBeInTheDocument();
  });
});
