"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { ArrowUpRight, RefreshCw, X } from "lucide-react";
import { safeLink } from "../lib/api";

const labels: Record<string, string> = {
  unknown: "Delivery uncertain",
  sending: "Send in progress",
  sent: "Sent receipt recorded",
  approved: "Approved · unsent",
  draft: "Needs review",
  rejected: "Returned for changes",
  auto_reply: "Acknowledgment · held",
  opt_out: "Opted out",
  needs_review: "Needs review",
  inactive: "No active batch",
};
export function Status({ value }: { value: string }) {
  return (
    <span className={`status status-${value}`}>
      <span aria-hidden="true" className="status-dot" />
      {labels[value] || value.replaceAll("_", " ")}
    </span>
  );
}
export function External({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  const url = safeLink(href);
  return url ? (
    <a className="external" href={url} target="_blank" rel="noreferrer">
      {children}
      <ArrowUpRight size={14} aria-hidden="true" />
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  ) : (
    <span className="muted">Source link unavailable</span>
  );
}
export function ErrorState({
  error,
  retry,
  id,
}: {
  error?: string;
  retry?: () => void;
  id?: string;
}) {
  return error ? (
    <div className="alert error" role="alert" id={id}>
      <div>
        <strong>This section needs attention</strong>
        <p>{error}</p>
      </div>
      {retry && (
        <button className="secondary" onClick={retry}>
          <RefreshCw size={14} aria-hidden="true" />
          Retry
        </button>
      )}
    </div>
  ) : null;
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-rule" aria-hidden="true" />
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Loading({
  label = "Loading this section",
}: {
  label?: string;
}) {
  return (
    <div className="loading" role="status" aria-label={label}>
      <span className="skeleton" />
      <span className="skeleton" />
      <span className="skeleton" />
      <span className="sr-only">{label}</span>
    </div>
  );
}
export function Header({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {children && <p className="intro">{children}</p>}
      </div>
      {action}
    </div>
  );
}
export function Dialog({
  title,
  children,
  close,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    const dialog = ref.current;
    dialog?.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby="dialog-title"
      onCancel={close}
      onKeyDown={(e) => {
        if (e.key !== "Tab") return;
        // WebKit on macOS may omit links from native Tab navigation. Keep the
        // dialog's controls and results reachable with a consistent focus loop.
        const controls = Array.from(
          e.currentTarget.querySelectorAll<HTMLElement>(
            "a[href], button, input, select, textarea, [tabindex]",
          ),
        ).filter(
          (el) =>
            el.tabIndex >= 0 &&
            !el.hasAttribute("disabled") &&
            el.getClientRects().length > 0,
        );
        if (!controls.length) return;
        const current = controls.indexOf(document.activeElement as HTMLElement);
        const next =
          (current + (e.shiftKey ? -1 : 1) + controls.length) % controls.length;
        e.preventDefault();
        controls[next].focus();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="dialog-header">
        <h2 id="dialog-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
