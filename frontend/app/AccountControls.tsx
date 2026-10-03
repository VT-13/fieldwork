"use client";
import { useState } from "react";
import { request, useResource } from "../lib/api";
import { Dialog, ErrorState, Status } from "../components/ui";
export default function AccountControls() {
  const connection = useResource("integrations/gmail", "ConnectionView");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [confirm, setConfirm] = useState(false);
  async function act(path: string, body?: object) {
    setBusy(true);
    setError("");
    try {
      const data = await request(path, "POST", body || {});
      if (
        path.endsWith("connect") &&
        !path.endsWith("disconnect") &&
        data &&
        typeof data === "object" &&
        "url" in data &&
        typeof data.url === "string"
      ) {
        const url = new URL(data.url);
        if (url.origin !== "https://accounts.google.com")
          throw Error("Unexpected authorization destination");
        window.location.assign(url.href);
      } else if (path === "auth/logout")
        window.location.assign(new URL("/login", window.location.origin).href);
      else {
        await connection.reload();
        setConfirm(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Account action failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="account-controls">
      <div className="section-heading">
        <div>
          <h2>Your Gmail connection</h2>
          <p>
            {connection.data?.email || "No connected mailbox identity recorded"}
          </p>
        </div>
        <Status value={connection.data?.status || "checking"} />
      </div>
      <ErrorState error={connection.error || error} retry={connection.reload} />
      <p className="muted">
        Connect opens Google’s authorization screen. Disconnect removes local
        credentials and pauses future company outreach; historical receipts
        remain.
      </p>
      <div className="buttons">
        <button
          className="primary"
          disabled={busy}
          onClick={() => act("integrations/gmail/connect")}
        >
          {busy
            ? "Working…"
            : connection.data?.connected
              ? "Reconnect Gmail"
              : "Connect Gmail"}
        </button>
        <button
          className="secondary"
          disabled={busy || !connection.data?.connected}
          onClick={() => setConfirm(true)}
        >
          Disconnect Gmail
        </button>
        <button
          className="text-button"
          disabled={busy}
          onClick={() => act("auth/logout")}
        >
          Sign out
        </button>
      </div>
      {confirm && (
        <Dialog title="Disconnect your Gmail?" close={() => setConfirm(false)}>
          <p>
            This stops future outreach and removes local Gmail credentials. Your
            historical send records remain available.
          </p>
          <ErrorState error={error} />
          <div className="buttons">
            <button
              className="danger-button"
              disabled={busy}
              onClick={() =>
                act("integrations/gmail/disconnect", { revoke: true })
              }
            >
              {busy ? "Disconnecting…" : "Disconnect and pause"}
            </button>
            <button className="secondary" onClick={() => setConfirm(false)}>
              Keep connected
            </button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
