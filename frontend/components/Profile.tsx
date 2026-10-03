"use client";
import { useState } from "react";
import type { ProfileInput } from "../lib/contracts";
import { request } from "../lib/api";
import { useUnsavedChanges } from "../lib/unsaved";
import { ErrorState, Header, Loading } from "./ui";
export default function Profile({
  resource,
}: {
  resource: {
    data?: ProfileInput;
    error?: string;
    loading: boolean;
    reload: () => Promise<void>;
  };
}) {
  return (
    <>
      <Header
        eyebrow="WORKSPACE / YOUR STORY"
        title="The experience behind your introduction."
      >
        Facts, projects and your own voice. Changes require pending messages to
        be reviewed again.
      </Header>
      <ErrorState error={resource.error} retry={resource.reload} />
      {resource.data ? (
        <ProfileForm
          key={resource.data.name + resource.data.verified}
          profile={resource.data}
          reload={resource.reload}
        />
      ) : resource.loading ? (
        <Loading />
      ) : null}
    </>
  );
}
function ProfileForm({
  profile,
  reload,
}: {
  profile: ProfileInput;
  reload: () => Promise<void>;
}) {
  const [form, setForm] = useState(profile),
    [saved, setSaved] = useState(profile),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  useUnsavedChanges(JSON.stringify(form) !== JSON.stringify(saved));
  return (
    <form
      className="profile-form"
      aria-label="My profile"
      aria-describedby={error ? "profile-error" : undefined}
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          await request("profile", "PUT", form);
          setSaved(form);
          setNotice("Profile saved. Pending approvals require review again.");
          await reload();
        } catch (err) {
          setError(
            err instanceof Error ? err.message : "Could not save profile",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <section className="section">
        <h2>Your introduction</h2>
        <div className="form-grid">
          {(
            ["name", "email", "grade", "location", "linkedin_url"] as const
          ).map((k) => (
            <label key={k}>
              {k === "linkedin_url"
                ? "LinkedIn URL"
                : k[0].toUpperCase() + k.slice(1)}
              <input
                required={k === "name"}
                type={
                  k === "email"
                    ? "email"
                    : k === "linkedin_url"
                      ? "url"
                      : "text"
                }
                value={form[k]}
                onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              />
            </label>
          ))}
        </div>
      </section>
      <section className="section">
        <h2>What you’ve done</h2>
        {(
          [
            "projects",
            "awards",
            "skills",
            "interests",
            "portfolio_links",
            "cover_letter_snippets",
          ] as const
        ).map((k) => (
          <label key={k}>
            {k.replaceAll("_", " ")}
            <small>One item per line</small>
            <textarea
              rows={3}
              value={form[k].join("\n")}
              onChange={(e) =>
                setForm({ ...form, [k]: e.target.value.split("\n") })
              }
            />
          </label>
        ))}
        <label>
          Resume text
          <textarea
            rows={7}
            maxLength={20000}
            value={form.resume}
            onChange={(e) => setForm({ ...form, resume: e.target.value })}
          />
        </label>
      </section>
      <section className="section">
        <h2>How you sound</h2>
        <label>
          Voice notes
          <textarea
            rows={3}
            maxLength={2000}
            value={form.voice_notes}
            onChange={(e) => setForm({ ...form, voice_notes: e.target.value })}
          />
        </label>
        <label>
          My own writing samples
          <small>Separate up to three samples with a line containing ---</small>
          <textarea
            rows={5}
            value={form.writing_samples.join("\n---\n")}
            onChange={(e) =>
              setForm({
                ...form,
                writing_samples: e.target.value.split("\n---\n").slice(0, 3),
              })
            }
          />
        </label>
        <label>
          Personal background
          <textarea
            rows={3}
            value={form.background}
            onChange={(e) => setForm({ ...form, background: e.target.value })}
          />
        </label>
      </section>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={form.verified}
          onChange={(e) => setForm({ ...form, verified: e.target.checked })}
        />
        I have checked these facts and links; messages may use them.
      </label>
      <ErrorState id="profile-error" error={error} />
      {notice && (
        <p className="alert" role="status">
          {notice}
        </p>
      )}
      <button className="primary" disabled={busy}>
        {busy ? "Saving…" : "Save profile"}
      </button>
    </form>
  );
}
