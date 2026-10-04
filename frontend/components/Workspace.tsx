"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Compass,
  LayoutDashboard,
  Mail,
  Search,
  Settings2,
  UserRound,
  Workflow,
  Plus,
} from "lucide-react";
import { useResource, request } from "../lib/api";
import { Dialog, ErrorState, Header, Loading } from "./ui";
import Dashboard from "./Dashboard";
import Discovery from "./Discovery";
import Prospects from "./Prospects";
import Prospect from "./Prospect";
import Campaign from "../app/Campaign";
import Review from "./Review";
import Profile from "./Profile";
import ResponseInbox from "../app/ResponseInbox";
import AccountControls from "../app/AccountControls";
import ReviewDesk from "../app/ReviewDesk";
import type { CompanyView } from "../lib/contracts";
export const navigation = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "discovery", label: "Discovery", icon: Search },
  { id: "prospects", label: "Prospects", icon: Compass },
  { id: "campaign", label: "Campaign", icon: Workflow },
  { id: "review", label: "Outreach review", icon: Mail },
  { id: "responses", label: "Responses", icon: ArrowRight },
  { id: "desk", label: "Practice desk", icon: Mail },
  { id: "profile", label: "My profile", icon: UserRound },
  { id: "settings", label: "Settings", icon: Settings2 },
];
export default function Workspace() {
  const params = useSearchParams(),
    router = useRouter();
  const view = navigation.some((n) => n.id === params.get("view"))
    ? params.get("view")!
    : "dashboard";
  const watchPipeline = [
    "dashboard",
    "campaign",
    "review",
    "prospects",
  ].includes(view);
  const companies = useResource(
    "companies",
    "CompanyView",
    true,
    watchPipeline ? 30000 : 0,
  );
  const messages = useResource(
    "outreach",
    "OutreachView",
    true,
    watchPipeline ? 30000 : 0,
  );
  const profile = useResource("profile", "ProfileInput");
  const settings = useResource("settings", "SettingsView");
  const campaign = useResource("campaign", "CampaignView", false, 30000);
  const [command, setCommand] = useState(false),
    [adding, setAdding] = useState(false);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommand((c) => !c);
      }
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, []);
  const refresh = async () => {
    await Promise.all([
      companies.reload(),
      messages.reload(),
      campaign.reload(),
    ]);
  };
  const company = params.get("company"),
    title = company
      ? "Prospect detail"
      : navigation.find((n) => n.id === view)!.label;
  return (
    <div className="workspace">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="Fieldwork overview">
          <span className="brand-symbol" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          fieldwork<span className="brand-period">.</span>
        </Link>
        <p className="nav-caption">YOUR FIELD NOTES</p>
        <nav aria-label="Workspace">
          {navigation.map((n) => (
            <Link
              key={n.id}
              href={`/?view=${n.id}`}
              aria-current={view === n.id ? "page" : undefined}
              className={view === n.id ? "nav active" : "nav"}
            >
              <n.icon size={17} aria-hidden="true" />
              {n.label}
              {n.id === "review" &&
                !!messages.data?.filter((m) => m.status === "draft").length && (
                  <span className="nav-count">
                    {messages.data.filter((m) => m.status === "draft").length}
                  </span>
                )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <p className="field-note">
            A real reason.
            <br />A useful offer.
            <br />A conversation.
          </p>
          <Link className="identity" href="/?view=profile">
            <span className="avatar" aria-hidden="true">
              {profile.data?.name?.[0] || "V"}
            </span>
            <span>
              <b>{profile.data?.name || "Your workspace"}</b>
              <small>Personal installation</small>
            </span>
          </Link>
        </div>
      </aside>
      <div className="work-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>{title}</strong>
          </div>
          <button
            className="command-trigger"
            aria-label="Find a prospect or action"
            aria-keyshortcuts="Meta+K Control+K"
            onClick={(event) => {
              event.currentTarget.focus();
              setCommand(true);
            }}
          >
            <Search size={16} aria-hidden="true" />
            <span>Find a prospect or action</span>
            <kbd>⌘ K</kbd>
          </button>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <div className="workspace-meta">
            <span>PERSONAL OUTREACH WORKSPACE</span>
            <span>
              {campaign.error
                ? "Pause status unavailable · check Settings"
                : campaign.data
                  ? campaign.data.ongoing_policy.enabled
                    ? "Recurring outreach enabled"
                    : "Recurring outreach paused"
                  : "Checking outreach status…"}
            </span>
          </div>
          {company ? (
            <Prospect
              id={company}
              messages={messages.data || []}
              campaign={campaign.data}
              refresh={refresh}
            />
          ) : (
            <>
              {view === "dashboard" && (
                <Dashboard
                  companies={companies}
                  messages={messages}
                  profile={profile.data}
                  campaign={campaign}
                />
              )}
              {view === "discovery" && <Discovery />}
              {view === "prospects" && (
                <>
                  <Header
                    eyebrow="01 / THE RIGHT TEAMS"
                    title="Make your next connection."
                    action={
                      <button
                        className="primary"
                        onClick={() => setAdding(true)}
                      >
                        <Plus size={16} aria-hidden="true" />
                        Add prospect
                      </button>
                    }
                  >
                    Greater Sacramento. Prioritized by fit, backed by a reason
                    to reach out.
                  </Header>
                  <Prospects resource={companies} />
                </>
              )}
              {view === "campaign" && (
                <Campaign
                  resource={campaign}
                  companies={companies}
                  messages={messages}
                  refresh={refresh}
                />
              )}
              {view === "review" && (
                <Review
                  companies={companies.data || []}
                  messages={messages}
                  profile={profile.data}
                  refresh={refresh}
                />
              )}
              {view === "responses" && (
                <>
                  <Header
                    eyebrow="04 / CONVERSATIONS"
                    title="The replies that matter."
                  >
                    Reply previews stay here. Read and respond in Gmail when
                    you’re ready.
                  </Header>
                  <ResponseInbox />
                </>
              )}
              {view === "profile" && <Profile resource={profile} />}
              {view === "settings" && (
                <>
                  <Header
                    eyebrow="WORKSPACE / SETTINGS"
                    title="Connected. Under your control."
                  >
                    Your private account and the current server settings.
                  </Header>
                  <AccountControls />
                  <ErrorState error={settings.error} retry={settings.reload} />
                  {settings.loading && !settings.data ? (
                    <Loading />
                  ) : (
                    settings.data && (
                      <section className="settings-ledger">
                        <h2>How this workspace runs</h2>
                        <dl>
                          <dt>General worker mode</dt>
                          <dd>
                            {settings.data.dry_run
                              ? "Dry run · no general-worker delivery"
                              : "Live sends subject to server policy"}
                          </dd>
                          <dt>Workflow</dt>
                          <dd>
                            {settings.data.manual_mode
                              ? "Personal manual mode"
                              : "Provider-assisted mode"}
                          </dd>
                          <dt>Daily attempt ceiling</dt>
                          <dd>
                            {settings.data.daily_send_limit} including
                            follow-ups and uncertain attempts
                          </dd>
                          <dt>Research boundary</dt>
                          <dd>
                            {settings.data.max_pages} pages /{" "}
                            {settings.data.research_seconds} seconds per company
                          </dd>
                          <dt>Automatic approval</dt>
                          <dd>
                            {settings.data.auto_approve
                              ? "Configured on"
                              : "Off"}
                          </dd>
                        </dl>
                        <p className="muted">
                          Recurring policy is shown above. A separately
                          authorized batch can have its own scope. Settings and
                          approval do not guarantee permission to send.
                        </p>
                        <p className="muted">
                          A local installation checks mail while its server is
                          running. It cannot run while your Mac is asleep.
                        </p>
                      </section>
                    )
                  )}
                </>
              )}
              {view === "desk" && (
                <>
                  <Header
                    eyebrow="WORKSPACE / PRACTICE"
                    title="Find the words that sound like you."
                  >
                    A separate, clearly labeled workflow for test copies to
                    yourself.
                  </Header>
                  <ReviewDesk
                    email={profile.data?.email || ""}
                    connected={!!settings.data?.mail_connected}
                    onProfile={() => router.push("/?view=profile")}
                  />
                </>
              )}
            </>
          )}
        </main>
        <footer className="workspace-footer">
          <span>FIELDWORK / ONE GOOD CONNECTION AT A TIME</span>
          <span>Private workspace</span>
        </footer>
      </div>
      {command && (
        <CommandPalette
          companies={companies.data || []}
          close={() => setCommand(false)}
        />
      )}
      {adding && (
        <AddProspect
          close={() => setAdding(false)}
          saved={async () => {
            await companies.reload();
            setAdding(false);
          }}
        />
      )}
    </div>
  );
}
function CommandPalette({
  companies,
  close,
}: {
  companies: CompanyView[];
  close: () => void;
}) {
  const [query, setQuery] = useState("");
  const results = [
    ...navigation.map((n) => ({
      href: `/?view=${n.id}`,
      label: n.label,
      category: "Go to",
    })),
    ...companies.map((c) => ({
      href: `/?view=prospects&company=${c.id}`,
      label: c.name,
      category: c.industry,
    })),
  ]
    .filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 12);
  return (
    <Dialog title="Find your next move" close={close}>
      <label className="command-input">
        Search prospects and actions
        <input
          autoFocus
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Company name, review, responses…"
        />
      </label>
      <nav aria-label="Search results" className="command-results">
        {results.map((r) => (
          <Link key={r.href} href={r.href} onClick={close}>
            <span>{r.label}</span>
            <small>{r.category}</small>
            <ArrowRight size={15} aria-hidden="true" />
          </Link>
        ))}
        {!results.length && <p>No matching prospect or action.</p>}
      </nav>
      <p className="dialog-footnote">
        Tab to a result, Enter to open. Esc to close.
      </p>
    </Dialog>
  );
}
function AddProspect({
  close,
  saved,
}: {
  close: () => void;
  saved: () => Promise<void>;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <Dialog title="Add a prospect" close={close}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          setBusy(true);
          setError("");
          try {
            await request("companies", "POST", {
              name: data.get("name"),
              website: data.get("website"),
              industry: data.get("industry") || "Unknown",
              distance_miles: data.get("distance")
                ? Number(data.get("distance"))
                : null,
              source: "manual",
            });
            await saved();
          } catch (err) {
            setError(
              err instanceof Error ? err.message : "Could not add company",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Company name
          <input name="name" required maxLength={255} autoFocus />
        </label>
        <label>
          Company website
          <input
            name="website"
            type="url"
            required
            placeholder="https://company.com"
          />
        </label>
        <div className="form-grid">
          <label>
            Industry
            <input name="industry" maxLength={100} />
          </label>
          <label>
            Distance (miles, if verified)
            <input name="distance" type="number" min="0" step="0.1" />
          </label>
        </div>
        <ErrorState error={error} />
        <button className="primary" disabled={busy}>
          {busy ? "Adding…" : "Add prospect"}
        </button>
      </form>
    </Dialog>
  );
}
