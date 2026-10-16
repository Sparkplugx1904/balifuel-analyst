/**
 * Bali Fuel Crisis Analyst — Cloudflare Worker v2
 * 1. Papan data publik GET /latest/<key> dengan CORS dan ETag caching
 * 2. Ingest privat PUT /ingest/<key> dan state sync GET|PUT /state/<key>
 * 3. Smart watchdog Cron setiap 10 menit — hanya picu runner bila benar-benar mati
 * 4. GET /health/runner — status pipeline real-time dari GitHub Actions API
 * 5. POST /trigger-runner — estafet: runner memanggil ini sebelum mati
 */

const KEY_WHITELIST = new Set([
  "meta.json",
  "summary.json",
  "stations.json",
  "history.json",
  "panic.json",
  "correlations.json",
  "sources.json",
  "balifuel.db"
]);

const MAX_JSON_BYTES = 5 * 1024 * 1024;   // 5 MB
const MAX_DB_BYTES   = 50 * 1024 * 1024;  // 50 MB

// Batas cooldown: jangan trigger baru bila run terakhir dimulai < N menit lalu
const RELAY_COOLDOWN_MINUTES = 30;

// ── Timing-safe token compare ──────────────────────────────────────────────
function timingSafeEqual(a, b) {
  if (a.byteLength !== b.byteLength) return false;
  let diff = 0;
  for (let i = 0; i < a.byteLength; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

function verifyToken(authHeader, expectedToken) {
  if (!authHeader || !authHeader.startsWith("Bearer ") || !expectedToken) return false;
  const enc = new TextEncoder();
  return timingSafeEqual(enc.encode(authHeader.slice(7).trim()), enc.encode(expectedToken));
}

function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...extraHeaders }
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization"
  };
}

// ── GitHub Actions API helpers ─────────────────────────────────────────────

/**
 * Ambil daftar run workflow terbaru dari GitHub Actions API.
 * Return: { runs: [...], active: bool, latest: run|null }
 */
async function getWorkflowStatus(env) {
  if (!env.GH_TOKEN || !env.GH_REPO) {
    return { ok: false, error: "GH_TOKEN or GH_REPO not configured" };
  }

  const url = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/pipeline.yml/runs?per_page=5`;
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": "BaliFuel-Worker/2.0",
        "Authorization": `Bearer ${env.GH_TOKEN}`,
        "Accept": "application/vnd.github+json"
      }
    });

    if (!res.ok) {
      return { ok: false, error: `GitHub API ${res.status}: ${await res.text()}` };
    }

    const data = await res.json();
    const runs = data.workflow_runs || [];
    const latest = runs[0] || null;

    // "aktif" = ada run yang in_progress atau queued atau waiting
    const activeStatuses = new Set(["in_progress", "queued", "waiting", "requested", "pending"]);
    const active = runs.some(r => activeStatuses.has(r.status));

    // Cooldown: run terakhir dimulai < RELAY_COOLDOWN_MINUTES menit lalu
    let inCooldown = false;
    if (latest && latest.created_at) {
      const ageMs = Date.now() - new Date(latest.created_at).getTime();
      inCooldown = ageMs < RELAY_COOLDOWN_MINUTES * 60 * 1000;
    }

    return {
      ok: true,
      active,
      inCooldown,
      latest: latest ? {
        id: latest.id,
        status: latest.status,
        conclusion: latest.conclusion,
        created_at: latest.created_at,
        html_url: latest.html_url
      } : null
    };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/**
 * Trigger GitHub Actions workflow_dispatch untuk pipeline.yml.
 * Hanya dipanggil setelah getWorkflowStatus memastikan tidak ada run aktif.
 */
async function triggerGitHubWorkflow(env) {
  if (!env.GH_TOKEN || !env.GH_REPO) {
    return { ok: false, error: "GH_TOKEN or GH_REPO not configured in Worker" };
  }

  const url = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/pipeline.yml/dispatches`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "User-Agent": "BaliFuel-Worker/2.0",
        "Authorization": `Bearer ${env.GH_TOKEN}`,
        "Accept": "application/vnd.github+json",
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

/**
 * Logika watchdog terpusat — dipakai oleh Cron dan /trigger-runner.
 * Mengecek status dulu, lalu memutuskan apakah perlu trigger.
 * @param {string} source - "cron" | "self-relay" | "manual"
 */
async function watchdogRelay(env, source = "cron") {
  const status = await getWorkflowStatus(env);

  if (!status.ok) {
    return { triggered: false, reason: `GitHub API error: ${status.error}`, source };
  }

  if (status.active) {
    return {
      triggered: false,
      reason: `Pipeline already active (status: ${status.latest?.status}). Skipped.`,
      latest: status.latest,
      source
    };
  }

  // Self-relay boleh bypass cooldown (runner tahu ia hampir mati)
  if (source !== "self-relay" && status.inCooldown) {
    return {
      triggered: false,
      reason: `In cooldown (latest run < ${RELAY_COOLDOWN_MINUTES}m ago). Skipped.`,
      latest: status.latest,
      source
    };
  }

  // Tidak ada run aktif & bukan cooldown → picu
  const result = await triggerGitHubWorkflow(env);
  return {
    triggered: result.ok,
    reason: result.ok ? "New runner triggered (estafet)" : `Trigger failed: ${result.message}`,
    trigger_result: result,
    latest: status.latest,
    source
  };
}

// ── Main fetch handler ─────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const url    = new URL(request.url);
    const path   = url.pathname;
    const method = request.method;

    // CORS Preflight
    if (method === "OPTIONS") {
      if (path.startsWith("/latest/") || path === "/debug" || path === "/health/runner") {
        return new Response(null, { status: 204, headers: corsHeaders() });
      }
      return new Response(null, { status: 405 });
    }

    // ── GET /health/runner ── Status pipeline real-time dari GitHub API ──────
    if (path === "/health/runner" && method === "GET") {
      const status = await getWorkflowStatus(env);
      return jsonResponse(
        {
          worker_time_utc: new Date().toISOString(),
          pipeline_status: status
        },
        status.ok ? 200 : 502,
        corsHeaders()
      );
    }

    // ── GET /debug ─────────────────────────────────────────────────────────
    if (path === "/debug" && method === "GET") {
      const now = new Date();
      const metaObj = await env.BUCKET.get("latest/meta.json");
      let meta = null;
      if (metaObj) { try { meta = await metaObj.json(); } catch (e) {} }

      const keys = ["latest/meta.json", "latest/summary.json", "latest/stations.json", "latest/history.json", "state/balifuel.db"];
      const r2Status = {};
      for (const k of keys) {
        const obj = await env.BUCKET.get(k);
        r2Status[k] = obj
          ? { exists: true, size: obj.size, etag: obj.etag, uploaded: obj.uploaded }
          : { exists: false };
      }

      const runnerStatus = await getWorkflowStatus(env);

      return jsonResponse({
        status: "healthy",
        worker_time_utc: now.toISOString(),
        worker_time_wita: new Date(now.getTime() + 8 * 3600 * 1000).toISOString().replace("Z", "+08:00"),
        latest_meta: meta,
        r2_storage: r2Status,
        runner: runnerStatus,
        cron_schedule: "*/10 * * * * (Every 10 minutes, smart watchdog)",
        relay_cooldown_minutes: RELAY_COOLDOWN_MINUTES
      }, 200, corsHeaders());
    }

    // ── GET /latest/<key> ── Public data board ─────────────────────────────
    if (path.startsWith("/latest/")) {
      if (method !== "GET") return jsonResponse({ error: "Method Not Allowed" }, 405, corsHeaders());
      const key = path.slice("/latest/".length);
      if (!KEY_WHITELIST.has(key)) return jsonResponse({ error: "Key not allowed or not found" }, 404, corsHeaders());

      const object = await env.BUCKET.get(`latest/${key}`);
      if (!object) return jsonResponse({ error: "Object not found" }, 404, corsHeaders());

      const clientEtag = request.headers.get("If-None-Match");
      if (clientEtag && (clientEtag === object.etag || clientEtag === `W/"${object.etag}"`)) {
        return new Response(null, {
          status: 304,
          headers: { "ETag": object.etag, "Cache-Control": "public, max-age=60", ...corsHeaders() }
        });
      }

      const headers = new Headers({
        "ETag": object.etag,
        "Cache-Control": "public, max-age=60",
        "Content-Type": key.endsWith(".json") ? "application/json; charset=utf-8" : "application/octet-stream",
        "Content-Length": String(object.size),
        ...corsHeaders()
      });
      return new Response(object.body, { status: 200, headers });
    }

    // ── PUT /ingest/<key> ── Authenticated ingest ──────────────────────────
    if (path.startsWith("/ingest/")) {
      if (method !== "PUT") return jsonResponse({ error: "Method Not Allowed" }, 405);
      if (!verifyToken(request.headers.get("Authorization"), env.INGEST_TOKEN))
        return jsonResponse({ error: "Unauthorized" }, 401);

      const key = path.slice("/ingest/".length);
      if (!KEY_WHITELIST.has(key)) return jsonResponse({ error: "Key not allowed" }, 400);

      const contentLength = parseInt(request.headers.get("Content-Length") || "0", 10);
      const maxLimit = key.endsWith(".db") ? MAX_DB_BYTES : MAX_JSON_BYTES;
      if (contentLength > maxLimit)
        return jsonResponse({ error: `Payload too large. Max: ${maxLimit} bytes` }, 413);

      const obj = await env.BUCKET.put(`latest/${key}`, request.body, {
        httpMetadata: { contentType: key.endsWith(".json") ? "application/json" : "application/octet-stream" }
      });
      return jsonResponse({ ok: true, key, etag: obj.etag, size: obj.size });
    }

    // ── GET|PUT /state/<key> ── Private state sync ─────────────────────────
    if (path.startsWith("/state/")) {
      if (!verifyToken(request.headers.get("Authorization"), env.INGEST_TOKEN))
        return jsonResponse({ error: "Unauthorized" }, 401);

      const key = path.slice("/state/".length);
      if (!KEY_WHITELIST.has(key)) return jsonResponse({ error: "Key not allowed" }, 400);
      const r2Key = `state/${key}`;

      if (method === "GET") {
        const object = await env.BUCKET.get(r2Key);
        if (!object) return jsonResponse({ error: "State object not found" }, 404);
        return new Response(object.body, {
          status: 200,
          headers: {
            "Content-Type": "application/octet-stream",
            "Content-Length": String(object.size),
            "ETag": object.etag
          }
        });
      }

      if (method === "PUT") {
        const contentLength = parseInt(request.headers.get("Content-Length") || "0", 10);
        if (contentLength > MAX_DB_BYTES)
          return jsonResponse({ error: `State too large. Max: ${MAX_DB_BYTES} bytes` }, 413);
        const obj = await env.BUCKET.put(r2Key, request.body, {
          httpMetadata: { contentType: "application/octet-stream" }
        });
        return jsonResponse({ ok: true, key, size: obj.size });
      }

      return jsonResponse({ error: "Method Not Allowed" }, 405);
    }

    // ── POST /trigger-runner ── Estafet manual / self-relay dari runner ─────
    if (path === "/trigger-runner") {
      if (method !== "POST") return jsonResponse({ error: "Method Not Allowed" }, 405);
      if (!verifyToken(request.headers.get("Authorization"), env.INGEST_TOKEN))
        return jsonResponse({ error: "Unauthorized" }, 401);

      // Baca source dari body opsional
      let source = "manual";
      try {
        const body = await request.json();
        source = body.source || "manual";
      } catch (e) {}

      const result = await watchdogRelay(env, source);
      return jsonResponse(result, result.triggered ? 200 : 200); // selalu 200, triggered field yang beda
    }

    return jsonResponse({ error: "Not Found", message: "BaliFuel Analyst Worker API v2" }, 404);
  },

  // ── Cron Trigger: */10 * * * * ── Smart watchdog ─────────────────────────
  async scheduled(event, env, ctx) {
    const result = await watchdogRelay(env, "cron");
    console.log(`[Cron Watchdog ${new Date().toISOString()}]`, JSON.stringify(result));
  }
};
