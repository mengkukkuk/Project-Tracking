/**
 * Cloudflare Worker that fronts the Vue SPA.
 *
 * - Static assets (the built SPA in ./dist) are served automatically by the
 *   [assets] binding; this code only runs for /api/* (see run_worker_first in
 *   wrangler.toml).
 * - For /api/*, it reverse-proxies to the Flask backend. The backend lives on a
 *   local Windows box exposed by a Cloudflare *quick tunnel*, whose URL is random
 *   and changes on every restart. That current URL is kept in KV under the key
 *   "backend_url", so the SPA/Worker never needs rebuilding when the tunnel rotates.
 */

export interface Env {
  CONFIG: KVNamespace;
  ASSETS: Fetcher;
}

// Headers that must not be forwarded verbatim between hops.
const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Defensive: anything that isn't /api/* is a static asset (SPA).
    if (!url.pathname.startsWith("/api/")) {
      return env.ASSETS.fetch(request);
    }

    const base = await env.CONFIG.get("backend_url");
    if (!base) {
      return json(
        { error: { message: "Backend URL not configured (KV 'backend_url' is empty)." } },
        503,
      );
    }

    const target = base.replace(/\/+$/, "") + url.pathname + url.search;

    const headers = new Headers(request.headers);
    for (const h of HOP_BY_HOP) headers.delete(h);
    headers.delete("host");

    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    const init: RequestInit = {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
    };
    // Required by the runtime when streaming a request body.
    if (hasBody) (init as RequestInit & { duplex: "half" }).duplex = "half";

    let upstream: Response;
    try {
      upstream = await fetch(target, init);
    } catch {
      return json(
        { error: { message: "Backend unreachable via tunnel." } },
        502,
      );
    }

    const respHeaders = new Headers(upstream.headers);
    for (const h of HOP_BY_HOP) respHeaders.delete(h);
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  },
};
