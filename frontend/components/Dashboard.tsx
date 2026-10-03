"use client";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Mail,
  Pause,
  ShieldCheck,
} from "lucide-react";
import type {
  CampaignView,
  CompanyView,
  OutreachView,
  ProfileInput,
} from "../lib/contracts";
import { useResource } from "../lib/api";
import { Empty, ErrorState, Header, Loading, Status } from "./ui";
type Resource<T> = {
  data?: T;
  loading: boolean;
  error?: string;
  reload: () => Promise<void>;
};
export default function Dashboard({
  companies,
  messages,
  profile,
  campaign,
}: {
  companies: Resource<CompanyView[]>;
  messages: Resource<OutreachView[]>;
  profile?: ProfileInput;
  campaign: Resource<CampaignView>;
}) {
  const metrics = useResource("metrics", "MetricsView", false, 30000),
    inbox = useResource("responses", "InboxView", false, 30000);
  const replies =
    inbox.data?.responses.filter((r) => r.kind === "reply" && !r.handled) || [];
  const uncertain =
    messages.data?.filter(
      (m) => m.status === "unknown" || m.status === "sending",
    ) || [];
  const drafts = messages.data?.filter((m) => m.status === "draft") || [];
  const next = uncertain.length
    ? {
        title: "Resolve delivery uncertainty first.",
        note: `${uncertain.length} message(s) need receipt reconciliation. Keep outreach held and inspect the message history.`,
        href: "/?view=review",
        action: "Inspect messages",
      }
    : replies.length
      ? {
          title: "A conversation is waiting for you.",
          note: `${replies[0].company} replied. Read the context and decide your next step in Gmail.`,
          href: "/?view=responses",
          action: "Read the response",
        }
      : !profile?.verified
        ? {
            title: "Give every introduction a solid foundation.",
            note: "Check your projects, experience and links, then verify your profile before outreach review.",
            href: "/?view=profile",
            action: "Check my profile",
          }
        : drafts.length
          ? {
              title: "Make the next introduction count.",
              note: `${drafts.length} draft(s) are ready to inspect. Match the message to its evidence and your experience.`,
              href: "/?view=review",
              action: "Review outreach",
            }
          : {
              title: "Find a team you can contribute to.",
              note: "Start with one strong prospect. A useful project and a verified contact are better than a full queue.",
              href: "/?view=prospects",
              action: "Explore prospects",
            };
  const top = [...(companies.data || [])]
    .filter((c) => !["bounce", "opt_out", "closed"].includes(c.stage))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  return (
    <>
      <Header
        eyebrow="YOUR NEXT CHAPTER"
        title={
          profile?.name
            ? `Good to see you, ${profile.name.split(" ")[0]}.`
            : "Your next chapter starts here."
        }
      >
        Keep your attention on the right people, the right work, and the next
        conversation.
      </Header>
      <div className="dashboard-layout">
        <div className="dashboard-primary">
          <section className="next-action">
            <p className="eyebrow">NEXT MOVE</p>
            <h2>{next.title}</h2>
            <p>{next.note}</p>
            <Link className="primary" href={next.href}>
              {next.action}
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </section>
          <section className="section">
            <div className="section-heading">
              <h2>
                Conversations to pick up <span>{replies.length}</span>
              </h2>
              <Link className="text-button" href="/?view=responses">
                All responses
                <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            </div>
            <ErrorState error={inbox.error} retry={inbox.reload} />
            {inbox.loading && !inbox.data ? (
              <Loading />
            ) : replies.length ? (
              replies.slice(0, 2).map((r) => (
                <Link className="reply-row" key={r.id} href="/?view=responses">
                  <span className="reply-icon">
                    <Mail size={18} aria-hidden="true" />
                  </span>
                  <div>
                    <strong>{r.company}</strong>
                    <p>{r.subject}</p>
                    <small>{r.preview.slice(0, 160)}</small>
                  </div>
                  <span className="reply-action">
                    Read reply
                    <ArrowRight size={16} aria-hidden="true" />
                  </span>
                </Link>
              ))
            ) : (
              <Empty title="Room for the next conversation">
                No human replies currently need attention. Delivery updates and
                acknowledgments live in Responses.
              </Empty>
            )}
          </section>
          <section className="section">
            <div className="section-heading">
              <h2>Prospects worth a closer look</h2>
              <Link className="text-button" href="/?view=prospects">
                View pipeline
                <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            </div>
            <ErrorState error={companies.error} retry={companies.reload} />
            {companies.loading && !companies.data ? (
              <Loading />
            ) : top.length ? (
              <div className="shortlist">
                {top.map((c, index) => (
                  <Link key={c.id} href={`/?view=prospects&company=${c.id}`}>
                    <span className="list-index">0{index + 1}</span>
                    <div>
                      <strong>{c.name}</strong>
                      <small>
                        {c.industry}
                        {c.demo ? " · Demo record" : ""}
                      </small>
                    </div>
                    <Status value={c.stage} />
                    <span className="fit-score">
                      {c.score}
                      <small>fit / 100</small>
                    </span>
                    <ArrowUpRight size={17} aria-hidden="true" />
                  </Link>
                ))}
              </div>
            ) : (
              <Empty title="Start with a team you know">
                Add a company to begin building an evidence-backed prospect
                list.
              </Empty>
            )}
          </section>
        </div>
        <aside className="dashboard-aside">
          <section className="attention-section">
            <p className="eyebrow">WORKSPACE STATUS</p>
            <ErrorState error={campaign.error} retry={campaign.reload} />
            {campaign.data ? (
              <>
                <div className="pause-label">
                  <Pause size={17} aria-hidden="true" />
                  <strong>
                    {campaign.data.ongoing_policy.enabled
                      ? "Recurring outreach enabled"
                      : "Recurring outreach paused"}
                  </strong>
                </div>
                <p>
                  {campaign.data.ongoing_policy.enabled
                    ? "The server policy governs every scheduled attempt."
                    : "The recurring schedule stays paused. Review and research remain available."}
                </p>
                <Link className="text-button" href="/?view=campaign">
                  Inspect campaign
                  <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </>
            ) : (
              <Loading />
            )}
            <div className="attention-count">
              <strong>{uncertain.length}</strong>
              <span>uncertain / in-progress deliveries</span>
            </div>
            <div className="attention-count">
              <strong>{drafts.length}</strong>
              <span>messages needing review</span>
            </div>
            <ErrorState error={messages.error} retry={messages.reload} />
          </section>
          <section className="progress-section">
            <p className="eyebrow">CONVERSATIONS → OPPORTUNITIES</p>
            <h2>Progress, with context.</h2>
            <ErrorState error={metrics.error} retry={metrics.reload} />
            {metrics.loading && !metrics.data ? (
              <Loading />
            ) : (
              metrics.data && (
                <>
                  <dl className="progress-ledger">
                    {[
                      ["Companies contacted", metrics.data.sent],
                      ["Companies that replied", metrics.data.replies],
                      ["Interviews", metrics.data.interviews],
                      ["Offers", metrics.data.offers],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <p className="metric-note">
                    {metrics.data.sent
                      ? `${Math.round(metrics.data.response_rate * 100)}% reply rate · ${metrics.data.replies} of ${metrics.data.sent} contacted companies`
                      : "No confirmed outreach yet. Rates will appear after a real send."}
                  </p>
                  <small>
                    Counts use confirmed initial outreach to real companies.
                    Demo records and drafts are excluded.
                  </small>
                </>
              )
            )}
          </section>
          <p className="quiet-note">
            <ShieldCheck size={16} aria-hidden="true" />
            Quality before quota. No open-tracking pixels.
          </p>
        </aside>
      </div>
    </>
  );
}
