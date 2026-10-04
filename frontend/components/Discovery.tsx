"use client";
import Link from "next/link";
import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useResource, request, date, text, decode } from "../lib/api";
import { Empty, ErrorState, External, Header, Loading, Status } from "./ui";
import IntelligenceJobs from "./IntelligenceJobs";
export default function Discovery() {
  const rows = useResource(
      "discovery/candidates",
      "CandidateView",
      true,
      10000,
    ),
    caps = useResource("intelligence/capabilities", "CapabilitiesView");
  const params = useSearchParams(),
    router = useRouter();
  const query = params.get("q") || "",
    status = params.get("candidateStatus") || "candidate",
    sort = params.get("candidateSort") || "recent",
    scope = params.get("scope") || "all";
  const [provider, setProvider] = useState("maps");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  function filter(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set(key, value);
    router.replace("/?" + next, { scroll: false });
  }
  async function act(path: string, body?: unknown) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await request(path, "POST", body);
      await rows.reload();
      setNotice(
        path.endsWith("accept")
          ? "Prospect accepted. Research and review still come before approval."
          : path.endsWith("dismiss")
            ? "Candidate dismissed."
            : ["discover", "discovery/import"].includes(path)
              ? `Work ${decode("JobView", response).status}. Check its saved state below; no email is sent.`
              : "Saved.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not queue work");
    } finally {
      setBusy(false);
    }
  }
  const visible = (rows.data || [])
    .filter(
      (c) =>
        `${c.name} ${c.industry} ${c.domain}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (status === "all" || c.status === status) &&
        (scope === "all" || c.contexts.includes(scope)),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name)
        : sort === "distance"
          ? (a.distance_miles ?? Infinity) - (b.distance_miles ?? Infinity)
          : b.updated_at.localeCompare(a.updated_at),
    );
  const contexts = Array.from(
    new Set((rows.data || []).flatMap((c) => c.contexts)),
  );
  return (
    <>
      <Header
        eyebrow="DISCOVERY / A REAL REASON"
        title="Find a team worth meeting."
      >
        Candidates stay here until you deliberately accept them. A search result
        is a lead to investigate, not a verified internship.
      </Header>
      <ErrorState error={error || caps.error} retry={caps.reload} />
      {notice && (
        <p className="alert" role="status">
          {notice}
        </p>
      )}
      <div className="discovery-context">
        <section className="section">
          <h2>Your search area</h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void act("discover", {
                area: f.get("area"),
                industry: f.get("industry"),
                provider: f.get("provider"),
                limit: Number(f.get("limit")),
                radius_miles: Number(f.get("radius")),
                context: f.get("context"),
                latitude: Number(f.get("latitude")),
                longitude: Number(f.get("longitude")),
              });
            }}
          >
            <label>
              Area
              <input
                name="area"
                required
                defaultValue="Rocklin / Roseville / greater Sacramento"
                maxLength={120}
              />
            </label>
            <label>
              Target interests
              <input
                name="industry"
                required
                defaultValue="software AI robotics engineering finance startups"
                maxLength={120}
              />
            </label>
            <label>
              Search context
              <input
                name="context"
                defaultValue="Personal internship search"
                maxLength={160}
              />
            </label>
            <div className="form-grid">
              <label>
                Radius (miles)
                <input
                  name="radius"
                  type="number"
                  min={1}
                  max={300}
                  defaultValue={50}
                />
              </label>
              <label>
                Candidate limit
                <input
                  name="limit"
                  type="number"
                  min={1}
                  max={caps.data?.limits.companies || 30}
                  defaultValue={20}
                />
              </label>
              <label>
                Center latitude
                <input
                  name="latitude"
                  type="number"
                  step="any"
                  min={-90}
                  max={90}
                  defaultValue={38.7907}
                />
              </label>
              <label>
                Center longitude
                <input
                  name="longitude"
                  type="number"
                  step="any"
                  min={-180}
                  max={180}
                  defaultValue={-121.2358}
                />
              </label>
            </div>
            <label>
              Discovery source
              <select
                name="provider"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                {["maps", "tavily", "apollo"].map((id) => (
                  <option key={id} value={id}>
                    {id === "maps"
                      ? "Google Places"
                      : id === "tavily"
                        ? "Tavily search"
                        : "Apollo companies"}
                    {caps.data?.providers.find((p) => p.id === id)?.available
                      ? ""
                      : " · unavailable"}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted">
              {caps.data?.paid_allowed
                ? "Only configured sources are available; configuration is not a live health check."
                : "Provider searches are unavailable while paid calls are disabled. Add known companies below at no provider cost."}
            </p>
            <button
              className="primary"
              disabled={
                busy ||
                !caps.data?.providers.find((p) => p.id === provider)?.available
              }
            >
              Queue bounded search
            </button>
          </form>
        </section>
        <section className="section">
          <h2>Add a known company</h2>
          <p className="muted">
            Use a public company website. This creates a candidate for review
            without research API calls.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void act("discovery/import", {
                context: f.get("context"),
                companies: [
                  {
                    name: f.get("name"),
                    website: f.get("website"),
                    industry: f.get("industry") || "Unknown",
                    source: f.get("source") || "manual",
                    distance_miles: f.get("distance")
                      ? Number(f.get("distance"))
                      : null,
                  },
                ],
              });
            }}
          >
            <label>
              Company name
              <input name="name" required maxLength={255} />
            </label>
            <label>
              Official website
              <input
                name="website"
                type="url"
                placeholder="https://company.com"
                required
              />
            </label>
            <label>
              Industry
              <input name="industry" maxLength={100} />
            </label>
            <label>
              Source URL / note
              <input name="source" maxLength={500} />
            </label>
            <label>
              Distance (miles, if known)
              <input name="distance" type="number" min={0} step="any" />
            </label>
            <label>
              Context
              <input
                name="context"
                defaultValue="Personal internship search"
                maxLength={160}
              />
            </label>
            <button className="secondary" disabled={busy}>
              Queue candidate import
            </button>
          </form>
          <details className="inline-details">
            <summary>Research bounds</summary>
            <dl className="context-ledger">
              {Object.entries(caps.data?.limits || {}).map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <p className="muted">
              Cost values are conservative reservations, not invoices.{" "}
              {caps.data?.worker_note}
            </p>
          </details>
        </section>
      </div>
      <section className="section">
        <div className="section-heading">
          <h2>Company candidates</h2>
          <small>{visible.length} matching</small>
        </div>
        <div className="register-tools">
          <label>
            Search candidates
            <input
              type="search"
              value={query}
              onChange={(e) => filter("q", e.target.value)}
            />
          </label>
          <label>
            Status
            <select
              aria-label="Candidate status"
              value={status}
              onChange={(e) => filter("candidateStatus", e.target.value)}
            >
              {["candidate", "accepted", "ambiguous", "dismissed", "all"].map(
                (x) => (
                  <option key={x}>{x}</option>
                ),
              )}
            </select>
          </label>
          <label>
            Candidate order
            <select
              value={sort}
              onChange={(e) => filter("candidateSort", e.target.value)}
            >
              <option value="recent">Recently collected</option>
              <option value="name">Company name</option>
              <option value="distance">Reported distance</option>
            </select>
          </label>
          <label>
            Search scope
            <select
              value={scope}
              onChange={(e) => filter("scope", e.target.value)}
            >
              <option value="all">All contexts</option>
              {contexts.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
        <ErrorState error={rows.error} retry={rows.reload} />
        {rows.loading && !rows.data ? (
          <Loading />
        ) : !visible.length ? (
          <Empty title="No matching candidates">
            Try another filter or add a company with a public source.
          </Empty>
        ) : (
          visible.slice(0, 100).map((c) => (
            <article className="candidate-row" key={c.id}>
              <div>
                <h3>{c.name}</h3>
                <p className="muted">
                  {c.industry} ·{" "}
                  {c.distance_miles === null
                    ? "Distance unknown"
                    : `${c.distance_miles} mi reported`}{" "}
                  · collected {date(c.updated_at)}
                </p>
                <Status value={c.status} />
                <p>
                  <External href={c.website}>{c.domain}</External>
                </p>
                <details className="inline-details">
                  <summary>Inspect field sources</summary>
                  {c.observations.map((o, i) => (
                    <p key={i}>
                      {text(o.field)}: {text(o.value)} · {text(o.confidence)} ·{" "}
                      {date(text(o.retrieved_at))}{" "}
                      {text(o.source_url) && (
                        <External href={text(o.source_url)}>Source</External>
                      )}
                    </p>
                  ))}
                  <p className="muted">
                    Industry and location are reported lead context; facts and
                    contact confidence still need research.
                  </p>
                </details>
              </div>
              <div className="candidate-actions">
                {c.company_id ? (
                  <Link
                    className="secondary"
                    href={`/?view=prospects&company=${c.company_id}`}
                  >
                    Inspect prospect
                  </Link>
                ) : c.status !== "dismissed" ? (
                  <>
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => act(`discovery/candidates/${c.id}/accept`)}
                    >
                      Accept {c.name}
                    </button>
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() =>
                        act(`discovery/candidates/${c.id}/dismiss`)
                      }
                    >
                      Dismiss {c.name}
                    </button>
                  </>
                ) : null}
              </div>
            </article>
          ))
        )}
      </section>
      <IntelligenceJobs />
    </>
  );
}
