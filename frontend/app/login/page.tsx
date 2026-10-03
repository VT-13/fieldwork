"use client";
import { useState } from "react";
export default function Login() {
  const [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-symbol" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          fieldwork<span className="brand-period">.</span>
        </div>
        <h1>Good work starts with a real connection.</h1>
        <p>
          Your experience. A useful idea. A thoughtful introduction to the
          people building things near you.
        </p>
        <small>PERSONAL OUTREACH / GREATER SACRAMENTO</small>
      </section>
      <div className="login-form">
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const r = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password }),
              });
              setPassword("");
              if (!r.ok) {
                const data: unknown = await r.json();
                throw Error(
                  data &&
                    typeof data === "object" &&
                    "detail" in data &&
                    typeof data.detail === "string"
                    ? data.detail
                    : "Sign-in failed. Try again.",
                );
              }
              window.location.assign(new URL("/", window.location.origin).href);
            } catch (err) {
              setError(
                err instanceof Error
                  ? err.message
                  : "Sign-in failed. Try again.",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <p className="eyebrow">YOUR PRIVATE WORKSPACE</p>
          <h2>Welcome back.</h2>
          <p>Sign in as the operator of this installation.</p>
          <label>
            Operator password
            <input
              type="password"
              required
              autoComplete="current-password"
              maxLength={1024}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={!!error}
              aria-describedby={error ? "login-error" : undefined}
            />
          </label>
          {error && (
            <p className="alert error" role="alert" id="login-error">
              {error}
            </p>
          )}
          <button disabled={busy} className="primary">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}
