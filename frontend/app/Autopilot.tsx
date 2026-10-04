"use client";
import { useEffect, useRef, useState } from "react";
import { useResource, request, decode, invalidate } from "../lib/api";
import { Dialog, ErrorState, Loading } from "../components/ui";

export default function Autopilot() {
  const resource = useResource("autopilot", "AutopilotView", false, 30000);
  const [target, setTarget] = useState("10");
  const [initials, setInitials] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failures, setFailures] = useState<string[] | null>(null);
  const [confirm, setConfirm] = useState(false);
  const initialized = useRef(false);
  const activationButton = useRef<HTMLButtonElement>(null);
  const data = resource.data;
  useEffect(() => {
    if (data && !initialized.current) {
      initialized.current = true;
      setTarget(String(data.new_companies_per_weekday));
      setInitials(data.auto_approve_initials);
    }
  }, [data]);
  const valid =
    /^\d+$/.test(target) && Number(target) >= 1 && Number(target) <= 25;
  const spec = {
    autopilot_enabled: true,
    new_companies_per_weekday: Number(target),
    auto_approve_initials: initials,
    auto_approve_followups: false,
  };
  async function check() {
    setBusy(true);
    setError("");
    setFailures(null);
    try {
      const result = decode(
        "AutopilotPrecheck",
        await request("autopilot/precheck", "POST", spec),
      );
      setFailures(result.failures);
      if (result.ready) setConfirm(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Activation precheck failed");
    } finally {
      setBusy(false);
    }
  }
  async function update(enabled: boolean) {
    setBusy(true);
    setError("");
    try {
      const body = enabled
        ? { ...spec, confirmed: true }
        : {
            autopilot_enabled: false,
            new_companies_per_weekday: data?.new_companies_per_weekday || 10,
            auto_approve_initials: data?.auto_approve_initials || false,
            auto_approve_followups: false,
          };
      decode("AutopilotView", await request("autopilot", "PUT", body));
      invalidate("autopilot", "campaign", "outreach", "runtime");
      await resource.reload();
      setConfirm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Mode update failed");
    } finally {
      setBusy(false);
    }
  }
  async function pause() {
    setBusy(true);
    setError("");
    try {
      await request("outreach-policy", "PUT", { enabled: false });
      invalidate("autopilot", "campaign", "runtime");
      await resource.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pause failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="section autopilot-panel"
      aria-label="Autopilot outreach"
    >
      <div className="section-heading">
        <h2>Autopilot outreach</h2>
        <strong role="status" aria-label="Autopilot status">
          AUTOPILOT{" "}
          {data ? (data.autopilot_enabled ? "ON" : "OFF") : "UNAVAILABLE"}
        </strong>
      </div>
      <p>
        When enabled, Fieldwork can research, prepare, approve and send eligible
        outreach without reviewing every message manually. The global pause and
        all delivery checks still apply.
      </p>
      <ErrorState error={resource.error || error} retry={resource.reload} />
      {!data ? (
        <Loading />
      ) : (
        <>
          <p>
            <strong>
              Recurring outreach: {data.recurring_paused ? "PAUSED" : "ON"}
            </strong>{" "}
            · {data.autopilot_enabled ? "Autopilot mode" : "Manual review mode"}
            . Activating Autopilot does not resume recurring outreach.
          </p>
          <dl className="autopilot-stats">
            {[
              [
                "Daily target",
                `${data.new_companies_per_weekday} new introductions / weekday`,
              ],
              [
                "Sent / attempted today",
                `${data.daily_attempts} / ${data.daily_limit}`,
              ],
              [
                "New introductions today",
                `${data.new_introductions_today} / ${data.new_companies_per_weekday}`,
              ],
              ["Approved queue", data.approved_queue],
              ["Needs review", data.needs_review],
              ["Replies", data.replies],
              ["Delivery holds", data.delivery_holds],
              ["Provider / budget", data.provider_budget_status],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <p>
            Up to your target, only when qualified prospects and provider
            capacity exist. The hard limit is 25 total daily attempts, including
            follow-ups, self-tests and uncertain attempts. Sending uses weekday
            business hours and the configured spacing.
          </p>
          <div className="autopilot-controls">
            <label>
              Daily new introductions
              <input
                type="number"
                min="1"
                max="25"
                step="1"
                value={target}
                disabled={busy}
                onChange={(e) => {
                  setTarget(e.target.value);
                  setFailures(null);
                }}
                aria-describedby="autopilot-target-help"
              />
            </label>
            <small id="autopilot-target-help">
              Choose 1–25 per weekday. This is a maximum, not a quota to fill.
            </small>
            <label>
              <input
                type="checkbox"
                checked={initials}
                disabled={busy}
                onChange={(e) => {
                  setInitials(e.target.checked);
                  setFailures(null);
                }}
              />
              Automatic initial-message approval
            </label>
            <label>
              <input type="checkbox" disabled checked={false} />
              Automatic follow-up approval — OFF
            </label>
            <small>
              Follow-ups require independent manual review and add new value
              after at least 168 hours. One follow-up maximum.
            </small>
          </div>
          {failures && failures.length > 0 && (
            <div role="alert">
              <strong>Activation needs attention</strong>
              <ul>
                {failures.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="buttons">
            <button
              ref={activationButton}
              className="primary"
              disabled={busy || !valid || !!resource.error}
              onClick={check}
            >
              {busy
                ? "Checking…"
                : data.autopilot_enabled
                  ? "Review Autopilot changes"
                  : "Activate Autopilot"}
            </button>
            {data.autopilot_enabled && (
              <button
                className="secondary"
                disabled={busy}
                onClick={() => update(false)}
              >
                Disable Autopilot
              </button>
            )}
            {!data.recurring_paused && (
              <button className="secondary" disabled={busy} onClick={pause}>
                Emergency Pause recurring outreach
              </button>
            )}
          </div>
        </>
      )}
      {confirm && (
        <Dialog
          title="Confirm Autopilot activation"
          returnFocus={activationButton}
          close={() => {
            if (!busy) setConfirm(false);
          }}
        >
          <p>
            Use up to {target} new introductions per weekday with automatic
            initial approval {initials ? "ON" : "OFF"}. Eligible sends still
            require the authoritative recurring policy to be enabled. The total
            daily attempt cap remains 25.
          </p>
          <p>
            Replies, acknowledgments, bounces, opt-outs and uncertain delivery
            stop or hold communication. No automatic replies are sent.
          </p>
          <ErrorState error={error} />
          <div className="buttons">
            <button
              className="primary"
              disabled={busy}
              onClick={() => update(true)}
            >
              {busy ? "Activating…" : "Confirm Activate Autopilot"}
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => setConfirm(false)}
            >
              Cancel
            </button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
