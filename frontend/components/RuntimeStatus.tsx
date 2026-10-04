"use client";
import { useState } from "react";
import { date, decode, request, useResource } from "../lib/api";
import { ErrorState, Status } from "./ui";

export default function RuntimeStatus({
  companyId,
  outreachIds = [],
}: {
  companyId?: string;
  outreachIds?: string[];
}) {
  const runtime = useResource("runtime", "RuntimeView", false, 15000);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  async function reconcile(id: string) {
    setBusy(true);
    setError("");
    try {
      const job = decode(
        "JobView",
        await request(`outreach/${id}/reconcile`, "POST"),
      );
      setNotice(`Sent check · ${job.status}. This check never resends.`);
      await runtime.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not queue Sent check");
    } finally {
      setBusy(false);
    }
  }
  async function requeue(id: string) {
    setBusy(true);
    setError("");
    try {
      const job = decode("JobView", await request(`jobs/${id}/retry`, "POST"));
      setNotice(
        `Eligibility recheck · ${job.status}. Sending still requires current policy.`,
      );
      await runtime.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not requeue work");
    } finally {
      setBusy(false);
    }
  }
  const data = runtime.data;
  const jobs = (data?.communication_jobs || []).filter(
    (j) =>
      !companyId ||
      j.payload.company_id === companyId ||
      outreachIds.includes(String(j.payload.id || "")),
  );
  return (
    <section className="section" aria-label="Communication processing">
      <div className="section-heading">
        <h2>Communication processing</h2>
        <small>Current saved state</small>
      </div>
      <ErrorState error={error || runtime.error} retry={runtime.reload} />
      {notice && <p role="status">{notice}</p>}
      {data && (
        <>
          <p
            className={data.worker === "offline" ? "alert" : "quiet-note"}
            role="status"
          >
            Worker{" "}
            {data.worker === "offline"
              ? "offline · queued work waits for a running worker."
              : `${data.worker} · last seen ${date(data.worker_at || "")}.`}
          </p>
          <p className="quiet-note">
            Recurring outreach {data.recurring_paused ? "paused" : "active"}.{" "}
            {data.sync_stale
              ? "Reply check is stale; fresh preflight is required before sending."
              : "A recent mailbox check is recorded."}{" "}
            {data.unresolved > 0
              ? `${data.unresolved} communication hold(s); further sending is blocked.`
              : "No unresolved communication hold recorded."}
          </p>
          {jobs.map((j) => (
            <article className="history-row" key={j.id}>
              <div>
                <strong>
                  {j.kind === "followup_prepare"
                    ? "Follow-up preparation"
                    : j.kind === "reconcile"
                      ? "Sent confirmation check"
                      : j.kind === "sync"
                        ? "Mailbox check"
                        : "Outreach delivery"}
                </strong>{" "}
                <Status value={j.status} />
                {j.available_at && (
                  <p className="quiet-note">
                    Eligible from {date(j.available_at)}; processing depends on
                    policy and worker availability.
                  </p>
                )}
                {j.error && <p role="status">{j.error}</p>}
                {j.can_retry && (
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => requeue(j.id)}
                  >
                    Recheck queued work
                  </button>
                )}
                {j.kind === "send" &&
                  ["failed", "interrupted", "blocked"].includes(j.status) && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => reconcile(String(j.payload.id || ""))}
                    >
                      Check existing Sent evidence
                    </button>
                  )}
              </div>
            </article>
          ))}
        </>
      )}
    </section>
  );
}
