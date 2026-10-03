import { NextRequest, NextResponse } from "next/server";
export const dynamic = "force-dynamic";
async function proxy(request:NextRequest, context:{params:Promise<{path:string[]}>}) {
  const {path} = await context.params;
  if (path.some(p=>!/^[-a-zA-Z0-9]+$/.test(p))) return NextResponse.json({detail:"Invalid path"},{status:400});
  if (!["GET","HEAD"].includes(request.method)) {
    const origin = request.headers.get("origin");
    const expected = process.env.APP_ORIGIN || request.nextUrl.origin;
    if (!origin || origin !== expected) return NextResponse.json({detail:"Origin check failed"},{status:403});
  }
  const payload = ["GET","HEAD"].includes(request.method) ? undefined : await request.text();
  if (payload && payload.length > 100000) return NextResponse.json({detail:"Request too large"},{status:413});
  try {
    const response = await fetch(`${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/${path.join("/")}${request.nextUrl.search}`, {
      method:request.method, headers:{"Authorization":`Bearer ${process.env.API_KEY || "local-development-key-change-me"}`,"Content-Type":"application/json"}, body:payload, cache:"no-store", signal:AbortSignal.timeout(15000)
    });
    return new NextResponse(await response.text(),{status:response.status,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
  } catch { return NextResponse.json({detail:"Backend unavailable. Start the API and run database migrations."},{status:502}); }
}
export {proxy as GET,proxy as POST,proxy as PUT,proxy as PATCH};
