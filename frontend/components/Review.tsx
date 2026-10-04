"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Check, ArrowRight, Save, ShieldCheck } from "lucide-react";
import type { CompanyView, OutreachView, ProfileInput } from "../lib/contracts";
import { date, request, useResource } from "../lib/api";
import { useUnsavedChanges } from "../lib/unsaved";
import { Empty, ErrorState, External, Header, Loading, Status } from "./ui";
type Messages = {
  data?: OutreachView[];
  error?: string;
  loading: boolean;
  reload: () => Promise<void>;
};
export default function Review({
  companies,
  messages,
  profile,
  refresh,
}: {
  companies: CompanyView[];
  messages: Messages;
  profile?: ProfileInput;
  refresh: () => Promise<void>;
}) {
  const params = useSearchParams(),
    selected = params.get("message");
  const rows = messages.data || [],
    active =
      rows.find((m) => m.id === selected) ||
      rows.find((m) => m.status === "draft") ||
      rows[0];
  return (
    <>
      <Header
        eyebrow="03 / A REASON TO REACH OUT"
        title="Every word should earn its place."
      >
        Read the message against its sources. Be specific, useful, and yourself.
      </Header>
      <ErrorState error={messages.error} retry={messages.reload} />
      {messages.loading && !messages.data ? (
        <Loading />
      ) : !active ? (
        <Empty title="No outreach is ready for review">
          Start with a researched prospect. Your practice desk is also available
          for writing and test copies to yourself.
          <Link className="text-button" href="/?view=desk">
            Open practice desk
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        </Empty>
      ) : (
        <div className="review-workspace">
          <aside className="review-queue">
            <p className="eyebrow">MESSAGE QUEUE / {rows.length}</p>
            <nav aria-label="Messages to inspect">
              {rows.slice(0, 100).map((m) => (
                <Link
                  key={m.id}
                  href={`/?view=review&message=${m.id}`}
                  aria-current={active.id === m.id ? "page" : undefined}
                  className={active.id === m.id ? "selected" : ""}
                >
                  <strong>
                    {companies.find((c) => c.id === m.company_id)?.name ||
                      "Company record"}
                  </strong>
                  <span>{m.subject}</span>
                  <Status value={m.status} />
                </Link>
              ))}
            </nav>
          </aside>
          <MessageEditor
            key={active.id}
            message={active}
            profile={profile}
            refresh={refresh}
          />
        </div>
      )}
    </>
  );
}
function MessageEditor({
  message: m,
  profile,
  refresh,
}: {
  message: OutreachView;
  profile?: ProfileInput;
  refresh: () => Promise<void>;
}) {
  const company = useResource(`companies/${m.company_id}`, "CompanyDetail"),
    capabilities = useResource("intelligence/capabilities", "CapabilitiesView");
  const [subject, setSubject] = useState(m.subject),
    [body, setBody] = useState(m.body),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const dirty = subject !== m.subject || body !== m.body;
  const editor = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const element = editor.current;
    if (!element) return;
    let width = 0;
    let frame = 0;
    const resize = () => {
      element.style.height = "auto";
      element.style.height = element.scrollHeight + "px";
    };
    resize();
    const observer = new ResizeObserver((entries) => {
      const nextWidth = entries[0].contentRect.width;
      if (nextWidth !== width) {
        width = nextWidth;
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(resize);
      }
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [body]);
  useUnsavedChanges(dirty);
  const editable =
    ["draft", "approved", "rejected"].includes(m.status) && m.attempts === 0;
  const ct = company.data?.contacts.find((c) => c.id === m.contact_id);
  const evidence =
    company.data?.evidence.filter((e) => m.evidence_ids.includes(e.id)) || [];
  async function act(path: string, method = "POST", data?: unknown) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await request(path, method, data);
      await refresh();
      setNotice(
        method === "PATCH"
          ? "Edits saved. Prior approval is cleared; quality review must run again before approval."
          : path.endsWith("regenerate")
            ? "Regeneration queued as a new version. The current message remains until it completes; no email was sent."
            : "Review state updated. No email was sent.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update message");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="review-detail">
      <div className="review-heading">
        <div>
          <p className="eyebrow">
            {m.sequence ? `FOLLOW-UP ${m.sequence}` : "FIRST INTRODUCTION"}
          </p>
          <h2>{company.data?.name || "Loading company…"}</h2>
          <p>
            {ct
              ? `${ct.name || "Name unverified"} · ${ct.title || "Role unrecorded"}`
              : "Recipient details not loaded"}
          </p>
        </div>
        <Status value={m.status} />
      </div>
      <ErrorState error={error} />
      {notice && (
        <p className="alert" role="status">
          {notice}
        </p>
      )}
      {m.status === "unknown" && (
        <div className="delivery-hold" role="alert">
          <strong>Delivery is uncertain. Do not resend.</strong>
          <p>
            Inspect the recorded provider receipt and Gmail thread.
            Reconciliation must resolve this attempt before another action.
          </p>
        </div>
      )}
      <section className="quality-review" aria-label="Review decision">
        <div>
          <p className="eyebrow">REVIEW / SAVED VERSION</p>
          <h3>
            {m.review.personalization_score === null
              ? "Quality review not completed"
              : `${m.review.personalization_score} / 100 personalization`}
          </h3>
          <p>
            {m.review.passed
              ? "Quality checks passed for the saved version. Still read every claim and recipient yourself."
              : "This version cannot be approved until the server quality check passes."}
          </p>
          {m.review.autopilot_blocked_reason && (
            <p role="status">
              Automatic approval held: {m.review.autopilot_blocked_reason}
            </p>
          )}
          {m.review.issues.map((issue, i) => (
            <p className="review-issue" key={`${i}-${issue}`}>
              {issue}
            </p>
          ))}
        </div>
        <div className="review-actions">
          {dirty && editable && (
            <button
              className="secondary"
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    "Discard local text and load the current saved version?",
                  )
                ) {
                  setSubject(m.subject);
                  setBody(m.body);
                }
              }}
            >
              Load current saved version
            </button>
          )}
          {editable && (
            <>
              <button
                className="secondary"
                disabled={
                  busy ||
                  dirty ||
                  company.data?.demo ||
                  !capabilities.data?.providers.find((p) => p.id === "generate")
                    ?.available
                }
                onClick={() => act(`outreach/${m.id}/regenerate`)}
              >
                Regenerate for review
              </button>
              <button
                className="primary"
                disabled={
                  busy ||
                  dirty ||
                  m.status !== "draft" ||
                  !m.review.passed ||
                  !profile?.verified
                }
                onClick={() => act(`outreach/${m.id}/approve`)}
              >
                <Check size={16} aria-hidden="true" />
                Approve saved draft
              </button>
              {m.status !== "rejected" && (
                <button
                  className="secondary"
                  disabled={busy || dirty}
                  onClick={() => act(`outreach/${m.id}/review/reject`)}
                >
                  Return for changes
                </button>
              )}
              {m.status !== "draft" && (
                <button
                  className="secondary"
                  disabled={busy || dirty}
                  onClick={() => act(`outreach/${m.id}/review/draft`)}
                >
                  Return to draft
                </button>
              )}
            </>
          )}
          {!editable && (
            <p className="muted">
              This delivery record is locked. Exact sent content is preserved.
            </p>
          )}
        </div>
      </section>
      <div className="composer-layout">
        <form
          className="email-paper"
          onSubmit={(e) => {
            e.preventDefault();
            void act(`outreach/${m.id}`, "PATCH", { subject, body });
          }}
        >
          <div className="email-envelope">
            <span>TO</span>
            <strong>{ct?.email || "Recipient not available"}</strong>
            <span>{ct ? ct.validation : "Verification unknown"}</span>
          </div>
          <label className="email-subject">
            Subject
            <input
              required
              maxLength={180}
              value={subject}
              readOnly={!editable}
              onChange={(e) => setSubject(e.target.value)}
            />
          </label>
          <label className="sr-only" htmlFor="outreach-body">
            Email body
          </label>
          <textarea
            ref={editor}
            id="outreach-body"
            className="email-content"
            required
            maxLength={8000}
            value={body}
            readOnly={!editable}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="email-footer">
            <span>{body.trim().split(/\s+/).filter(Boolean).length} words</span>
            <span>
              {dirty ? "Unsaved edits" : "Saved version"} · {date(m.created_at)}
            </span>
          </div>
          {editable && (
            <div className="composer-actions">
              <button className="secondary" disabled={busy || !dirty}>
                <Save size={15} aria-hidden="true" />
                {busy ? "Saving…" : "Save edits"}
              </button>
              <span>Saving clears the previous quality review.</span>
            </div>
          )}
        </form>
        <aside className="review-evidence">
          <section>
            <p className="eyebrow">COMPANY EVIDENCE</p>
            <ErrorState error={company.error} retry={company.reload} />
            {company.loading && !company.data ? (
              <Loading />
            ) : evidence.length ? (
              evidence.map((e, i) => (
                <article key={e.id}>
                  <span className="evidence-number">0{i + 1}</span>
                  <h3>{e.fact}</h3>
                  <blockquote>{e.quote}</blockquote>
                  <External href={e.url}>
                    Source · {date(e.fetched_at)}
                  </External>
                </article>
              ))
            ) : (
              <p className="evidence-missing">
                No matching source evidence is recorded for this message. Verify
                its claims before approval.
              </p>
            )}
            <Link
              className="text-button"
              href={`/?view=prospects&company=${m.company_id}`}
            >
              Full prospect context
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </section>
          <section>
            <p className="eyebrow">YOUR EXPERIENCE</p>
            <Status value={profile?.verified ? "verified" : "unverified"} />
            {profile ? (
              <ul className="experience-list">
                {[...profile.projects, ...profile.awards]
                  .slice(0, 5)
                  .map((p, i) => (
                    <li key={`${i}-${p}`}>{p}</li>
                  ))}
              </ul>
            ) : (
              <p>Profile unavailable. Check it before approving.</p>
            )}
            <Link className="text-button" href="/?view=profile">
              Check profile
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </section>
        </aside>
      </div>

      <p className="quiet-note">
        <ShieldCheck size={15} aria-hidden="true" />
        Review does not send an email or resume outreach. Edited text needs a
        fresh server quality check; regeneration is available through the
        existing worker when enabled.
      </p>
      <details className="inline-details">
        <summary>Delivery record & reference headers</summary>
        <dl className="context-ledger">
          <dt>Attempts</dt>
          <dd>{m.attempts}</dd>
          <dt>Provider receipt</dt>
          <dd>{m.provider_id || "No receipt recorded"}</dd>
          <dt>Thread</dt>
          <dd>{m.thread_id || "No thread recorded"}</dd>
          <dt>Message ID</dt>
          <dd>{m.message_id || "Not recorded"}</dd>
          <dt>Sent timestamp</dt>
          <dd>{m.sent_at || "Not sent"}</dd>
        </dl>
      </details>
    </div>
  );
}
