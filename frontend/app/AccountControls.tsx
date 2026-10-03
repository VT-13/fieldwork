"use client";
import { useEffect, useState } from "react";
type Connection = { status: string; email: string };
export default function AccountControls() {
  const [connection, setConnection] = useState<Connection>(); const [error, setError] = useState("");
  async function load() { const r = await fetch("/api/integrations/gmail"); if (r.ok) setConnection(await r.json()); }
  useEffect(() => { void load(); }, []);
  async function act(path: string, body?: object) {
    setError(""); try {
      const r = await fetch("/api/" + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      const d = await r.json(); if (!r.ok) throw Error(typeof d.detail === "string" ? d.detail : "Operation failed"); return d;
    } catch (e) { setError(e instanceof Error ? e.message : "Operation failed"); }
  }
  return <section className="panel"><h3>Private account</h3><p>Gmail: {connection?.status || "Checking…"}{connection?.email ? ` · ${connection.email}` : ""}</p><button onClick={async () => { const d = await act("integrations/gmail/connect"); if (d?.url) window.location.assign(d.url); }}>Connect / reconnect Gmail</button> <button onClick={async () => { if (window.confirm("Disconnect Gmail and stop future outreach? Historical send records stay available.")) { await act("integrations/gmail/disconnect", { revoke: true }); await load(); } }}>Disconnect Gmail</button> <button onClick={async () => { const d = await act("auth/logout"); if (d) window.location.assign("/login"); }}>Sign out</button>{error && <p role="alert">{error}</p>}</section>;
}
