"use client";
import { useCallback, useEffect, useSyncExternalStore } from "react";
import schemas from "./contracts.schema.json";
import type {
  PacketView,
  EmlView,
  SelfTestView,
  CampaignView,
  CompanyDetail,
  CompanyView,
  ConnectionView,
  InboxView,
  MetricsView,
  OutreachView,
  ProfileInput,
  SettingsView,
} from "./contracts";

type Views = {
  PacketView: PacketView;
  EmlView: EmlView;
  SelfTestView: SelfTestView;
  CampaignView: CampaignView;
  CompanyDetail: CompanyDetail;
  CompanyView: CompanyView;
  ConnectionView: ConnectionView;
  InboxView: InboxView;
  MetricsView: MetricsView;
  OutreachView: OutreachView;
  ProfileInput: ProfileInput;
  SettingsView: SettingsView;
};
type Schema = {
  $ref?: string;
  enum?: unknown[];
  anyOf?: Schema[];
  type?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  additionalProperties?: Schema | boolean;
  format?: string;
};
const definitions: Record<string, Schema> = schemas.$defs;

function valid(value: unknown, schema: Schema): boolean {
  if (schema.$ref)
    return valid(value, definitions[schema.$ref.split("/").at(-1)!]);
  if (schema.anyOf) return schema.anyOf.some((s) => valid(value, s));
  if (schema.enum) return schema.enum.includes(value);
  switch (schema.type) {
    case "null":
      return value === null;
    case "string":
      return (
        typeof value === "string" &&
        (schema.format !== "date-time" || Number.isFinite(Date.parse(value)))
      );
    case "boolean":
      return typeof value === "boolean";
    case "number":
      return typeof value === "number" && Number.isFinite(value);
    case "integer":
      return typeof value === "number" && Number.isInteger(value);
    case "array":
      return (
        Array.isArray(value) && value.every((v) => valid(v, schema.items || {}))
      );
    case "object": {
      if (!value || typeof value !== "object" || Array.isArray(value))
        return false;
      const obj: Record<string, unknown> = Object.fromEntries(
        Object.entries(value),
      );
      return (
        (schema.required || []).every((k) => Object.hasOwn(obj, k)) &&
        Object.entries(obj).every(([k, v]) => {
          const property = schema.properties?.[k];
          if (property) return valid(v, property);
          return typeof schema.additionalProperties === "object"
            ? valid(v, schema.additionalProperties)
            : true;
        })
      );
    }
    default:
      return true;
  }
}

export function decode<K extends keyof Views>(
  name: K,
  data: unknown,
  array: true,
): Views[K][];
export function decode<K extends keyof Views>(
  name: K,
  data: unknown,
  array?: false,
): Views[K];
export function decode<K extends keyof Views>(
  name: K,
  data: unknown,
  array: boolean | undefined,
): Views[K] | Views[K][];
export function decode<K extends keyof Views>(
  name: K,
  data: unknown,
  array = false,
): Views[K] | Views[K][] {
  if (
    !definitions[name] ||
    !(array
      ? Array.isArray(data) && data.every((v) => valid(v, definitions[name]))
      : valid(data, definitions[name]))
  ) {
    throw Error(
      "The server returned an unexpected response. Reload this section; if it continues, check the server version.",
    );
  }
  return data as Views[K] | Views[K][]; // Only after generated runtime contract validation.
}

export async function request(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch("/api/" + path, {
    method,
    signal,
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data: unknown = await response.json().catch(() => null);
  if (response.status === 401) {
    window.location.assign(new URL("/login", window.location.origin).href);
    throw Error("Your session expired. Sign in again.");
  }
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data ? data.detail : null;
    throw Error(
      typeof detail === "string"
        ? detail
        : `This action failed (${response.status}). Try again.`,
    );
  }
  if (method !== "GET") {
    if (path === "profile") invalidate("profile", "outreach");
    else if (path.startsWith("outreach/")) invalidate("outreach");
    else if (path.startsWith("companies")) invalidate("companies", "metrics");
    else if (path === "outreach-policy" || path === "campaign/stop")
      invalidate("campaign");
    else if (path === "integrations/gmail/disconnect")
      invalidate("campaign", "settings");
  }
  return data;
}

type Snapshot<T> = {
  data?: T;
  error?: string;
  loading: boolean;
  updated?: number;
};
type Entry = {
  snapshot: Snapshot<unknown>;
  listeners: Set<() => void>;
  pending?: Promise<void>;
  reload?: () => Promise<void>;
};
const cache = new Map<string, Entry>();
const empty: Snapshot<never> = { loading: true };
function entry(key: string): Entry {
  let value = cache.get(key);
  if (!value) {
    value = { snapshot: empty, listeners: new Set() };
    cache.set(key, value);
  }
  return value;
}
function notify(value: Entry) {
  value.listeners.forEach((fn) => fn());
}

export function useResource<K extends keyof Views, A extends boolean = false>(
  path: string,
  name: K,
  array?: A,
  poll = 0,
) {
  type Result = A extends true ? Views[K][] : Views[K];
  const key = name + ":" + path;
  const subscribe = useCallback(
    (fn: () => void) => {
      const e = entry(key);
      e.listeners.add(fn);
      return () => {
        e.listeners.delete(fn);
      };
    },
    [key],
  );
  const snapshot = useSyncExternalStore(
    subscribe,
    useCallback(() => entry(key).snapshot as Snapshot<Result>, [key]),
    () => empty,
  );
  const reload = useCallback(async () => {
    const e = entry(key);
    if (e.pending) return e.pending;
    e.snapshot = { ...e.snapshot, loading: true };
    notify(e);
    e.pending = request(path)
      .then((data) => {
        e.snapshot = {
          data: decode(name, data, array),
          loading: false,
          updated: Date.now(),
        };
      })
      .catch((error) => {
        e.snapshot = {
          ...e.snapshot,
          loading: false,
          error:
            error instanceof Error
              ? error.message
              : "Connection failed. Try again.",
        };
      })
      .finally(() => {
        e.pending = undefined;
        notify(e);
      });
    return e.pending;
  }, [key, path, name, array]);
  useEffect(() => {
    if (
      !entry(key).snapshot.updated ||
      Date.now() - entry(key).snapshot.updated! > 30000
    )
      void reload();
    entry(key).reload = reload;
    if (!poll) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void reload();
    }, poll);
    return () => clearInterval(timer);
  }, [key, reload, poll]);
  return { ...snapshot, reload };
}

export function invalidate(...paths: string[]) {
  for (const [key, e] of cache)
    if (paths.some((p) => key.endsWith(":" + p))) {
      e.snapshot = { ...e.snapshot, updated: 0 };
      notify(e);
      if (e.listeners.size && e.reload) {
        const reload = e.reload;
        void (e.pending || Promise.resolve()).then(() => reload());
      }
    }
}

export function safeLink(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    return ["https:", "http:"].includes(parsed.protocol) &&
      !parsed.username &&
      !parsed.password
      ? parsed.href
      : undefined;
  } catch {
    return undefined;
  }
}
export function date(value: string | null | undefined) {
  const time = value ? Date.parse(value) : NaN;
  return Number.isFinite(time)
    ? new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
      }).format(new Date(time))
    : "Not recorded";
}

export function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}
