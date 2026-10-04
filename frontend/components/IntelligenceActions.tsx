"use client";
import { useState } from "react";
import { decode, request, useResource, date } from "../lib/api";
import { ErrorState } from "./ui";
import IntelligenceJobs from "./IntelligenceJobs";
export default function IntelligenceActions({
  id,
  demo,
}: {
  id: string;
  demo: boolean;
}) {
  const caps = useResource("intelligence/capabilities", "CapabilitiesView"),
    history = useResource(
      `companies/${id}/generations`,
      "GenerationView",
      true,
      10000,
    );
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function queue(action: string) {
    setBusy(true);
    setError("");
    try {
      const job = decode(
        "JobView",
        await request(`companies/${id}/actions/${action}`, "POST"),
      );
      setNotice(
        job.status === "queued"
          ? "Queued. A generated message stays unsent and needs review."
          : `Existing ${action} job is ${job.status}. Inspect its saved state below; no email was sent.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not queue work");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="section">
        <div className="section-heading">
          <h2>Build the evidence, then write.</h2>
        </div>
        <p className="muted">
          Research prioritizes the homepage, about, careers and contact pages.
          It stops once enough observations and a suitable contact exist.
        </p>
        <div className="decision-actions">
          <button
            className="secondary"
            disabled={
              busy ||
              demo ||
              !caps.data?.providers.find((p) => p.id === "research")?.available
            }
            onClick={() => queue("research")}
          >
            Queue research
          </button>
          <button
            className="primary"
            disabled={
              busy ||
              demo ||
              !caps.data?.providers.find((p) => p.id === "generate")?.available
            }
            onClick={() => queue("generate")}
          >
            Generate for review
          </button>
        </div>
        {!caps.data?.paid_allowed && (
          <p className="muted">
            Provider work is disabled by current mode/policy. Existing evidence
            and history remain inspectable.
          </p>
        )}
        {notice && (
          <p className="alert" role="status">
            {notice}
          </p>
        )}
        <ErrorState error={error || caps.error} retry={caps.reload} />
      </section>
      <IntelligenceJobs companyId={id} />
      <details className="inline-details">
        <summary>
          Generation history · {history.data?.length || 0} saved versions
        </summary>
        <ErrorState error={history.error} retry={history.reload} />
        {history.data?.map((g) => (
          <article className="section" key={g.id}>
            <p className="eyebrow">
              {date(g.created_at)} · {g.model}
            </p>
            <h3>{g.subject || "Rejected before rendering"}</h3>
            <p className="muted">
              {g.prompt_version} · {g.evidence_ids.length} company observations
              · {g.student_fact_ids.length} student facts
            </p>
            <pre className="generation-body">
              {g.body || "No free-form model claims accepted."}
            </pre>
          </article>
        ))}
      </details>
    </>
  );
}
