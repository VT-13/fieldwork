"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, ArrowUpRight } from "lucide-react";
import type { CompanyView } from "../lib/contracts";
import { Empty, ErrorState, Loading, Status } from "./ui";
export default function Prospects({
  resource,
  campaign = false,
}: {
  resource: {
    data?: CompanyView[];
    error?: string;
    loading: boolean;
    reload: () => Promise<void>;
  };
  campaign?: boolean;
}) {
  const params = useSearchParams(),
    router = useRouter();
  const query = params.get("q") || "",
    stage = params.get("stage") || "all",
    sort = params.get("sort") || "fit";
  function update(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set(key, value);
    router.replace("/?" + next.toString(), { scroll: false });
  }
  const visible = (resource.data || [])
    .filter(
      (c) =>
        `${c.name} ${c.industry}`.toLowerCase().includes(query.toLowerCase()) &&
        (stage === "all" ||
          (stage === "review"
            ? c.stage === "drafted"
            : stage === "conversation"
              ? ["replied", "positive", "interview", "offer"].includes(c.stage)
              : c.stage === stage)),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name)
        : sort === "distance"
          ? (a.distance_miles ?? Infinity) - (b.distance_miles ?? Infinity)
          : b.score - a.score,
    );
  return (
    <section className="prospect-register">
      <div className="register-tools">
        <label className="search-field">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search companies</span>
          <input
            type="search"
            placeholder="Search companies or industries"
            value={query}
            onChange={(e) => update("q", e.target.value)}
          />
        </label>
        <label className="compact-field">
          Stage
          <select
            value={stage}
            onChange={(e) => update("stage", e.target.value)}
          >
            <option value="all">All stages</option>
            <option value="review">Ready for review</option>
            <option value="conversation">In conversation</option>
            <option value="discovered">Discovered</option>
            <option value="researched">Researched</option>
            <option value="bounce">Bounced</option>
          </select>
        </label>
        <label className="compact-field">
          Sort
          <select value={sort} onChange={(e) => update("sort", e.target.value)}>
            <option value="fit">Highest fit</option>
            <option value="name">Company name</option>
            <option value="distance">Nearest first</option>
          </select>
        </label>
      </div>
      <ErrorState error={resource.error} retry={resource.reload} />
      {resource.loading && !resource.data ? (
        <Loading />
      ) : (
        <>
          <div className="register-caption">
            <span>
              {visible.length}{" "}
              {campaign ? "targets in the workspace" : "prospects"}
            </span>
            <span>Scores guide research; they do not predict eligibility.</span>
          </div>
          <div className="register-heading" aria-hidden="true">
            <span>COMPANY / INDUSTRY</span>
            <span>FIT</span>
            <span>DISTANCE</span>
            <span>STAGE</span>
            <span />
          </div>
          <ul className="prospect-list">
            {visible.slice(0, 100).map((c) => (
              <li key={c.id}>
                <Link
                  className="prospect-row"
                  href={`/?view=${campaign ? "campaign" : "prospects"}&company=${c.id}`}
                >
                  <span className="prospect-identity">
                    <span className="company-monogram" aria-hidden="true">
                      {c.name
                        .split(" ")
                        .map((w) => w[0])
                        .slice(0, 2)
                        .join("")}
                    </span>
                    <span>
                      <strong>{c.name}</strong>
                      <small>
                        {c.industry}
                        {c.demo && " · Demo record"}
                      </small>
                    </span>
                  </span>
                  <span className="fit-score">
                    {c.score}
                    <small>/ 100</small>
                  </span>
                  <span className="distance">
                    {c.distance_miles === null
                      ? "Unverified"
                      : `${c.distance_miles} mi`}
                  </span>
                  <Status value={c.stage} />
                  <ArrowUpRight
                    className="row-arrow"
                    size={18}
                    aria-hidden="true"
                  />
                </Link>
              </li>
            ))}
          </ul>
          {!visible.length && (
            <Empty
              title={
                query || stage !== "all"
                  ? "No prospects match this view"
                  : "Your first prospect starts here"
              }
            >
              {query || stage !== "all"
                ? "Clear your search or choose all stages to see the rest of the pipeline."
                : "Add a company you’re interested in. Verified contacts and specific evidence come next."}
            </Empty>
          )}
          {visible.length > 100 && (
            <p className="muted">
              Showing the first 100 matches. Narrow your search to find a
              specific company.
            </p>
          )}
        </>
      )}
    </section>
  );
}
