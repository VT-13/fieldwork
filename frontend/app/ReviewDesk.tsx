"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Plus,
  Check,
  Copy,
  ExternalLink,
  Save,
  Download,
  Mail,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import type { PacketView as Packet } from "../lib/contracts";
import { decode, request } from "../lib/api";
import { useUnsavedChanges } from "../lib/unsaved";
const blank = {
  company: "",
  subject: "",
  body: "",
  evidence: "",
  fictional: false,
};
async function packet(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<Packet> {
  return decode("PacketView", await request(path, method, body));
}
async function listPackets(signal?: AbortSignal): Promise<Packet[]> {
  return decode(
    "PacketView",
    await request("desk", "GET", undefined, signal),
    true,
  );
}
export default function ReviewDesk({
  email,
  connected,
  onProfile,
}: {
  email: string;
  connected: boolean;
  onProfile: () => void;
}) {
  const [packets, setPackets] = useState<Packet[]>([]),
    [active, setActive] = useState<Packet | null>(null),
    [form, setForm] = useState(blank),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [result, setResult] = useState(""),
    [probability, setProbability] = useState(""),
    [report, setReport] = useState(""),
    [checks, setChecks] = useState({
      facts_checked: false,
      sounds_like_me: false,
      recipient_checked: false,
      detector_reviewed: false,
    });
  const refresh = useCallback(async () => {
    const rows = await listPackets();
    setPackets(rows);
    return rows;
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    listPackets(controller.signal)
      .then((rows) => {
        setPackets(rows);
        if (rows.length) {
          setActive(rows[0]);
          setForm(rows[0]);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, []);
  const dirty = (
    ["company", "subject", "body", "evidence", "fictional"] as const
  ).some((k) => form[k] !== (active || blank)[k]);
  useUnsavedChanges(dirty);
  function select(p: Packet) {
    setActive(p);
    setForm(p);
    setError("");
    setNotice("");
    setResult("");
    setProbability("");
    setReport("");
    setChecks({
      facts_checked: false,
      sounds_like_me: false,
      recipient_checked: false,
      detector_reviewed: false,
    });
  }
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function update(p: Packet) {
    setActive(p);
    setForm(p);
    await refresh();
  }
  async function copy(text: string, label: string) {
    await navigator.clipboard.writeText(text);
    setNotice(label);
  }
  async function exportEml() {
    if (!active) return;
    const data = decode("EmlView", await request(`desk/${active.id}/eml`));
    const url = URL.createObjectURL(
      new Blob([data.content], { type: "message/rfc822" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = data.filename;
    a.click();
    URL.revokeObjectURL(url);
    setNotice("Downloaded an unsent dry-run email addressed to you.");
  }
  const gmail =
    email && active
      ? "https://mail.google.com/mail/?authuser=" +
        encodeURIComponent(email) +
        "&view=cm&fs=1&to=" +
        encodeURIComponent(email) +
        "&su=" +
        encodeURIComponent("[DRY RUN] " + active.subject) +
        "&body=" +
        encodeURIComponent(
          (active.fictional
            ? "FICTIONAL PRACTICE — not a researched opportunity.\n\n"
            : "") + active.body,
        )
      : "";
  return (
    <div className="personal-desk">
      <div className="desk-banner">
        <div>
          <span className="eyebrow">JUST YOUR EMAIL WORKFLOW</span>
          <h2>Write it. Read it aloud. Make it yours.</h2>
          <p>
            Draft here with me, check the details, then send a test copy only to
            yourself.
          </p>
        </div>
        <span className="badge">
          <ShieldCheck size={14} /> Manual mode · no paid API calls
        </span>
      </div>
      <div className="desk-steps">
        <span>
          01 <b>Your voice</b>
        </span>
        <ArrowRight size={15} />
        <span>
          02 <b>Detector + review</b>
        </span>
        <ArrowRight size={15} />
        <span>
          03 <b>Test in your mailbox</b>
        </span>
      </div>
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="alert" role="status">
          {notice}
        </div>
      )}
      <div className="desk-layout">
        <aside className="desk-list">
          <button
            className="primary"
            onClick={() => {
              if (
                dirty &&
                !window.confirm(
                  "Discard unsaved edits and start a new practice email?",
                )
              )
                return;
              setActive(null);
              setForm(blank);
              setNotice("");
              setError("");
            }}
          >
            <Plus size={16} /> New email
          </button>
          {packets.map((p) => (
            <button
              className={
                active?.id === p.id ? "desk-item selected" : "desk-item"
              }
              key={p.id}
              onClick={() => {
                if (dirty) {
                  setError("Save your edits before switching drafts.");
                  return;
                }
                select(p);
              }}
            >
              <b>{p.company || "Personal draft"}</b>
              <span>{p.subject}</span>
              <small>
                {p.fictional ? "Fictional practice · " : ""}
                {p.status.replaceAll("_", " ")}
              </small>
            </button>
          ))}
          <p className="muted">
            This is your review queue. Only Send test to myself sends mail, and
            only to your connected account.
          </p>
        </aside>
        <section className="desk-editor">
          <form
            className="panel"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                const p = await packet(
                  active ? `desk/${active.id}` : "desk",
                  active ? "PUT" : "POST",
                  form,
                );
                await update(p);
                setChecks({
                  facts_checked: false,
                  sounds_like_me: false,
                  recipient_checked: false,
                  detector_reviewed: false,
                });
                setNotice(
                  "Saved locally. Changes reset old detector results and approvals.",
                );
              });
            }}
          >
            <div className="editor-header">
              <h2>{active ? "Your draft" : "Start an email"}</h2>
              {active && (
                <span className="badge">
                  {dirty ? "Unsaved edits" : active.status.replaceAll("_", " ")}
                </span>
              )}
            </div>
            <div className="form-grid">
              <label>
                Company
                <input
                  value={form.company}
                  onChange={(e) =>
                    setForm({ ...form, company: e.target.value })
                  }
                  placeholder="The team you want to meet"
                />
              </label>
              <label>
                Subject
                <input
                  required
                  maxLength={180}
                  value={form.subject}
                  onChange={(e) =>
                    setForm({ ...form, subject: e.target.value })
                  }
                  placeholder="One specific reason to connect"
                />
              </label>
            </div>
            <label>
              Email
              <textarea
                required
                className="desk-body"
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                placeholder="Start with what caught your attention. What would you actually say to this person?"
              />
            </label>
            <label>
              Company facts and source links
              <textarea
                rows={3}
                value={form.evidence}
                onChange={(e) => setForm({ ...form, evidence: e.target.value })}
                placeholder="Keep the source for any product, person or company claim here."
              />
            </label>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.fictional}
                onChange={(e) =>
                  setForm({ ...form, fictional: e.target.checked })
                }
              />{" "}
              This is a fictional practice email.
            </label>
            <div className="buttons">
              <button className="primary" disabled={busy}>
                <Save size={16} /> Save draft
              </button>
              <button type="button" className="secondary" onClick={onProfile}>
                Tune my voice
              </button>
              {active && (
                <button
                  type="button"
                  className="secondary"
                  disabled={dirty || busy}
                  onClick={() =>
                    act(async () => {
                      const profile = decode(
                        "ProfileInput",
                        await request("profile"),
                      );
                      await copy(
                        "Review and improve this internship email in my voice. Use only the supplied company evidence and my verified profile. Do not make paid app API calls or send any email. Make at most one revision, use a real detector as an advisory check, record its actual result, and leave the draft for my sign-off.\n\n" +
                          JSON.stringify({ profile, draft: active }, null, 2),
                        "Agent brief copied. Paste it into this task to work on the draft together.",
                      );
                    })
                  }
                >
                  <Copy size={16} /> Copy agent brief
                </button>
              )}
            </div>
          </form>
          {active && (
            <>
              <section className="panel">
                <div className="editor-header">
                  <h2>How it reads</h2>
                  <span className="muted">{active.style.words} words</span>
                </div>
                <p>
                  {active.style.generic_phrases.length
                    ? "Try replacing these stock phrases: " +
                      active.style.generic_phrases.join(", ")
                    : "No stock phrases from the local checklist found."}
                </p>
                {active.style.long_sentences > 0 && (
                  <p>
                    {active.style.long_sentences} long sentence(s): try reading
                    them aloud.
                  </p>
                )}
                <small>{active.style.note}</small>
              </section>
              <section className="panel">
                <div className="editor-header">
                  <h2>Detector check</h2>
                  <a
                    className="external"
                    href="https://gptzero.me/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open GPTZero <ExternalLink size={14} />
                  </a>
                </div>
                <p className="muted">
                  A detector result is an opinion about this text, not a verdict
                  about you. Keep the actual result; don’t rewrite endlessly to
                  chase a number.
                </p>
                <button
                  className="secondary"
                  disabled={dirty || busy}
                  onClick={() =>
                    act(() =>
                      copy(
                        active.body,
                        "Email body copied for the detector. Remove any private details before pasting.",
                      ),
                    )
                  }
                >
                  <Copy size={15} /> Copy saved email body
                </button>
                {active.detector && (
                  <div className="detector-result">
                    <strong>
                      {active.detector.provider}:{" "}
                      {active.detector.ai_probability === null
                        ? "No percentage reported"
                        : `${active.detector.ai_probability}% AI probability`}
                    </strong>
                    <p>{active.detector.result}</p>
                    <small>
                      Recorded manually ·{" "}
                      {new Date(active.detector.checked_at).toLocaleString()} ·
                      applies to this saved version only
                    </small>
                  </div>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    act(async () => {
                      await update(
                        await packet(`desk/${active.id}/detector`, "POST", {
                          draft_hash: active.draft_hash,
                          provider: "GPTZero",
                          ai_probability:
                            probability === "" ? null : Number(probability),
                          result,
                          report_url: report || null,
                        }),
                      );
                      setNotice(
                        "Actual detector result recorded. It does not approve the email.",
                      );
                    });
                  }}
                >
                  <div className="form-grid">
                    <label>
                      Reported AI probability (optional)
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={probability}
                        onChange={(e) => setProbability(e.target.value)}
                      />
                    </label>
                    <label>
                      Report link (optional)
                      <input
                        type="url"
                        value={report}
                        onChange={(e) => setReport(e.target.value)}
                      />
                    </label>
                  </div>
                  <label>
                    Paste the actual result or feedback
                    <textarea
                      required
                      rows={3}
                      value={result}
                      onChange={(e) => setResult(e.target.value)}
                    />
                  </label>
                  <button className="secondary" disabled={dirty || busy}>
                    Record result
                  </button>
                </form>
              </section>
              <section className="panel">
                <h2>Your final read</h2>
                {Object.entries({
                  facts_checked:
                    "I checked the company details and my experience.",
                  sounds_like_me:
                    "I would actually say this; it sounds like me.",
                  recipient_checked: "I checked who this is for.",
                  detector_reviewed:
                    "I read the detector feedback and made my own decision.",
                }).map(([key, label]) => (
                  <label className="checkbox" key={key}>
                    <input
                      type="checkbox"
                      checked={checks[key as keyof typeof checks]}
                      onChange={(e) =>
                        setChecks({ ...checks, [key]: e.target.checked })
                      }
                    />
                    {label}
                  </label>
                ))}
                <button
                  className="primary"
                  disabled={
                    dirty ||
                    busy ||
                    !active.detector ||
                    !Object.values(checks).every(Boolean)
                  }
                  onClick={() =>
                    act(async () => {
                      await update(
                        await packet(`desk/${active.id}/signoff`, "POST", {
                          draft_hash: active.draft_hash,
                          ...checks,
                        }),
                      );
                      setNotice("Reviewed. Still unsent.");
                    })
                  }
                >
                  <Check size={16} /> Mark reviewed
                </button>
              </section>
              <section className="panel mailbox-panel">
                <h2>Try it in your email</h2>
                <p>
                  {email ? (
                    <>
                      Dry-run recipient: <b>{email}</b>
                    </>
                  ) : (
                    "Add your email address in My profile to try a draft addressed only to you."
                  )}
                </p>
                <p className="muted">
                  Subject starts with [DRY RUN]. Download and Gmail compose stay
                  unsent. Send test to myself delivers a copy only to your
                  connected Gmail. No company is contacted.
                </p>
                <div className="buttons">
                  <button
                    className="secondary"
                    disabled={dirty || busy || !email}
                    onClick={() => act(exportEml)}
                  >
                    <Download size={16} /> Download unsent email
                  </button>
                  {gmail && !dirty && (
                    <a
                      className="secondary"
                      href={gmail}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Mail size={16} /> Open Gmail compose
                    </a>
                  )}
                  <button
                    className="primary"
                    disabled={dirty || busy || !connected || !email}
                    onClick={() =>
                      act(async () => {
                        const test = decode(
                          "SelfTestView",
                          await request(`desk/${active.id}/self-test`, "POST"),
                        );
                        setNotice(
                          `Test ${test.status} to ${test.to}. The same saved version is sent only once.`,
                        );
                      })
                    }
                  >
                    <Save size={16} /> Send test to myself
                  </button>
                  <button
                    className="text-button"
                    onClick={() =>
                      act(async () => {
                        const rows = await refresh();
                        const p = rows.find((r) => r.id === active.id);
                        if (p) await update(p);
                      })
                    }
                  >
                    Refresh status
                  </button>
                </div>
                {active.mailbox_draft && (
                  <p className="mail-status">
                    Mailbox draft: {active.mailbox_draft.status} · To:{" "}
                    {active.mailbox_draft.to}
                  </p>
                )}
                {!connected && (
                  <small>
                    Automatic mailbox saving needs OAuth authorization. You can
                    open Gmail compose or download the email without API
                    credentials.
                  </small>
                )}
              </section>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
