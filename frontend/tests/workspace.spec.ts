import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import seed from "./fixture.json";
import type {
  CandidateView,
  JobView,
  CapabilitiesView,
  GenerationView,
  CampaignView,
  CompanyDetail,
  CompanyView,
  ConnectionView,
  InboxView,
  MetricsView,
  OutreachView,
  ProfileInput,
  SettingsView,
  MessageState,
} from "../lib/contracts";
import { decode, safeLink } from "../lib/api";
import { mkdirSync } from "node:fs";
const artifact =
  process.env.FIELDWORK_BROWSER_ARTIFACT_DIR || "../docs/module3";
type Fixture = {
  companies: CompanyView[];
  details: Record<string, CompanyDetail>;
  outreach: OutreachView[];
  profile: ProfileInput;
  responses: InboxView;
  metrics: MetricsView;
  settings: SettingsView;
  campaign: CampaignView;
  connection: ConnectionView;
  desk: unknown[];
  candidates: CandidateView[];
  jobs: JobView[];
  capabilities: CapabilitiesView;
  generations: Record<string, GenerationView[]>;
};
const base: Fixture = seed as Fixture;
async function mock(page: Page, data: Fixture = structuredClone(base)) {
  const attempts: string[] = [],
    reads: string[] = [];
  await page.context().addCookies([
    {
      name: "fieldwork_session",
      value: "synthetic-browser-fixture",
      url: "http://localhost:13030",
    },
  ]);
  await page.route("**/api/**", async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname.slice(5);
    const method = req.method();
    if (
      /(\/send$|self-test|\/mailbox$|integrations\/gmail\/(connect|disconnect)|^discover$|actions)/.test(
        path,
      )
    ) {
      attempts.push(path);
      await route.fulfill({
        status: 409,
        json: { detail: "No external operation is permitted in browser QA" },
      });
      return;
    }
    if (method === "GET") reads.push(path);
    let payload: unknown;
    if (path === "discovery/candidates") payload = data.candidates;
    else if (path === "intelligence/capabilities") payload = data.capabilities;
    else if (path === "jobs") payload = data.jobs;
    else if (path === "discovery/import") payload = data.jobs[0];
    else if (path.startsWith("jobs/") && path.endsWith("/stop")) {
      const job = data.jobs.find((j) => j.id === path.split("/")[1])!;
      job.status = "blocked";
      job.error = "Stopped by operator";
      job.payload.stop_requested = true;
      payload = job;
    } else if (path.startsWith("discovery/candidates/") && method === "POST") {
      const c = data.candidates.find((c) => c.id === path.split("/")[2])!;
      if (path.endsWith("/accept")) {
        c.status = "accepted";
        c.company_id = "qa-company-2";
        payload = data.companies[2];
      } else {
        c.status = "dismissed";
        payload = c;
      }
    } else if (path.startsWith("companies/") && path.endsWith("/generations"))
      payload = data.generations[path.split("/")[1]];
    else if (path === "companies") payload = data.companies;
    else if (path.startsWith("companies/"))
      payload = data.details[path.slice(10) as keyof typeof data.details];
    else if (path === "integrations/gmail") payload = data.connection;
    else if (path === "outreach-policy" && method === "PUT") {
      data.campaign.ongoing_policy.enabled = false;
      payload = { paused: true };
    } else if (path === "campaign/stop") {
      data.campaign.stop_requested = true;
      payload = { stop_requested: true };
    } else if (path.startsWith("outreach/")) {
      const [, id, action, decision] = path.split("/");
      const m = data.outreach.find((row) => row.id === id)!;
      if (method === "PATCH") {
        Object.assign(m, req.postDataJSON());
        m.status = "draft";
        m.review.passed = false;
        m.review.issues = [
          "Message edited. Regenerate to run quality review before approval.",
        ];
      } else
        m.status =
          action === "approve"
            ? "approved"
            : decision === "reject"
              ? "rejected"
              : "draft";
      payload = m;
    } else if (path.startsWith("responses/") && method === "PUT") {
      const reply = data.responses.responses.find(
        (r) => r.id === path.slice(10),
      );
      if (reply) reply.handled = Boolean(req.postDataJSON().handled);
      data.responses.needs_attention = data.responses.responses.filter(
        (r) => r.kind === "reply" && !r.handled,
      ).length;
      payload = {};
    } else if (path === "responses/sync") payload = { status: "queued" };
    else if (path === "profile" && method === "PUT") {
      data.profile = req.postDataJSON();
      payload = data.profile;
    } else payload = data[path as keyof Fixture];
    await route.fulfill({
      status: payload === undefined ? 404 : 200,
      json: payload ?? { detail: "Fixture route missing" },
    });
  });
  return { data, attempts, reads };
}
test("generated contracts reject malformed data and unsafe source links", () => {
  expect(() =>
    decode("CompanyView", [{ name: "Missing fields" }], true),
  ).toThrow("unexpected response");
  expect(() =>
    decode("OutreachView", { ...base.outreach[0], status: "invented" }),
  ).toThrow();
  expect(safeLink("javascript:alert(1)")).toBeUndefined();
  expect(safeLink("https://user:pass@example.com")).toBeUndefined();
});
test("workspace renders with fictional records", async ({ page }) => {
  await mock(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Good to see you/ }),
  ).toBeVisible();
  await expect(
    page.getByText("A conversation is waiting for you."),
  ).toBeVisible();
  mkdirSync(artifact, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 1024 });
  await page.screenshot({
    path: `${artifact}/smoke-dashboard-desktop.png`,
    fullPage: true,
  });
  await page.goto("/?view=review&message=qa-message-0");
  await expect(page.getByLabel("Email body")).toHaveValue(/Hi Jordan/);
  await page.screenshot({
    path: `${artifact}/smoke-review-desktop.png`,
    fullPage: true,
  });
});
test("flagship navigation, URL filters and command palette work by keyboard", async ({
  page,
}) => {
  const fixture = await mock(page);
  await page.goto("/");
  await page
    .getByRole("navigation", { name: "Workspace", exact: true })
    .getByRole("link", { name: "Prospects" })
    .click();
  await page.getByLabel("Search companies").fill("Aster");
  await expect(page.locator(".prospect-list li")).toHaveCount(1);
  await page.reload();
  await expect(page.getByLabel("Search companies")).toHaveValue("Aster");
  await page.getByRole("link", { name: /Aster Robotics/ }).click();
  await expect(
    page.getByRole("heading", { name: "Evidence behind the introduction" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Jordan Lee (fictional)", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Meta+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByLabel("Search prospects and actions").fill("Campaign");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/view=campaign/);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Find a prospect or action" }).click();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Find a prospect or action" }),
  ).toBeFocused();
  expect(fixture.attempts).toEqual([]);
});
test("pause is database-authoritative even with no active batch; failed pause is not optimistic", async ({
  page,
}) => {
  const d = structuredClone(base);
  d.campaign.ongoing_policy.enabled = true;
  await mock(page, d);
  await page.goto("/?view=campaign");
  await expect(
    page.getByText("Recurring outreach is enabled", { exact: true }),
  ).toBeVisible();
  await page.route("**/api/outreach-policy", (route) =>
    route.fulfill({ status: 503, json: { detail: "Database unavailable" } }),
  );
  await page.getByRole("button", { name: "Pause recurring outreach" }).click();
  await expect(page.getByText("Database unavailable")).toBeVisible();
  await expect(
    page.getByText("Recurring outreach is enabled", { exact: true }),
  ).toBeVisible();
  await page.unroute("**/api/outreach-policy");
  await page.getByRole("button", { name: "Pause recurring outreach" }).click();
  await expect(
    page.getByText("Recurring outreach is paused", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Resume/ })).toHaveCount(0);
});
test("review supports approval, return for changes, return to draft and edits that invalidate review", async ({
  page,
}) => {
  const { data, attempts } = await mock(page);
  await page.goto("/?view=review&message=qa-message-0");
  await expect(
    page.getByText(
      "The fixture team is building a vision dashboard for operators.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve saved draft" }).click();
  await expect(page.locator(".review-heading")).toContainText(
    "Approved · unsent",
  );
  await page.getByRole("button", { name: "Return for changes" }).click();
  await expect(page.locator(".review-heading")).toContainText(
    "Returned for changes",
  );
  await page.getByRole("button", { name: "Return to draft" }).click();
  await expect(
    page.getByRole("button", { name: "Approve saved draft" }),
  ).toBeEnabled();
  await page
    .getByLabel("Subject", { exact: true })
    .fill("A more personal idea for the dashboard");
  await expect(
    page.getByRole("button", { name: "Approve saved draft" }),
  ).toBeDisabled();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("link", { name: "Full prospect context" }).click();
  await expect(page).toHaveURL(/view=review/);
  await page.getByRole("button", { name: "Save edits" }).click();
  await expect(
    page.getByRole("button", { name: "Approve saved draft" }),
  ).toBeDisabled();
  expect(data.outreach[0].review.passed).toBe(false);
  expect(attempts).toEqual([]);
});
test("sent and uncertain messages are locked and never offer retry/send", async ({
  page,
}) => {
  const data = structuredClone(base);
  data.outreach[1].status = "unknown" as MessageState;
  await mock(page, data);
  await page.goto("/?view=review&message=qa-message-1");
  await expect(
    page.getByText("Delivery is uncertain. Do not resend.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Email body")).toHaveAttribute("readonly", "");
  await expect(
    page.getByRole("button", { name: /Send|Retry|Approve/ }),
  ).toHaveCount(0);
});
test("localized loading, empty, failed reads and retry are usable", async ({
  page,
}) => {
  await mock(page);
  let fail = true;
  await page.route("**/api/companies", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({
      status: fail ? 503 : 200,
      json: fail ? { detail: "Prospect service unavailable" } : [],
    });
  });
  await page.goto("/?view=prospects");
  await expect(
    page.getByRole("status", { name: "Loading this section" }),
  ).toBeVisible();
  await expect(
    page.getByText("Prospect service unavailable", { exact: true }),
  ).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByText("Your first prospect starts here", { exact: true }),
  ).toBeVisible();
});
test("profile form uses native validation and retains edits through failed save", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/?view=profile");
  await page.getByLabel("Name", { exact: true }).fill("");
  await page.getByRole("button", { name: "Save profile" }).click();
  expect(
    await page
      .getByLabel("Name", { exact: true })
      .evaluate((el: HTMLInputElement) => el.validity.valid),
  ).toBe(false);
  await page.getByLabel("Name", { exact: true }).fill("Vihaan QA edited");
  await page.route("**/api/profile", (route) =>
    route.fulfill({ status: 503, json: { detail: "Save unavailable" } }),
  );
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("Save unavailable")).toBeVisible();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
    "Vihaan QA edited",
  );
});
test("reply handling refreshes attention without sending or reading Gmail", async ({
  page,
}) => {
  const { data, attempts } = await mock(page);
  await page.goto("/?view=responses");
  await page.getByRole("button", { name: "Mark handled" }).click();
  await expect(
    page.getByRole("heading", { name: "0 replies need your attention" }),
  ).toBeVisible();
  expect(data.responses.responses[0].handled).toBe(true);
  expect(attempts).toEqual([]);
});
test("responsive flagship screenshots, contrast and semantic accessibility", async ({
  page,
}) => {
  test.setTimeout(90000); // Sixteen screenshot + axe scans, not an application response timeout.
  await mock(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const [width, height, label] of [
    [1728, 1117, "wide"],
    [1280, 900, "laptop"],
    [768, 1024, "tablet"],
    [390, 844, "mobile"],
  ] as const) {
    await page.setViewportSize({ width, height });
    for (const [view, suffix] of [
      ["dashboard", ""],
      ["prospects", "&company=qa-company-0"],
      ["campaign", ""],
      ["review", "&message=qa-message-0"],
    ]) {
      await page.goto(`/?view=${view}${suffix}`);
      await expect(page.locator("h1")).toBeVisible();
      await expect(page.locator(".loading")).toHaveCount(0);
      await page.screenshot({
        path: `${artifact}/${view}-${label}.png`,
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      const a11y = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(a11y.violations).toEqual([]);
    }
  }
  expect(errors).toEqual([]);
});

test("editor expands on viewport changes and decision controls precede the reading surface", async ({
  page,
}) => {
  await mock(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/?view=review&message=qa-message-0");
  const editor = page.getByLabel("Email body");
  await expect(editor).toHaveValue(/Fictional browser QA/);
  const decision = await page
    .getByRole("region", { name: "Review decision" })
    .boundingBox();
  const paper = await page.locator(".email-paper").boundingBox();
  expect(decision!.y + decision!.height).toBeLessThanOrEqual(paper!.y);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(async () =>
      editor.evaluate(
        (element: HTMLTextAreaElement) =>
          element.scrollHeight <= element.clientHeight + 2,
      ),
    )
    .toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(
    await page
      .locator(".primary")
      .first()
      .evaluate((el) => getComputedStyle(el).transitionDuration),
  ).toBe("0s");
});

test("resource reads are deduplicated and secondary screens retain the shared visual language", async ({
  page,
}) => {
  const { reads } = await mock(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Good to see you/ }),
  ).toBeVisible();
  await expect(page.locator(".loading")).toHaveCount(0);
  expect(reads.filter((path) => path === "responses")).toHaveLength(1);
  expect(reads.filter((path) => path === "companies")).toHaveLength(1);
  expect(reads.filter((path) => path === "campaign")).toHaveLength(1);
  for (const view of ["settings", "profile", "responses", "desk"]) {
    await page.goto("/?view=" + view);
    await expect(page.locator("h1")).toBeVisible();
    await expect(page.locator(".loading")).toHaveCount(0);
    const scan = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(scan.violations).toEqual([]);
  }
});

test("discovery accepts candidates deliberately, retains URL filters and stops bounded work", async ({
  page,
}) => {
  const fixture = await mock(page);
  await page.goto("/?view=discovery");
  await expect(
    page.getByRole("heading", { name: "Find a team worth meeting." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Queue bounded search" }),
  ).toBeDisabled();
  await page.getByLabel("Search candidates").fill("Willow");
  await page.reload();
  await expect(page.getByLabel("Search candidates")).toHaveValue("Willow");
  await expect(
    page.getByRole("heading", { name: "Willow Robotics (Demo)" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Accept Willow Robotics (Demo)" })
    .click();
  await expect(
    page.getByText(
      "Prospect accepted. Research and review still come before approval.",
    ),
  ).toBeVisible();
  expect(fixture.data.candidates[0].status).toBe("accepted");
  expect(fixture.data.outreach).toHaveLength(2);
  await page
    .getByRole("combobox", { name: "Candidate status" })
    .selectOption("accepted");
  await expect(
    page.getByRole("link", { name: "Inspect prospect" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Stop research" }).click();
  await expect(page.getByText("Stopped by operator")).toBeVisible();
  expect(fixture.attempts).toEqual([]);
});

test("discovery failure, empty state and no-provider manual import keep user input", async ({
  page,
}) => {
  await mock(page);
  await page.goto("/?view=discovery");
  await page
    .getByLabel("Company name", { exact: true })
    .fill("QA student company");
  await page.getByLabel("Official website").fill("https://candidate.example");
  await page.route("**/api/discovery/import", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "Import temporarily unavailable" },
    }),
  );
  await page.getByRole("button", { name: "Queue candidate import" }).click();
  await expect(page.getByText("Import temporarily unavailable")).toBeVisible();
  await expect(page.getByLabel("Company name", { exact: true })).toHaveValue(
    "QA student company",
  );
  await page.getByLabel("Search candidates").fill("No matching fixture");
  await expect(
    page.getByRole("heading", { name: "No matching candidates" }),
  ).toBeVisible();
});

test("discovery and intelligence provenance are accessible at laptop and phone sizes", async ({
  page,
}) => {
  await mock(page);
  mkdirSync("../docs/module4", { recursive: true });
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/?view=discovery");
    await expect(
      page.getByRole("heading", { name: "Company candidates" }),
    ).toBeVisible();
    await page.getByText("Inspect field sources").click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(results.violations).toEqual([]);
    await page.evaluate(() => {
      if (document.activeElement instanceof HTMLElement)
        document.activeElement.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: `../docs/module4/discovery-${width}.png`,
      fullPage: true,
    });
    await page.goto("/?view=prospects&company=qa-company-0");
    await expect(
      page.getByRole("heading", { name: "Build the evidence, then write." }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Generate for review" }),
    ).toBeDisabled();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.evaluate(() => {
      if (document.activeElement instanceof HTMLElement)
        document.activeElement.blur();
      window.scrollTo(0, 0);
    });
    await page.screenshot({
      path: `../docs/module4/prospect-${width}.png`,
      fullPage: true,
    });
  }
});

test("research failure keeps evidence inspectable and generation errors cannot be approved", async ({
  page,
}) => {
  const d = structuredClone(base);
  d.details["qa-company-0"].demo = false;
  d.capabilities.paid_allowed = true;
  d.capabilities.providers.forEach((p) => {
    if (["research", "generate"].includes(p.id)) {
      p.available = true;
      p.configured = true;
    }
  });
  await mock(page, d);
  await page.route("**/api/companies/qa-company-0/actions/research", (route) =>
    route.fulfill({
      status: 409,
      json: { detail: "Provider unavailable; partial evidence retained" },
    }),
  );
  await page.goto("/?view=prospects&company=qa-company-0");
  await page.getByRole("button", { name: "Queue research" }).click();
  await expect(
    page.getByText("Provider unavailable; partial evidence retained"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence behind the introduction" }),
  ).toBeVisible();
  d.outreach[0].status = "rejected";
  d.outreach[0].review.passed = false;
  d.outreach[0].review.issues = ["Unsupported student fact reference"];
  await page.goto("/?view=review&message=qa-message-0");
  await expect(
    page.getByText("Unsupported student fact reference"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Approve saved draft" }),
  ).toBeDisabled();
});

test("explicit regeneration queues a new version without changing saved content or sending", async ({
  page,
}) => {
  const d = structuredClone(base);
  d.details["qa-company-0"].demo = false;
  d.capabilities.paid_allowed = true;
  d.capabilities.providers.find((p) => p.id === "generate")!.available = true;
  const fixture = await mock(page, d),
    saved = d.outreach[0].body;
  await page.route("**/api/outreach/qa-message-0/regenerate", (route) =>
    route.fulfill({
      status: 202,
      json: {
        ...d.jobs[0],
        id: "qa-generation-job",
        kind: "regenerate",
        status: "queued",
      },
    }),
  );
  await page.goto("/?view=review&message=qa-message-0");
  await page.getByRole("button", { name: "Regenerate for review" }).click();
  await expect(
    page.getByText(/Regeneration queued as a new version/),
  ).toBeVisible();
  await expect(page.getByLabel("Email body")).toHaveValue(saved);
  expect(d.outreach[0].status).toBe("draft");
  expect(fixture.attempts).toEqual([]);
});
