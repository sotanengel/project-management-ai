import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiChart } from "./KpiChart";
import type { Metric } from "../api/pmdfTypes";

function makeMetric(overrides: Partial<Metric> = {}): Metric {
  return {
    kind: "metric",
    id: "metric-01",
    name: "週次アクティブ率",
    target_value: 0.6,
    threshold_value: 0.4,
    current_value: 0.55,
    time_series: [
      { timestamp: "2026-06-01T00:00:00Z", value: 0.4 },
      { timestamp: "2026-06-08T00:00:00Z", value: 0.48 },
      { timestamp: "2026-06-15T00:00:00Z", value: 0.55 },
    ],
    ...overrides,
  };
}

describe("KpiChart", () => {
  it("KPI名と現在値を表示する", () => {
    render(<KpiChart metric={makeMetric()} />);
    expect(screen.getByText("週次アクティブ率")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-current-value")).toHaveTextContent("0.55");
  });

  it("現在値が未計測(null)の場合は代替表示をする", () => {
    render(<KpiChart metric={makeMetric({ current_value: null })} />);
    expect(screen.getByTestId("kpi-current-value")).toHaveTextContent("未計測");
  });

  it("時系列データが無くてもエラーにならない", () => {
    render(<KpiChart metric={makeMetric({ time_series: [] })} />);
    expect(screen.getByText("週次アクティブ率")).toBeInTheDocument();
  });
});
