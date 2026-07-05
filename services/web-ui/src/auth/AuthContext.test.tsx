import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useContext } from "react";
import { AuthContext, AuthProvider } from "./AuthContext";
import { VALID_EMAIL, VALID_PASSWORD } from "../test/handlers";

function AuthProbe() {
  const auth = useContext(AuthContext);
  if (!auth) {
    throw new Error("AuthContextが提供されていません");
  }
  return (
    <div>
      <span data-testid="token">{auth.token ?? "no-token"}</span>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <button
        onClick={() => {
          void auth.login({ email: VALID_EMAIL, password: VALID_PASSWORD });
        }}
      >
        login-success
      </button>
      <button
        onClick={() => {
          void auth
            .login({ email: "wrong@example.com", password: "wrong" })
            .catch(() => undefined);
        }}
      >
        login-fail
      </button>
      <button onClick={() => auth.logout()}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  it("ログイン成功時にJWTを保持しisAuthenticatedがtrueになる", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");

    await user.click(screen.getByText("login-success"));

    await waitFor(() => {
      expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("token")).toHaveTextContent("test.jwt.token");
  });

  it("ログイン失敗時はトークンを保持しない", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await user.click(screen.getByText("login-fail"));

    await waitFor(() => {
      expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    });
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
  });

  it("logout呼び出しでトークンが破棄される", async () => {
    const user = userEvent.setup();
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await user.click(screen.getByText("login-success"));
    await waitFor(() => {
      expect(screen.getByTestId("authenticated")).toHaveTextContent("true");
    });

    await user.click(screen.getByText("logout"));
    expect(screen.getByTestId("authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("token")).toHaveTextContent("no-token");
  });
});
