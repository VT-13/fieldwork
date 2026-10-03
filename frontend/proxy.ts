import { NextRequest, NextResponse } from "next/server";
export function proxy(request: NextRequest) {
  const password = process.env.DASHBOARD_PASSWORD;
  if (!password && process.env.ALLOW_LOCAL_NO_AUTH === "true" && ["localhost", "127.0.0.1"].includes(request.nextUrl.hostname)) return NextResponse.next();
  if (!password) return new NextResponse("Set DASHBOARD_PASSWORD before serving this app.", {status:503});
  let supplied = "";
  try { supplied = atob((request.headers.get("authorization") || "").replace(/^Basic /, "")); } catch {}
  if (supplied !== `student:${password}`) return new NextResponse("Sign in to your private workspace", {status:401, headers:{"WWW-Authenticate":'Basic realm="Fieldwork", charset="UTF-8"'}});
  return NextResponse.next();
}
export const config = { matcher: ["/((?!_next/static|_next/image|favicon.svg).*)"] };
