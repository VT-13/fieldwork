"use client";
import { useState } from "react";
export default function Login() {
  const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  return <main className="content"><form className="panel" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const r = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }) });
      setPassword(""); if (!r.ok) { const d = await r.json(); throw Error(typeof d.detail === "string" ? d.detail : "Sign-in failed"); }
      window.location.assign("/");
    } catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed"); } finally { setBusy(false); }
  }}><h1>Fieldwork</h1><p>Sign in to your private workspace.</p><label>Operator password<input type="password" required autoComplete="current-password" maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} /></label><button disabled={busy} className="primary">{busy ? "Signing in…" : "Sign in"}</button>{error && <p role="alert">{error}</p>}</form></main>;
}
