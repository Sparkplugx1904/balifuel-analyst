// BaliFuel Analyst — Data API & Live Poller Module
(function () {
  let CURRENT_RUN_ID = null;
  let DATA_CACHE = null;
  let POLL_TIMER = null;
  const REFRESH_INTERVAL_MS = 60000; // 60 detik (1 menit sekali)

  function getFeedUrl() {
    let u = window.FEED_URL || "https://balifuel-worker.anandapradnyana68.workers.dev";
    return u.replace(/\/+$/, "");
  }

  function formatAgo(mins) {
    if (mins == null || isNaN(mins)) return "-";
    if (mins < 1) return "baru saja";
    if (mins < 60) return `${Math.round(mins)}m lalu`;
    return `${Math.round(mins / 60)}j lalu`;
  }

  function updateStatusBadge(meta, isLive) {
    const badge = document.getElementById("dataAgeBadge");
    const dot = document.getElementById("statusDot");
    const text = document.getElementById("badgeText");
    if (!badge || !dot || !text) return;

    if (!isLive) {
      dot.className = "status-dot red";
      text.textContent = "OFFLINE // FALLBACK";
      badge.style.borderColor = "var(--danger)";
      return;
    }

    const age = meta ? meta.data_age_min : 0;
    const ageStr = formatAgo(age);

    if (age > 30 || meta.status === "stale") {
      dot.className = "status-dot";
      dot.style.background = "var(--warning)";
      text.textContent = `DATA USANG (${ageStr}) \u00B7 60s`;
      badge.style.borderColor = "var(--warning)";
    } else if (meta.status === "degraded") {
      dot.className = "status-dot";
      dot.style.background = "var(--warning)";
      text.textContent = `DEGRADED (${ageStr}) \u00B7 60s`;
      badge.style.borderColor = "var(--warning)";
    } else {
      dot.className = "status-dot green";
      dot.style.background = "var(--success)";
      text.textContent = `LIVE (${ageStr}) \u00B7 60s`;
      badge.style.borderColor = "var(--line-strong)";
    }
  }

  async function fetchJson(url) {
    const res = await fetch(url, { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status} on ${url}`);
    const text = await res.text();
    // Client-side safeguard against NaN, Infinity, -Infinity
    const sanitized = text.replace(/:\s*NaN\b/g, ': null').replace(/:\s*Infinity\b/g, ': null');
    return JSON.parse(sanitized);
  }

  async function loadData() {
    const feed = getFeedUrl();

    // 1. Cek data tertanam (Local Target Mode)
    if (window.BALI_EMBEDDED_DATA) {
      DATA_CACHE = window.BALI_EMBEDDED_DATA;
      window.dispatchEvent(new CustomEvent("dataupdated", { detail: DATA_CACHE }));
      updateStatusBadge({ data_age_min: 5, status: "ok" }, true);
      return;
    }

    // 2. Pages Target: Fetch dari Cloudflare Worker
    if (feed) {
      try {
        const meta = await fetchJson(`${feed}/latest/meta.json`);
        updateStatusBadge(meta, true);

        if (meta.run_id !== CURRENT_RUN_ID) {
          CURRENT_RUN_ID = meta.run_id;
          const [summary, stations] = await Promise.all([
            fetchJson(`${feed}/latest/summary.json`),
            fetchJson(`${feed}/latest/stations.json`)
          ]);

          DATA_CACHE = {
            meta: meta,
            summary: summary,
            stations: stations.stations || [],
            hours: stations.hours || []
          };
          window.dispatchEvent(new CustomEvent("dataupdated", { detail: DATA_CACHE }));
        }
        return;
      } catch (err) {
        console.warn("[Feed Warning] Live fetch failed, falling back to local snapshot:", err);
      }
    }

    // 3. Fallback jika Worker offline
    try {
      const fb = await fetchJson("./fallback.json");
      DATA_CACHE = fb;
      window.dispatchEvent(new CustomEvent("dataupdated", { detail: fb }));
      updateStatusBadge(null, false);
    } catch (fbErr) {
      console.error("[Fatal] Fallback also failed:", fbErr);
    }
  }

  function startPolling() {
    if (POLL_TIMER) clearTimeout(POLL_TIMER);
    POLL_TIMER = setTimeout(async () => {
      if (document.visibilityState === "visible") {
        await loadData();
      }
      startPolling();
    }, REFRESH_INTERVAL_MS);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      loadData();
    }
  });

  // Click badge to force instant refresh
  function setupBadgeRefresh() {
    const badgeEl = document.getElementById("dataAgeBadge");
    if (badgeEl) {
      badgeEl.style.cursor = "pointer";
      badgeEl.title = "Klik untuk segarkan data sekarang (Pembaruan otomatis tiap 60 detik)";
      badgeEl.addEventListener("click", () => {
        const text = document.getElementById("badgeText");
        if (text) text.textContent = "MEMPERBARUI...";
        loadData();
      });
    }
  }

  window.BaliAPI = {
    loadData: loadData,
    startPolling: startPolling,
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
