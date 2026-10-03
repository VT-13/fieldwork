import { NextRequest, NextResponse } from "next/server";
export function proxy(request: NextRequest) {
  const origin = process.env.APP_ORIGIN || "http://localhost:3000";
  if (request.nextUrl.host !== new URL(origin).host)
    return new NextResponse("Invalid host", { status: 400 });
  // Only FastAPI can authorize API access; cookie presence grants no authority.
  if (
    request.nextUrl.pathname.startsWith("/api/") ||
    request.nextUrl.pathname === "/login"
  )
    return NextResponse.next();
  if (!request.cookies.get("fieldwork_session"))
    return NextResponse.redirect(new URL("/login", origin));
  return NextResponse.next();
}
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.svg).*)"],
};
