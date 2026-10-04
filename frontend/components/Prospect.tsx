"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, ArrowRight, MapPin } from "lucide-react";
import type {
  CampaignView,
  OutreachView,
  CompanyDetail,
} from "../lib/contracts";
import { useResource, date, request, text } from "../lib/api";
import { Empty, ErrorState, External, Header, Loading, Status } from "./ui";
import IntelligenceActions from "./IntelligenceActions";
export default function Prospect({
  id,
  messages,
  campaign,
  refresh,
}: {
  id: string;
  messages: OutreachView[];
  campaign?: CampaignView;
  refresh: () => Promise<void>;
}) {
  const detail = useResource(`companies/${id}`, "CompanyDetail"),
    inbox = useResource("responses", "InboxView");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const c = detail.data,
    history = messages.filter((m) => m.company_id === id),
    replies = inbox.data?.responses.filter((r) => r.company_id === id) || [];
  async function act(path: string, body?: unknown) {
    setBusy(true);
    setError("");
    try {
      await request(path, "POST", body);
      await Promise.all([detail.reload(), refresh()]);
      setNotice("Saved. The record has been updated.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update prospect");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" href="/?view=prospects">
        <ArrowLeft size={15} aria-hidden="true" />
        Back to prospects
      </Link>
      <ErrorState error={detail.error || error} retry={detail.reload} />
      {notice && (
        <p className="alert" role="status">
          {notice}
        </p>
      )}
      {!c ? (
        detail.loading ? (
          <Loading label="Loading prospect and evidence" />
        ) : null
      ) : (
        <>
          <Header
            eyebrow={`${c.industry.toUpperCase()} / PROSPECT`}
            title={c.name}
            action={<External href={c.website}>Company website</External>}
          >
            {c.description ||
              "Description not researched yet. Verify what this team does before drafting."}
          </Header>
          <div className="prospect-meta">
            <Status value={c.stage} />
            <span>
              <MapPin size={14} aria-hidden="true" />
              {c.distance_miles === null
                ? "Distance unverified"
                : `${c.distance_miles} miles from your search area`}
            </span>
            <span>Source: {c.source}</span>
            {c.demo && <Status value="demo" />}
          </div>
          <div className="prospect-detail-layout">
            <div>
              <section className="section">
                <div className="section-heading">
                  <h2>The person to reach</h2>
                  <small>Public business contacts</small>
                </div>
                {c.contacts.length ? (
                  c.contacts.map((ct) => (
                    <article className="contact-row" key={ct.id}>
                      <div>
                        <h3>{ct.name || "Name not verified"}</h3>
                        <p>{ct.title || "Role not recorded"}</p>
                        <span className="contact-address">{ct.email}</span>
                      </div>
                      <div>
                        <span className="status">{ct.confidence}</span>
                        <small>Checked {date(ct.validated_at)}</small>
                        <small>Source: {ct.source || "Not recorded"}</small>
                        <details className="inline-details">
                          <summary>Role / identity observations</summary>
                          {ct.observations.map((o) => (
                            <p key={o.id}>
                              {o.field}: {o.value} · {o.confidence} ·{" "}
                              {date(o.retrieved_at)}{" "}
                              {o.source_url && (
                                <External href={o.source_url}>Source</External>
                              )}
                            </p>
                          ))}
                        </details>
                      </div>
                    </article>
                  ))
                ) : (
                  <Empty title="No verified contact yet">
                    A role or email must come from a real source before outreach
                    can proceed.
                  </Empty>
                )}
                <details className="inline-details">
                  <summary>Add a sourced contact</summary>
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      const form = e.currentTarget;
                      const data = new FormData(form);
                      await act(`companies/${id}/contacts`, {
                        name: data.get("name"),
                        title: data.get("title"),
                        email: data.get("email"),
                        source: data.get("source"),
                      });
                    }}
                  >
                    <div className="form-grid">
                      <label>
                        Name
                        <input name="name" maxLength={255} />
                      </label>
                      <label>
                        Role
                        <input name="title" maxLength={255} />
                      </label>
                    </div>
                    <label>
                      Business email
                      <input name="email" type="email" required />
                    </label>
                    <label>
                      Public source URL or citation
                      <input name="source" required />
                    </label>
                    <button className="secondary" disabled={busy}>
                      Save contact · unverified
                    </button>
                  </form>
                </details>
              </section>
              <div className="mobile-relevance">
                <FitContext company={c} />
              </div>
              <section className="section">
                <div className="section-heading">
                  <h2>Evidence behind the introduction</h2>
                  <span>{c.evidence.length} sources</span>
                </div>
                {c.evidence.length ? (
                  c.evidence.map((e, index) => (
                    <article className="evidence-row" key={e.id}>
                      <div className="evidence-number">
                        {String(index + 1).padStart(2, "0")}
                      </div>
                      <div>
                        <p className="eyebrow">
                          {e.category} / COLLECTED {date(e.fetched_at)} ·{" "}
                          {e.source_kind} · {e.confidence} ·{" "}
                          {e.fresh ? "current" : "stale / unverified"}
                        </p>
                        <h3>{e.fact}</h3>
                        <blockquote>{e.quote}</blockquote>
                        <External href={e.url}>View primary source</External>
                      </div>
                    </article>
                  ))
                ) : (
                  <Empty title="The evidence is still missing">
                    Research should capture a specific observation and its
                    source. Unknown facts stay unknown.
                  </Empty>
                )}
              </section>
              <IntelligenceActions id={id} demo={c.demo} />
              <section className="section">
                <div className="section-heading">
                  <h2>Communication history</h2>
                </div>
                {history.length ? (
                  history.map((m) => (
                    <article className="history-row" key={m.id}>
                      <span className="timeline-dot" aria-hidden="true" />
                      <div>
                        <Status value={m.status} />
                        <h3>{m.subject}</h3>
                        <p>
                          {m.sequence
                            ? `Follow-up ${m.sequence}`
                            : "Initial introduction"}{" "}
                          · {date(m.sent_at || m.created_at)}
                        </p>
                        <Link
                          className="text-button"
                          href={`/?view=review&message=${m.id}`}
                        >
                          Inspect exact message
                          <ArrowRight size={14} aria-hidden="true" />
                        </Link>
                      </div>
                    </article>
                  ))
                ) : (
                  <p className="muted">
                    No outreach has been recorded for this company.
                  </p>
                )}
                <ErrorState error={inbox.error} retry={inbox.reload} />
                {replies.map((r) => (
                  <article className="history-row" key={r.id}>
                    <span className="timeline-dot" aria-hidden="true" />
                    <div>
                      <Status value={r.kind} />
                      <h3>{r.subject}</h3>
                      <p>{r.preview}</p>
                      <External href={r.gmail_url}>
                        Open conversation in Gmail
                      </External>
                    </div>
                  </article>
                ))}
              </section>
              <section className="section">
                <div className="section-heading">
                  <h2>Notes & outcomes</h2>
                </div>
                {c.events.map((e) => (
                  <div className="event-row" key={e.id}>
                    <Status value={e.kind} />
                    <p>{e.detail || "Outcome recorded"}</p>
                    <small>{date(e.created_at)}</small>
                  </div>
                ))}
                <form
                  className="outcome-form"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    await act(`companies/${id}/events`, {
                      kind: data.get("kind"),
                      detail: data.get("detail"),
                    });
                  }}
                >
                  <label>
                    Outcome
                    <select name="kind">
                      <option value="reply">Reply received</option>
                      <option value="positive">Positive response</option>
                      <option value="interview">Interview</option>
                      <option value="offer">Internship offer</option>
                      <option value="negative">Declined</option>
                      <option value="closed">Closed</option>
                    </select>
                  </label>
                  <label>
                    Context / note
                    <textarea
                      name="detail"
                      rows={3}
                      maxLength={2000}
                      placeholder="What happened, and what is the next step?"
                    />
                  </label>
                  <p className="muted">
                    Recording a response or outcome stops pending automated
                    outreach for this company.
                  </p>
                  <button className="secondary" disabled={busy}>
                    Record outcome
                  </button>
                </form>
              </section>
            </div>
            <aside className="prospect-context">
              <div className="desktop-relevance">
                <FitContext company={c} />
              </div>
              <section>
                <p className="eyebrow">RESEARCH CONTEXT</p>
                <p className="muted">
                  Reported research notes. Check their supporting sources before
                  using these details in an email.
                </p>
                <dl className="context-ledger">
                  <dt>Founder</dt>
                  <dd>{text(c.research.founder) || "Not verified"}</dd>
                  <dt>Company size</dt>
                  <dd>{text(c.research.size) || "Not verified"}</dd>
                  <dt>Internship history</dt>
                  <dd>
                    {text(c.research.internship_history) || "Not verified"}
                  </dd>
                </dl>
                {text(c.research.careers_url) && (
                  <External href={text(c.research.careers_url)}>
                    Careers page
                  </External>
                )}
              </section>
              <section>
                <p className="eyebrow">NEXT STEP</p>
                <p>
                  {history.length
                    ? "Read the current message and any response before choosing another action."
                    : c.evidence.length
                      ? "Match a sourced company observation to your actual experience."
                      : "Research the homepage, team and contact details before writing."}
                </p>
                <Link
                  className="primary"
                  href={`/?view=review${history[0] ? `&message=${history[0].id}` : ""}`}
                >
                  Open outreach review
                  <ArrowRight size={15} aria-hidden="true" />
                </Link>
                <p className="muted">
                  Recurring outreach:{" "}
                  {campaign
                    ? campaign.ongoing_policy.enabled
                      ? "enabled"
                      : "paused"
                    : "status unavailable"}
                  .{" "}
                  {campaign?.outreach_ids.some((outreachId) =>
                    history.some((m) => m.id === outreachId),
                  )
                    ? "This prospect has a message in the current scoped batch."
                    : "No current scoped batch membership is recorded."}
                </p>
              </section>
            </aside>
          </div>
        </>
      )}
    </>
  );
}

function FitContext({ company }: { company: CompanyDetail }) {
  return (
    <section aria-label="Company relevance">
      <p className="eyebrow">WHY THIS TEAM</p>
      <div className="detail-score">
        <strong>{company.score}</strong>
        <span>fit / 100</span>
      </div>
      <p>Fit is a research priority, not a hiring prediction.</p>
      {Object.keys(company.score_factors).length ? (
        <dl className="factor-ledger">
          {Object.entries(company.score_factors).map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="muted">No fit factors recorded.</p>
      )}
      <p className="muted">
        Research updated {date(company.researched_at)}. Evidence is dated below;
        freshness requires a new source check.
      </p>
    </section>
  );
}
