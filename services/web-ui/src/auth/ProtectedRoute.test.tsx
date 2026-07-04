import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { AuthProvider } from "./AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";
import { useAuth } from "./useAuth";
import { VALID_EMAIL, VALID_PASSWORD } from "../test/handlers";

function LoginStub() {
  const { login } = useAuth();
  const navigate = useNavigate();
  return (
    <button
      onClick={async () => {
        await login({ email: VALID_EMAIL, password: VALID_PASSWORD });
        navigate("/dashboard");
      }}
    >
      do-login
    </button>
  );
}

function renderApp() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/login" element={<LoginStub />} />
          <Route element={<ProtectedRoute />}>
            <Route
              path="/dashboard"
              element={<div>保護されたダッシュボード</div>}
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("ProtectedRoute", () => {
  it("未認証の場合はログイン画面へリダイレクトされる", () => {
    renderApp();
    expect(screen.getByText("do-login")).toBeInTheDocument();
    expect(
      screen.queryByText("保護されたダッシュボード"),
    ).not.toBeInTheDocument();
  });

  it("認証済みの場合は保護されたコンテンツを表示する", async () => {
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByText("do-login"));

    await waitFor(() => {
      expect(screen.getByText("保護されたダッシュボード")).toBeInTheDocument();
    });
  });
});
