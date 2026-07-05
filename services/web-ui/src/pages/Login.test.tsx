import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { Login } from "./Login";
import { VALID_EMAIL, VALID_PASSWORD } from "../test/handlers";

function renderLogin() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<div>ダッシュボード画面</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("Login", () => {
  it("正しい入力でログインAPIが呼ばれ、成功後ダッシュボードへ遷移する", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText("メールアドレス"), VALID_EMAIL);
    await user.type(screen.getByLabelText("パスワード"), VALID_PASSWORD);
    await user.click(screen.getByRole("button", { name: "ログイン" }));

    await waitFor(() => {
      expect(screen.getByText("ダッシュボード画面")).toBeInTheDocument();
    });
  });

  it("誤った入力ではエラーメッセージを表示し遷移しない", async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(
      screen.getByLabelText("メールアドレス"),
      "wrong@example.com",
    );
    await user.type(screen.getByLabelText("パスワード"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "ログイン" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("認証に失敗しました");
    });
    expect(screen.queryByText("ダッシュボード画面")).not.toBeInTheDocument();
  });

  it("TOTPコード入力欄は任意項目として表示される", () => {
    renderLogin();
    const totpField = screen.getByLabelText("TOTPコード(任意)");
    expect(totpField).not.toBeRequired();
  });
});
