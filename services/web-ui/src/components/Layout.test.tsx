import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AppStateContext } from "../state/AppStateContext";
import { Layout } from "./Layout";

function renderLayout(pendingApprovalCount = 0) {
  return render(
    <AppStateContext.Provider
      value={{ pendingApprovalCount, isWsConnected: true, recentActivity: [] }}
    >
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<Layout />}>
            <Route
              path="/dashboard"
              element={<div>ダッシュボードコンテンツ</div>}
            />
            <Route
              path="/approvals"
              element={<div>承認キューコンテンツ</div>}
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </AppStateContext.Provider>,
  );
}

describe("Layout", () => {
  it("共通ナビゲーションと現在のページコンテンツを表示する", () => {
    renderLayout();

    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /ダッシュボード/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /承認キュー/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /ドキュメント/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /活動ログ/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Import-Export/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /エージェント制御/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /コスト/ })).toBeInTheDocument();
    expect(screen.getByText("ダッシュボードコンテンツ")).toBeInTheDocument();
  });

  it("承認キューへのリンク上に未承認件数バッジを表示する", () => {
    renderLayout(4);
    const nav = screen.getByRole("navigation");
    expect(nav).toHaveTextContent("4");
  });
});
