"use client";
import { useState } from "react";
import { RefreshCw } from "lucide-react";
import { useResource, request, date } from "../lib/api";
import { Empty, ErrorState, External, Loading, Status } from "../components/ui";
export default function ResponseInbox() {
  const inbox = useResource("responses", "InboxView", false, 30000);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function action(path: string, method: string, body?: unknown) {
    setBusy(true);
    setError("");
    try {
      await request(path, method, body);
      await inbox.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reply update failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="response-inbox">
      <div className="section-heading">
        <div>
          <h2>
            {inbox.data ? inbox.data.needs_attention : "…"} replies need your
            attention
          </h2>
          <p>
            {inbox.data?.sync.last_success
              ? `Gmail last checked ${date(inbox.data.sync.last_success)}`
              : "No completed inbox check recorded."}{" "}
            {inbox.data?.enabled
              ? "Server polling is enabled while it runs."
              : "Automatic checking is disabled."}
          </p>
        </div>
        <button
          className="secondary"
          disabled={busy || inbox.data?.sync.status === "syncing"}
          onClick={() => action("responses/sync", "POST")}
        >
          <RefreshCw size={15} aria-hidden="true" />
          {busy || inbox.data?.sync.status === "syncing"
            ? "Checking Gmail…"
            : "Check Gmail"}
        </button>
      </div>
      <ErrorState
        error={error || inbox.error || inbox.data?.sync.error || undefined}
        retry={inbox.reload}
      />
      {inbox.loading && !inbox.data ? (
        <Loading />
      ) : (
        inbox.data && (
          <>
            {inbox.data.responses.length ? (
              inbox.data.responses.map((r) => (
                <article key={r.id} className="response-row">
                  <div className="section-heading">
                    <div>
                      <h3>{r.company}</h3>
                      <small>
                        {r.sender} · {date(r.received_at)}
                      </small>
                    </div>
                    <Status value={r.kind} />
                  </div>
                  <h4>{r.subject}</h4>
                  <p className="reply-preview">{r.preview}</p>
                  <div className="buttons">
                    <External href={r.gmail_url}>Open in Gmail</External>
                    {r.kind === "reply" && (
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          action(`responses/${r.id}`, "PUT", {
                            handled: !r.handled,
                          })
                        }
                      >
                        {r.handled ? "Mark needing attention" : "Mark handled"}
                      </button>
                    )}
                  </div>
                </article>
              ))
            ) : (
              <Empty title="No responses have been recorded">
                Check your connected mailbox to pull in replies, delivery
                updates and acknowledgments.
              </Empty>
            )}
            <p className="quiet-note">
              Handling a reply here does not mark it read in Gmail. Replies stop
              follow-ups; acknowledgments remain held. This app never replies
              for you.
            </p>
          </>
        )
      )}
    </section>
  );
}
