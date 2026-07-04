import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ApiError } from "../api/client";
import styles from "./Login.module.css";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({
        email,
        password,
        totp_code: totpCode.length > 0 ? totpCode : null,
      });
      navigate("/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          typeof err.detail === "string" ? err.detail : "認証に失敗しました",
        );
      } else {
        setError("認証に失敗しました");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={styles.container}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <h1>PdM AI 監督UI</h1>
        {error && (
          <p role="alert" className={styles.error}>
            {error}
          </p>
        )}
        <label htmlFor="login-email">メールアドレス</label>
        <input
          id="login-email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <label htmlFor="login-password">パスワード</label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <label htmlFor="login-totp">TOTPコード(任意)</label>
        <input
          id="login-totp"
          type="text"
          inputMode="numeric"
          placeholder="TOTP有効時のみ入力してください"
          value={totpCode}
          onChange={(event) => setTotpCode(event.target.value)}
        />
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "ログイン中..." : "ログイン"}
        </button>
      </form>
    </div>
  );
}
