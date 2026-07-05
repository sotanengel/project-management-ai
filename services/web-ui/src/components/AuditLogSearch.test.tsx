import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuditLogSearch } from "./AuditLogSearch";

describe("AuditLogSearch", () => {
  it("actor/action/期間を入力して検索するとonSearchが呼ばれる", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<AuditLogSearch onSearch={onSearch} />);

    await user.type(screen.getByLabelText("actor"), "agent:backlog@v1");
    await user.type(screen.getByLabelText("操作種別"), "pmdf.story.create");
    await user.click(screen.getByRole("button", { name: "検索" }));

    expect(onSearch).toHaveBeenCalledWith({
      actor: "agent:backlog@v1",
      action: "pmdf.story.create",
      kind: "",
      dateFrom: "",
      dateTo: "",
    });
  });

  it("初期表示では空条件で検索できる", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<AuditLogSearch onSearch={onSearch} />);

    await user.click(screen.getByRole("button", { name: "検索" }));

    expect(onSearch).toHaveBeenCalledWith({
      actor: "",
      action: "",
      kind: "",
      dateFrom: "",
      dateTo: "",
    });
  });
});
