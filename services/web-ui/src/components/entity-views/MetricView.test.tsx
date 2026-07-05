import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricView } from "./MetricView";
import type { Metric } from "../../api/pmdfTypes";

const METRIC: Metric = {
  kind: "metric",
  id: "metric-01",
  name: "週次アクティブ率",
  target_value: 0.6,
  threshold_value: 0.4,
  current_value: 0.5,
  time_series: [{ timestamp: "2026-06-01T00:00:00Z", value: 0.5 }],
};

describe("MetricView", () => {
  it("目標値・閾値・現在値を表示する", () => {
    render(<MetricView entity={METRIC} />);

    expect(screen.getByText("週次アクティブ率")).toBeInTheDocument();
    expect(screen.getByText("0.6")).toBeInTheDocument();
    expect(screen.getByText("0.4")).toBeInTheDocument();
    expect(screen.getByText("0.5")).toBeInTheDocument();
  });
});
