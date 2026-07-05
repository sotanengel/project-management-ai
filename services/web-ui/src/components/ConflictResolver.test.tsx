import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BundleDiffEntry } from "../api/client";
import { ConflictResolver } from "./ConflictResolver";

const CONFLICT: BundleDiffEntry = {
  id: "story-01",
  kind: "story",
  diff_type: "conflict",
  field_diffs: {
    title: { current: "既存タイトル", incoming: "取込タイトル" },
  },
  reference_errors: [],
};

describe("ConflictResolver", () => {
  it("conflict種別のエンティティごとに取込側/既存側を選択できる", async () => {
    const handleResolve = vi.fn();
    const user = userEvent.setup();
    render(
      <ConflictResolver
        conflicts={[CONFLICT]}
        resolutions={{}}
        onResolve={handleResolve}
      />,
    );

    expect(screen.getByText(/story-01/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "取込側を採用" }));
    expect(handleResolve).toHaveBeenCalledWith("story-01", "incoming");

    await user.click(screen.getByRole("button", { name: "既存側を維持" }));
    expect(handleResolve).toHaveBeenCalledWith("story-01", "existing");
  });

  it("選択済みの方針を視覚的に示す", () => {
    render(
      <ConflictResolver
        conflicts={[CONFLICT]}
        resolutions={{ "story-01": "incoming" }}
        onResolve={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "取込側を採用" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("手動編集への導線ボタンを提供する", async () => {
    const handleManualEdit = vi.fn();
    const user = userEvent.setup();
    render(
      <ConflictResolver
        conflicts={[CONFLICT]}
        resolutions={{}}
        onResolve={vi.fn()}
        onManualEdit={handleManualEdit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "手動で編集" }));
    expect(handleManualEdit).toHaveBeenCalledWith(CONFLICT);
  });
});
