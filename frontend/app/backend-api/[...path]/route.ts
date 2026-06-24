import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function backendOrigin(): string | null {
  const raw = (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "").trim();
  if (!raw) {
    if (process.env.VERCEL) return null;
    return "http://127.0.0.1:8001";
  }
  let url = raw.replace(/\/api\/?$/i, "").replace(/\/$/, "");
  if (!/^https?:\/\//i.test(url)) {
    url = `https://${url}`;
  }
  return url;
}

async function proxy(req: NextRequest, pathSegments: string[]) {
  const origin = backendOrigin();
  if (!origin) {
    return NextResponse.json(
      {
        detail:
          "BACKEND_URL is not configured on Vercel. Set BACKEND_URL and NEXT_PUBLIC_API_URL to your Railway URL, then redeploy.",
      },
      { status: 503 }
    );
  }

  const subpath = pathSegments.join("/");
  const target = `${origin}/api/${subpath}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  const init: RequestInit = {
    method: req.method,
    headers,
    cache: "no-store",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  try {
    const upstream = await fetch(target, init);
    const body = await upstream.arrayBuffer();
    const response = new NextResponse(body, { status: upstream.status });
    const upstreamType = upstream.headers.get("content-type");
    if (upstreamType) response.headers.set("content-type", upstreamType);
    return response;
  } catch {
    return NextResponse.json(
      { detail: "Cannot reach the backend API. Set BACKEND_URL in Vercel environment variables." },
      { status: 502 }
    );
  }
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  return proxy(req, (await ctx.params).path);
}

export async function POST(req: NextRequest, ctx: RouteContext) {
  return proxy(req, (await ctx.params).path);
}

export async function PUT(req: NextRequest, ctx: RouteContext) {
  return proxy(req, (await ctx.params).path);
}

export async function PATCH(req: NextRequest, ctx: RouteContext) {
  return proxy(req, (await ctx.params).path);
}

export async function DELETE(req: NextRequest, ctx: RouteContext) {
  return proxy(req, (await ctx.params).path);
}
