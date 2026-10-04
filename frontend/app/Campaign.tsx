"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Pause, ShieldCheck } from "lucide-react";
import type { CampaignView, CompanyView, OutreachView } from "../lib/contracts";
import { request, date } from "../lib/api";
import { Empty, ErrorState, Header, Loading, Status } from "../components/ui";
import Prospects from "../components/Prospects";
import ResponseInbox from "./ResponseInbox";
import Autopilot from "./Autopilot";
type Resource<T> = {
  data?: T;
  error?: string;
  loading: boolean;
  reload: () => Promise<void>;
};
export default function Campaign({
  resource,
  companies,
  messages,
  refresh,
}: {
  resource: Resource<CampaignView>;
  companies: Resource<CompanyView[]>;
  messages: Resource<OutreachView[]>;
  refresh: () => Promise<void>;
}) {
  const params = useSearchParams(),
    router = useRouter();
  const tab = params.get("tab") || "targets";
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const batch = resource.data;
  async function control(path: string, method: string, body?: unknown) {
    setBusy(true);
    setError("");
    try {
      await request(path, method, body);
      await resource.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Campaign update failed");
    } finally {
      setBusy(false);
    }
  }
  function select(value: string) {
    const next = new URLSearchParams(params);
    next.set("tab", value);
    router.push("/?" + next.toString(), { scroll: false });
  }
  const rows = (messages.data || []).filter(
    (m) => tab !== "followups" || m.sequence > 0,
  );
  return (
    <>
      <Header eyebrow="02 / THE CAMPAIGN" title="Keep every connection moving.">
        Targets, messages and responses in one place. Each step has a clear
        owner.
      </Header>
      <ErrorState error={resource.error || error} retry={resource.reload} />
      {resource.loading && !batch ? (
        <Loading />
      ) : (
        batch && (
          <>
            <section
              className={`campaign-policy ${batch.ongoing_policy.enabled ? "enabled" : "paused"}`}
              aria-label="Authoritative campaign policy"
            >
              <div className="policy-symbol">
                <Pause size={21} aria-hidden="true" />
              </div>
              <div>
                <strong>
                  {batch.ongoing_policy.enabled
                    ? "Recurring outreach is enabled"
                    : "Recurring outreach is paused"}
                </strong>
                <p>
                  {batch.ongoing_policy.enabled
                    ? "Scheduled outreach remains subject to server checks and attempt limits."
                    : "No recurring introductions or follow-ups run while this database policy is paused."}
                </p>
                <small>
                  {batch.active
                    ? `Separate batch: ${batch.batch_name || "Authorized outreach"} · ${batch.status}. Its scoped authorization is independent of the recurring pause.`
                    : "No active scoped batch is recorded."}
                </small>
                <p className="policy-cadence">
                  {batch.ongoing_policy.new_companies_per_weekday === null
                    ? "New-company pace not configured"
                    : `${batch.ongoing_policy.new_companies_per_weekday} new companies / weekday`}{" "}
                  ·{" "}
                  {batch.ongoing_policy.followup_after_days === null
                    ? "Follow-up cadence not configured"
                    : `Follow-up eligibility after ${batch.ongoing_policy.followup_after_days} days`}
                </p>
              </div>
              {batch.ongoing_policy.enabled && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    control("outreach-policy", "PUT", { enabled: false })
                  }
                >
                  {busy ? "Pausing…" : "Pause recurring outreach"}
                </button>
              )}
            </section>
            {batch.active && (
              <div className="batch-strip">
                <div>
                  <Status value={batch.status} />
                  <p>
                    {batch.detail ||
                      "Batch progress uses recorded send outcomes."}
                  </p>
                </div>
                <dl>
                  <div>
                    <dt>Planned</dt>
                    <dd>{batch.planned}</dd>
                  </div>
                  <div>
                    <dt>Sent records</dt>
                    <dd>{batch.sent}</dd>
                  </div>
                  <div>
                    <dt>Gmail Sent verified</dt>
                    <dd>{batch.verified}</dd>
                  </div>
                  <div>
                    <dt>Skipped</dt>
                    <dd>{batch.skipped}</dd>
                  </div>
                </dl>
                {batch.can_stop && (
                  <button
                    className="secondary"
                    disabled={busy || batch.stop_requested}
                    onClick={() => control("campaign/stop", "POST")}
                  >
                    {batch.stop_requested
                      ? "Stopping before the next send…"
                      : "Stop this batch"}
                  </button>
                )}
              </div>
            )}
          </>
        )
      )}
      <Autopilot />
      <div className="campaign-stage-ledger" aria-label="Workspace pipeline">
        {[
          ["Prospects", companies.data?.length || 0],
          [
            "Needs review",
            messages.data?.filter((m) => m.status === "draft").length || 0,
          ],
          [
            "Approved, unsent",
            messages.data?.filter((m) => m.status === "approved").length || 0,
          ],
          [
            "Delivery uncertain",
            messages.data?.filter((m) => m.status === "unknown").length || 0,
          ],
        ].map(([label, count]) => (
          <div key={label}>
            <strong>
              {companies.loading || messages.loading ? "…" : count}
            </strong>
            <span>{label}</span>
          </div>
        ))}
      </div>
      <nav className="workspace-tabs" aria-label="Campaign sections">
        {["targets", "messages", "responses", "followups"].map((value) => (
          <button
            key={value}
            aria-current={tab === value ? "page" : undefined}
            className={tab === value ? "selected" : ""}
            onClick={() => select(value)}
          >
            {value === "followups" ? "Follow-ups" : value}
          </button>
        ))}
      </nav>
      {tab === "targets" ? (
        <Prospects resource={companies} campaign />
      ) : tab === "responses" ? (
        <ResponseInbox />
      ) : (
        <section className="section">
          <div className="section-heading">
            <h2>
              {tab === "followups" ? "Follow-up queue" : "Message ledger"}
            </h2>
            <button className="text-button" onClick={refresh}>
              Refresh records
            </button>
          </div>
          <ErrorState error={messages.error} retry={messages.reload} />
          {messages.loading && !messages.data ? (
            <Loading />
          ) : rows.length ? (
            <div className="message-ledger">
              {rows.slice(0, 100).map((m) => (
                <Link key={m.id} href={`/?view=review&message=${m.id}`}>
                  <div>
                    <strong>
                      {companies.data?.find((c) => c.id === m.company_id)
                        ?.name || "Company record"}
                    </strong>
                    <p>{m.subject}</p>
                    <small>
                      {m.sequence
                        ? `Follow-up ${m.sequence} · due ${date(m.due_at)}`
                        : "First introduction"}
                    </small>
                  </div>
                  <Status value={m.status} />
                </Link>
              ))}
            </div>
          ) : (
            <Empty
              title={
                tab === "followups"
                  ? "No follow-up is queued"
                  : "No messages yet"
              }
            >
              {tab === "followups"
                ? "A follow-up needs an eligible initial message, no response or bounce, and a fresh server check. Paused policy remains authoritative."
                : "Research a prospect before preparing its introduction."}
            </Empty>
          )}
        </section>
      )}
      <p className="quiet-note">
        <ShieldCheck size={15} aria-hidden="true" />
        Approval is a review state. The server still checks pause, suppression,
        replies, quotas and delivery uncertainty before any send.
      </p>
    </>
  );
}
