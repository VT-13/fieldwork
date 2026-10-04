"use client";
import { useState } from "react";
import { request, useResource } from "../lib/api";
import { ErrorState, Status, Empty } from "./ui";
function count(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? String(value)
    : "unknown";
}
export default function IntelligenceJobs({
  companyId,
}: {
  companyId?: string;
}) {
  const jobs = useResource("jobs", "JobView", true, 10000);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const visible = (jobs.data || [])
    .filter(
      (j) =>
        [
          "discover",
          "candidate_import",
          "research",
          "pipeline",
          "generate",
          "regenerate",
          "verify",
        ].includes(j.kind) &&
        (!companyId || j.payload.id === companyId),
    )
    .slice(0, 12);
  async function act(id: string, action: string) {
    setBusy(true);
    setError("");
    try {
      await request(`jobs/${id}/${action}`, "POST");
      await jobs.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update work");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="section">
      <div className="section-heading">
        <h2>Research queue</h2>
        <small>Actual saved job state</small>
      </div>
      <ErrorState error={error || jobs.error} retry={jobs.reload} />
      {!visible.length ? (
        <Empty title="No intelligence work queued">
          Work starts only when you queue it. A running worker is required.
        </Empty>
      ) : (
        visible.map((j) => (
          <article className="intelligence-job" key={j.id}>
            <div>
              <strong>{j.kind.replaceAll("_", " ")}</strong>{" "}
              <Status value={j.status} />
              <p className="muted">
                {j.result.facts !== undefined
                  ? `${count(j.result.facts)} observations · `
                  : ""}
                {j.result.pages !== undefined
                  ? `${count(j.result.pages)} pages · `
                  : ""}
                {j.result.provider_requests !== undefined
                  ? `${count(j.result.provider_requests)} provider requests`
                  : "No provider counts recorded yet"}
              </p>
              {j.error && <p role="status">{j.error}</p>}
            </div>
            {["queued", "running"].includes(j.status) ? (
              <button
                className="secondary"
                disabled={busy}
                onClick={() => act(j.id, "stop")}
              >
                Stop {j.kind.replaceAll("_", " ")}
              </button>
            ) : ["failed", "blocked"].includes(j.status) &&
              !j.payload.stop_requested ? (
              <button
                className="text-button"
                disabled={busy}
                onClick={() => act(j.id, "retry")}
              >
                Explicit retry
              </button>
            ) : null}
          </article>
        ))
      )}
    </section>
  );
}
