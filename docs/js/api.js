// BaliFuel Analyst — Data API & Live Poller Module
(function () {
  let CURRENT_RUN_ID = null;
  let DATA_CACHE = null;
  let POLL_TIMER = null;
  let TICK_TIMER = null;
  let LAST_FETCH_AT = null;   // Date.now() saat fetch terakhir sukses
  let LAST_STATUS = "ok";     // "ok" | "degraded" | "stale" | "offline"
  const REFRESH_INTERVAL_MS = 60000;

  function getFeedUrl() {
    let u = window.FEED_URL || "https://balifuel-worker.anandapradnyana68.workers.dev";
    return u.replace(/\/+$/, "");
  }

  // ── Live ticker: dipanggil tiap 1 detik, menghitung umur riil ──────────────
  function formatElapsed(ms) {
    if (ms == null) return "?";
    const s = Math.floor(ms / 1000);
    if (s < 5)  return "baru saja";
    if (s < 60) return `${s} detik lalu`;
    const m = Math.floor(s / 60);
    const rs = s % 60;
    if (m < 60) return rs > 0 ? `${m}m ${rs}s lalu` : `${m} menit lalu`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}j ${rm}m lalu`;
  }

  function tickBadge() {
    const dot  = document.getElementById("statusDot");
    const text = document.getElementById("badgeText");
    const badge = document.getElementById("dataAgeBadge");
    if (!dot || !text || !badge) return;

    if (LAST_STATUS === "offline" || LAST_FETCH_AT === null) {
      dot.style.background  = "var(--danger)";
      badge.style.borderColor = "var(--danger)";
      text.textContent = "OFFLINE // FALLBACK";
      return;
    }

    const ageMs = Date.now() - LAST_FETCH_AT;
    const ageSec = Math.floor(ageMs / 1000);
    const elapsed = formatElapsed(ageMs);

    // Warna dot berdasarkan umur data riil
    if (ageSec < 90) {
      dot.style.background    = "var(--success)";   // hijau — segar
      badge.style.borderColor = "var(--line-strong)";
    } else if (ageSec < 300) {
      dot.style.background    = "var(--warning)";   // kuning — agak lama
      badge.style.borderColor = "var(--warning)";
    } else {
      dot.style.background    = "var(--danger)";    // merah — data stale
      badge.style.borderColor = "var(--danger)";
    }

    // Label status + elapsed nyata
    const prefix = LAST_STATUS === "degraded" ? "DEGRADED" : "LIVE";
    text.textContent = `${prefix} · ${elapsed}`;
  }

  function startTicker() {
    clearInterval(TICK_TIMER);
    TICK_TIMER = setInterval(tickBadge, 1000);
    tickBadge(); // langsung tampil tanpa tunggu 1 detik
  }

  // ── Fetch helpers ─────────────────────────────────────────────────────────
  async function fetchJson(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
    const raw = await res.text();
    const sanitized = raw.replace(/:\s*NaN\b/g, ": null").replace(/:\s*[-]?Infinity\b/g, ": null");
    return JSON.parse(sanitized);
  }

  // ── Data loader ───────────────────────────────────────────────────────────
  async function loadData() {
    const feed = getFeedUrl();

    // 1. Data tertanam (Local Target / dashboard.html mandiri)
    if (window.BALI_EMBEDDED_DATA) {
      DATA_CACHE = window.BALI_EMBEDDED_DATA;
      LAST_FETCH_AT = Date.now();
      LAST_STATUS   = "ok";
      window.dispatchEvent(new CustomEvent("dataupdated", { detail: DATA_CACHE }));
      startTicker();
      return;
    }

    // 2. Fetch dari Cloudflare Worker
    if (feed) {
      try {
        const meta = await fetchJson(`${feed}/latest/meta.json`);
        LAST_FETCH_AT = Date.now();
        LAST_STATUS   = meta.status || "ok";
        startTicker();

        if (meta.run_id !== CURRENT_RUN_ID) {
          CURRENT_RUN_ID = meta.run_id;
          const [summary, stations, panic, correlations, sources] = await Promise.all([
            fetchJson(`${feed}/latest/summary.json`),
            fetchJson(`${feed}/latest/stations.json`),
            fetchJson(`${feed}/latest/panic.json`).catch(() => null),
            fetchJson(`${feed}/latest/correlations.json`).catch(() => null),
            fetchJson(`${feed}/latest/sources.json`).catch(() => null)
          ]);
          DATA_CACHE = {
            meta,
            summary,
            stations: stations.stations || [],
            hours:    stations.hours    || [],
            panic:    panic,
            correlations: correlations,
            sources:  sources
          };
          window.dispatchEvent(new CustomEvent("dataupdated", { detail: DATA_CACHE }));
        }
        return;
      } catch (err) {
        console.warn("[Feed Warning] Live fetch failed, falling back to local snapshot:", err);
      }
    }

    // 3. Fallback statis
    try {
      const fb = await fetchJson("./fallback.json");
      DATA_CACHE    = fb;
      LAST_FETCH_AT = Date.now();
      LAST_STATUS   = "offline";
      window.dispatchEvent(new CustomEvent("dataupdated", { detail: fb }));
      startTicker();
    } catch (fbErr) {
      LAST_STATUS = "offline";
      startTicker();
      console.error("[Fatal] Fallback also failed:", fbErr);
    }
  }

  // ── Polling scheduler ─────────────────────────────────────────────────────
  function startPolling() {
    clearTimeout(POLL_TIMER);
    POLL_TIMER = setTimeout(async () => {
      if (document.visibilityState === "visible") await loadData();
      startPolling();
    }, REFRESH_INTERVAL_MS);
  }

  // Tab kembali aktif → fetch langsung
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") loadData();
  });

  // Klik badge → refresh paksa
  function setupBadgeRefresh() {
    const badgeEl = document.getElementById("dataAgeBadge");
    if (!badgeEl) return;
    badgeEl.style.cursor = "pointer";
    badgeEl.title = "Klik untuk segarkan data sekarang";
    badgeEl.addEventListener("click", () => {
      const text = document.getElementById("badgeText");
      if (text) text.textContent = "MEMPERBARUI...";
      loadData();
    });
  }

  window.BaliAPI = {
    loadData,
    startPolling,
    getData: () => DATA_CACHE
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      setupBadgeRefresh();
      loadData();
      startPolling();
    });
  } else {
    setupBadgeRefresh();
    loadData();
    startPolling();
  }
})();
