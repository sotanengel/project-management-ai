import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EvidencePanel } from "./EvidencePanel";

function renderPanel(evidence: Array<Record<string, unknown>>) {
  return render(
    <MemoryRouter>
      <EvidencePanel evidence={evidence} />
    </MemoryRouter>,
  );
}

describe("EvidencePanel", () => {
  it("KB出典の根拠を抜粋付きで表示する", () => {
    renderPanel([
      {
        source: "kb",
        domain: "discovery",
        framework: "JTBD",
        excerpt: "顧客インタビューでは...",
      },
    ]);

    expect(screen.getByText(/KB出典/)).toBeInTheDocument();
    expect(screen.getByText("discovery")).toBeInTheDocument();
    expect(screen.getByText("顧客インタビューでは...")).toBeInTheDocument();
  });

  it("PMDF参照の根拠をリンク付きで表示する", () => {
    renderPanel([{ source: "pmdf", kind: "story", id: "story-01" }]);

    expect(screen.getByText(/PMDF参照/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /story-01/ })).toHaveAttribute(
      "href",
      "/documents/story/story-01",
    );
  });

  it("データ根拠を説明付きで表示する", () => {
    renderPanel([
      {
        source: "data",
        description: "RICEスコア計算の入力値",
        data: { reach: 100 },
      },
    ]);

    expect(screen.getByText(/データ根拠/)).toBeInTheDocument();
    expect(screen.getByText("RICEスコア計算の入力値")).toBeInTheDocument();
  });

  it("根拠が無い場合はその旨を表示する", () => {
    renderPanel([]);

    expect(screen.getByText("根拠情報がありません")).toBeInTheDocument();
  });
});
