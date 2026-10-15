/**
 * Bali Fuel Crisis Analyst — Cloudflare Worker
 * Berperan sebagai:
 * 1. Papan data publik (/latest/<key>) dengan CORS & ETag caching
 * 2. Penyimpan data ingest (/ingest/<key>) & state privat (/state/<key>)
 * 3. Pemicu otomatis (Cron Trigger 10m) -> GitHub API workflow_dispatch
 */

const KEY_WHITELIST = new Set([
  "meta.json",
  "summary.json",
  "stations.json",
  "history.json",
  "balifuel.db"
]);

const MAX_JSON_BYTES = 5 * 1024 * 1024;    // 5 MB
const MAX_DB_BYTES = 50 * 1024 * 1024;     // 50 MB

// Portable constant-time comparison (timing-attack resistant)
function timingSafeEqual(a, b) {
  if (a.byteLength !== b.byteLength) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.byteLength; i++) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

function verifyToken(authHeader, expectedToken) {
  if (!authHeader || !authHeader.startsWith("Bearer ") || !expectedToken) {
    return false;
  }
  const token = authHeader.slice(7).trim();
  const enc = new TextEncoder();
  const a = enc.encode(token);
  const b = enc.encode(expectedToken);
  return timingSafeEqual(a, b);
}

function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...extraHeaders
    }
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, If-None-Match",
    "Access-Control-Expose-Headers": "ETag, Content-Type, Content-Length",
    "Access-Control-Max-Age": "86400"
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    // 1. CORS Preflight
    if (method === "OPTIONS") {
      if (path.startsWith("/latest/") || path === "/debug") {
        return new Response(null, { status: 204, headers: corsHeaders() });
      }
      return new Response(null, { status: 405 });
    }

    // 2. Public Debug Telemetry: GET /debug
    if (path === "/debug" && method === "GET") {
      const now = new Date();
      const metaObj = await env.BUCKET.get("latest/meta.json");
      let meta = null;
      if (metaObj) {
        try { meta = await metaObj.json(); } catch (e) {}
      }

      const keys = ["latest/meta.json", "latest/summary.json", "latest/stations.json", "latest/history.json", "state/balifuel.db"];
      const r2Status = {};
      for (const k of keys) {
        const obj = await env.BUCKET.get(k);
        r2Status[k] = obj ? { exists: true, size: obj.size, etag: obj.etag, uploaded: obj.uploaded } : { exists: false };
      }

      return jsonResponse({
        status: "healthy",
        worker_time_utc: now.toISOString(),
        worker_time_wita: new Date(now.getTime() + 8 * 3600 * 1000).toISOString().replace("Z", "+08:00"),
        latest_meta: meta,
        r2_storage: r2Status,
        cron_schedule: "*/10 * * * * (Every 10 minutes)"
      }, 200, corsHeaders());
    }

    // 3. Public Data Board: GET /latest/<key>
    if (path.startsWith("/latest/")) {
      if (method !== "GET") {
        return jsonResponse({ error: "Method Not Allowed" }, 405, corsHeaders());
      }
      const key = path.slice("/latest/".length);
      if (!KEY_WHITELIST.has(key)) {
        return jsonResponse({ error: "Key not allowed or not found" }, 404, corsHeaders());
      }

      const r2Key = `latest/${key}`;
      const object = await env.BUCKET.get(r2Key);
      if (!object) {
        return jsonResponse({ error: "Object not found" }, 404, corsHeaders());
      }

      // Check conditional If-None-Match
      const clientEtag = request.headers.get("If-None-Match");
      if (clientEtag && (clientEtag === object.etag || clientEtag === `W/"${object.etag}"`)) {
        return new Response(null, {
          status: 304,
          headers: {
            "ETag": object.etag,
            "Cache-Control": "public, max-age=60",
            ...corsHeaders()
          }
        });
      }

      const headers = new Headers();
      headers.set("ETag", object.etag);
      headers.set("Cache-Control", "public, max-age=60");
      headers.set("Content-Type", key.endsWith(".json") ? "application/json; charset=utf-8" : "application/octet-stream");
      headers.set("Content-Length", String(object.size));
      Object.entries(corsHeaders()).forEach(([k, v]) => headers.set(k, v));

      return new Response(object.body, { status: 200, headers });
    }

    // 3. Authenticated Ingest: PUT /ingest/<key>
    if (path.startsWith("/ingest/")) {
      if (method !== "PUT") {
        return jsonResponse({ error: "Method Not Allowed" }, 405);
      }
      const auth = await verifyToken(request.headers.get("Authorization"), env.INGEST_TOKEN);
      if (!auth) {
        return jsonResponse({ error: "Unauthorized" }, 401);
      }

      const key = path.slice("/ingest/".length);
      if (!KEY_WHITELIST.has(key)) {
        return jsonResponse({ error: "Key not allowed" }, 400);
      }

      const contentLength = parseInt(request.headers.get("Content-Length") || "0", 10);
      const maxLimit = key.endsWith(".db") ? MAX_DB_BYTES : MAX_JSON_BYTES;
      if (contentLength > maxLimit) {
        return jsonResponse({ error: `Payload too large. Max allowed: ${maxLimit} bytes` }, 413);
      }

      const r2Key = `latest/${key}`;
      const obj = await env.BUCKET.put(r2Key, request.body, {
        httpMetadata: {
          contentType: key.endsWith(".json") ? "application/json" : "application/octet-stream"
        }
      });

      return jsonResponse({
        ok: true,
        key: key,
        etag: obj.etag,
        size: obj.size
      });
    }

    // 4. Private State Sync: GET|PUT /state/<key> (No CORS)
    if (path.startsWith("/state/")) {
      const auth = await verifyToken(request.headers.get("Authorization"), env.INGEST_TOKEN);
      if (!auth) {
        return jsonResponse({ error: "Unauthorized" }, 401);
      }

      const key = path.slice("/state/".length);
      if (!KEY_WHITELIST.has(key)) {
        return jsonResponse({ error: "Key not allowed" }, 400);
      }

      const r2Key = `state/${key}`;

      if (method === "GET") {
        const object = await env.BUCKET.get(r2Key);
        if (!object) {
          return jsonResponse({ error: "State object not found" }, 404);
        }
        const headers = new Headers();
        headers.set("Content-Type", "application/octet-stream");
        headers.set("Content-Length", String(object.size));
        headers.set("ETag", object.etag);
        return new Response(object.body, { status: 200, headers });
      }

      if (method === "PUT") {
        const contentLength = parseInt(request.headers.get("Content-Length") || "0", 10);
        if (contentLength > MAX_DB_BYTES) {
          return jsonResponse({ error: `State too large. Max: ${MAX_DB_BYTES} bytes` }, 413);
        }
        const obj = await env.BUCKET.put(r2Key, request.body, {
          httpMetadata: { contentType: "application/octet-stream" }
        });
        return jsonResponse({ ok: true, key: key, size: obj.size });
      }
      return jsonResponse({ error: "Method Not Allowed" }, 405);
    }

    // 5. Trigger Runner On-Demand: POST /trigger-runner (Bearer INGEST_TOKEN)
    if (path === "/trigger-runner") {
      if (method !== "POST") {
        return jsonResponse({ error: "Method Not Allowed" }, 405);
      }
      const auth = await verifyToken(request.headers.get("Authorization"), env.INGEST_TOKEN);
      if (!auth) {
        return jsonResponse({ error: "Unauthorized" }, 401);
      }
      const result = await triggerGitHubWorkflow(env);
      return jsonResponse(result, result.ok ? 200 : 502);
    }

    // Default Fallback
    return jsonResponse({ error: "Not Found", message: "BaliFuel Analyst Worker API" }, 404);
  },

  // Cron Trigger (every 10 minutes)
  async scheduled(event, env, ctx) {
    const res = await triggerGitHubWorkflow(env);
    console.log(`[Cron Trigger] Workflow dispatch:`, JSON.stringify(res));
  }
};

async function triggerGitHubWorkflow(env) {
  if (!env.GH_TOKEN || !env.GH_REPO) {
    return { ok: false, error: "GH_TOKEN or GH_REPO not configured in Worker" };
  }
  const url = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/pipeline.yml/dispatches`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "User-Agent": "BaliFuel-Worker/1.0",
        "Authorization": `Bearer ${env.GH_TOKEN}`,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ ref: "main" })
    });
    return {
      ok: res.status === 204 || res.status === 200,
      status: res.status,
      message: res.status === 204 ? "Workflow dispatch successful" : await res.text()
    };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}
