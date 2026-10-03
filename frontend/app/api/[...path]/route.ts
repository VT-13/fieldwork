import { NextRequest, NextResponse } from "next/server";
export const dynamic = "force-dynamic";
const MAX = 100_000;
async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  if (path.some((p) => !/^[-a-zA-Z0-9]+$/.test(p)))
    return NextResponse.json({ detail: "Invalid path" }, { status: 400 });
  const expected = process.env.APP_ORIGIN || "http://localhost:3000";
  if (
    !["GET", "HEAD"].includes(request.method) &&
    request.headers.get("origin") !== expected
  )
    return NextResponse.json(
      { detail: "Origin check failed" },
      { status: 403 },
    );
  if (Number(request.headers.get("content-length") || 0) > MAX)
    return NextResponse.json({ detail: "Request too large" }, { status: 413 });
  let payload: Uint8Array | undefined;
  if (!["GET", "HEAD"].includes(request.method) && request.body) {
    const reader = request.body.getReader();
    const parts: Uint8Array[] = [];
    let length = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX) {
        await reader.cancel();
        return NextResponse.json(
          { detail: "Request too large" },
          { status: 413 },
        );
      }
      parts.push(value);
    }
    payload = new Uint8Array(length);
    let offset = 0;
    for (const part of parts) {
      payload.set(part, offset);
      offset += part.byteLength;
    }
  }
  try {
    const headers: Record<string, string> = {
      Cookie: request.headers.get("cookie") || "",
    };
    for (const key of ["origin", "content-type", "sec-fetch-site"]) {
      const value = request.headers.get(key);
      if (value) headers[key] = value;
    }
    // Browser requests never inherit a privileged backend bearer key.
    const response = await fetch(
      `${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body: payload as BodyInit | undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(60000),
      },
    );
    if (path.join("/") === "integrations/gmail/callback" && response.ok)
      return NextResponse.redirect(new URL("/?gmail=connected", expected));
    const output = new NextResponse(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
    for (const cookie of response.headers.getSetCookie())
      output.headers.append("Set-Cookie", cookie);
    return output;
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable. Check service health." },
      { status: 502 },
    );
  }
}
export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
