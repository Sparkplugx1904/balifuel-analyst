// BaliFuel Analyst — Client Controller & Live Poller (Gaya Devtools-UI)
(function () {
  let CURRENT_RUN_ID = null;
  let DATA_CACHE = null;
  let POLL_TIMER = null;
  let ALL_STATIONS = [];
  let ALL_HOURS = [];

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
    const sanitized = text.replace(/:\s*NaN/g, ': null').replace(/:\s*Infinity/g, ': null');
    return JSON.parse(sanitized);
  }

  async function loadData() {
    const feed = getFeedUrl();

    // 1. Cek data tertanam (Local Target Mode)
    if (window.BALI_EMBEDDED_DATA) {
      renderDashboard(window.BALI_EMBEDDED_DATA);
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
          renderDashboard(DATA_CACHE);
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
      renderDashboard(fb);
      updateStatusBadge(null, false);
    } catch (fbErr) {
      console.error("[Fatal] Fallback also failed:", fbErr);
    }
  }

  const REFRESH_INTERVAL_MS = 60000; // 60 detik (1 menit sekali)

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

  // UI RENDERER
  function renderDashboard(data) {
    if (!data) return;
    const meta = data.meta || data.summary?.metrics || {};
    const sum = data.summary || data;
    const stList = data.stations || [];
    const hours = data.hours || data.forecasts?.hours_label || [];

    // Header Values
    const csiVal = meta.csi_island || sum.metrics?.current_island_csi || 50.0;
    const statusTxt = sum.metrics?.current_status || "Pemulihan Bertahap";
    const recoveryTxt = meta.median_recovery_wita || (sum.monte_carlo?.median_hours ? `${sum.monte_carlo?.median_hours} Jam` : "18 Okt 2026, 05:00 WITA");
    const emptyPct = sum.metrics?.latest_empty_spbu_pct || 48.2;

    document.getElementById("hdrStatus").textContent = `${statusTxt.toUpperCase()} (CSI: ${csiVal})`;
    document.getElementById("hdrRecovery").textContent = recoveryTxt;
    document.getElementById("hdrEmptyPct").textContent = `${emptyPct}%`;

    // Box Values
    document.getElementById("boxMedianDate").textContent = meta.median_recovery_wita || "18 Okt 2026, 05:00 WITA";
    if (meta.ci50 && meta.ci50.length >= 2) {
      document.getElementById("boxCi50").textContent = `${meta.ci50[0].split(' ')[0]} \u2014 ${meta.ci50[1].split(' ')[0]}`;
    }
    if (meta.ci80 && meta.ci80.length >= 2) {
      document.getElementById("boxCi80").textContent = `${meta.ci80[0].split(' ')[0]} \u2014 ${meta.ci80[1].split(' ')[0]}`;
    }
    document.getElementById("pillCount").textContent = `${stList.length} Titik`;
    ALL_STATIONS = stList || [];
    ALL_HOURS = hours || [];

    // Leaflet Map Render
    initMap(stList, hours);

    // Area Chart & Table
    initAreaAnalysis(sum.areas || []);

    // Monte Carlo Charts
    initMonteCarlo(sum.monte_carlo || {});

    // Hotspots Table
    initHotspots(sum.hotspots || [], stList, hours);

    // Timeline
    initTimeline(sum.timeline || []);
  }

  // LEAFLET MAP MODULE
  let mapInstance = null;
  let markersLayer = null;

  function initMap(stations, hours) {
    if (!mapInstance) {
      const mapEl = document.getElementById("map");
      if (!mapEl) return;

      mapInstance = L.map("map", { attributionControl: true }).setView([-8.48, 115.18], 10);

      // OpenStreetMap Standard Tiles (BEBAS API KEY, sama seperti route-planner template)
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(mapInstance);

      // Terminal Pins
      const termIcon = (title) => L.divIcon({
        className: 'term-pin',
        html: `<div style="background:#000; color:#FF8A3D; border:1px solid #FF8A3D; padding:2px 6px; font-family:JetBrains Mono, monospace; font-size:10px; font-weight:700; border-radius:3px; box-shadow:0 0 8px rgba(255,138,61,0.4);">${title}</div>`,
        iconSize: [110, 20]
      });
      L.marker([-8.7262, 115.2120], { icon: termIcon("TBBM SANGGARAN") }).addTo(mapInstance).bindPopup("<b>TBBM Sanggaran (Denpasar)</b><br>Depot Suplai Utama Bali Selatan");
      L.marker([-8.5115, 115.5300], { icon: termIcon("TBBM MANGGIS") }).addTo(mapInstance).bindPopup("<b>TBBM Manggis (Karangasem)</b><br>Depot Penerima Tanker Laut Dalam");

      markersLayer = L.layerGroup().addTo(mapInstance);

      document.getElementById("filterKind").addEventListener("change", () => renderMapPins());
      document.getElementById("filterArea").addEventListener("change", () => renderMapPins());
      document.getElementById("filterStatus").addEventListener("change", () => renderMapPins());

      // Reset Map Button
      const btnReset = document.getElementById("btnResetMap");
      if (btnReset) {
        btnReset.addEventListener("click", () => {
          mapInstance.setView([-8.48, 115.18], 10);
        });
      }

      // Locate Me Button
      const btnLocate = document.getElementById("btnLocateMe");
      if (btnLocate) {
        btnLocate.addEventListener("click", () => {
          if (!navigator.geolocation) {
            alert("Geolocation tidak didukung oleh browser Anda.");
            return;
          }
          btnLocate.textContent = "\uD83D\uDCCD Mencari...";
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              btnLocate.textContent = "\uD83D\uDCCD Lokasi Saya";
              const userLat = pos.coords.latitude;
              const userLng = pos.coords.longitude;
              mapInstance.setView([userLat, userLng], 14);
              L.circleMarker([userLat, userLng], {
                radius: 8,
                fillColor: "#38BDF8",
                color: "#FFFFFF",
                weight: 2,
                fillOpacity: 1.0
              }).addTo(mapInstance).bindPopup("<b>Lokasi Anda Saat Ini</b>").openPopup();
            },
            (err) => {
              btnLocate.textContent = "\uD83D\uDCCD Lokasi Saya";
              alert("Gagal membaca lokasi GPS: " + err.message);
            },
            { enableHighAccuracy: true, timeout: 8000 }
          );
        });
      }

      // Populate Area Dropdown
      const areaSelect = document.getElementById("filterArea");
      const areaSet = new Set(stations.map(s => s.area).filter(Boolean));
      Array.from(areaSet).sort().forEach(a => {
        const opt = document.createElement("option");
        opt.value = a;
        opt.textContent = a;
        areaSelect.appendChild(opt);
      });

      setTimeout(() => mapInstance.invalidateSize(), 200);
    }

    renderMapPins();

    if (ALL_STATIONS.length > 0) {
      selectStation(ALL_STATIONS[0], ALL_HOURS);
    }
  }

  function renderMapPins() {
    if (!markersLayer) return;
    markersLayer.clearLayers();

    const fKind = document.getElementById("filterKind") ? document.getElementById("filterKind").value : "all";
    const fArea = document.getElementById("filterArea") ? document.getElementById("filterArea").value : "all";
    const fStatus = document.getElementById("filterStatus") ? document.getElementById("filterStatus").value : "all";

    const stations = ALL_STATIONS;
    if (!stations || stations.length === 0) return;

    stations.forEach(s => {
      const lat = s.lat != null ? parseFloat(s.lat) : (s.latitude != null ? parseFloat(s.latitude) : null);
      const lng = s.lng != null ? parseFloat(s.lng) : (s.lon != null ? parseFloat(s.lon) : (s.longitude != null ? parseFloat(s.longitude) : null));
      if (lat == null || lng == null || isNaN(lat) || isNaN(lng)) return;

      const kind = (s.kind || "spbu").toLowerCase();
      const area = s.area || "Bali";
      const p = s.p_now != null ? parseFloat(s.p_now) : (s.prob_pertalite != null ? parseFloat(s.prob_pertalite) : 0.5);

      if (fKind !== "all" && kind !== fKind) return;
      if (fArea !== "all" && area !== fArea) return;

      if (fStatus === "avail" && p < 0.60) return;
      if (fStatus === "warn" && (p < 0.35 || p >= 0.60)) return;
      if (fStatus === "empty" && p >= 0.35) return;

      let color = "#FF6B5A";
      if (p >= 0.60) color = "#22C55E";
      else if (p >= 0.35) color = "#FF8A3D";

      const isSpbu = kind === "spbu";
      const marker = L.circleMarker([lat, lng], {
        radius: isSpbu ? 7.0 : 4.5,
        fillColor: color,
        color: "#000000",
        weight: 1.5,
        opacity: 1.0,
        fillOpacity: 0.9
      });

      const qText = s.queue != null ? `${s.queue} mnt` : "Belum ada laporan";
      const priceText = s.price ? `Rp ${Number(s.price).toLocaleString()}/L` : (isSpbu ? "Rp 10.000/L (HET)" : "-");

      const popupHtml = `
        <div style="font-size:11px; line-height:1.5;">
          <div style="font-weight:700; color:var(--accent); font-size:12px; margin-bottom:2px;">${s.name || 'SPBU'}</div>
          <div style="color:var(--ink-3); margin-bottom:6px;">${area} \u00B7 [${kind.toUpperCase()}]</div>
          <div style="border-top:1px solid var(--line-strong); padding-top:6px;">
            <div>PELUANG STOK: <b style="color:${color}">${Math.round(p * 100)}%</b></div>
            <div>EST. ANTREAN: <b>${qText}</b></div>
            <div>HARGA: <b>${priceText}</b></div>
          </div>
          <button id="popBtn_${s.id}" style="margin-top:8px; width:100%; height:26px; background:var(--accent); color:#000; border:0; border-radius:3px; font-weight:700; font-size:10px; cursor:pointer;">
            INSPEKSI GRAFIK 72 JAM
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml);
      marker.on("popupopen", () => {
        const btn = document.getElementById(`popBtn_${s.id}`);
        if (btn) {
          btn.onclick = () => {
            selectStation(s, ALL_HOURS);
            switchTab('tabForecast');
          };
        }
      });

      markersLayer.addLayer(marker);
    });
  }

  // SELECT SPBU & PLOTLY FORECAST CHART
  function selectStation(st, hours) {
    if (!st) return;
    document.getElementById("cardBadgeKind").textContent = (st.kind || "spbu").toUpperCase();
    document.getElementById("cardCode").textContent = st.code || "-";
    document.getElementById("cardName").textContent = st.name || `SPBU ${st.id}`;
    document.getElementById("cardAddress").textContent = st.address || st.area || "-";

    const p = st.p_now != null ? st.p_now : 0.5;
    document.getElementById("cardProb").textContent = `${Math.round(p * 100)}%`;
    document.getElementById("cardProb").style.color = p >= 0.60 ? "var(--success)" : (p >= 0.35 ? "var(--accent)" : "var(--danger)");

    document.getElementById("cardQueue").textContent = st.queue != null ? `${st.queue} menit` : "15 menit";
    document.getElementById("cardDist").textContent = st.distance_to_terminal_km ? `${st.distance_to_terminal_km} km` : "-";
    document.getElementById("cardRecovery").textContent = st.recov || "-";
    document.getElementById("cardPrice").textContent = st.price ? `Rp ${Number(st.price).toLocaleString()} / L` : (st.kind === 'spbu' ? "Rp 10.000 / L (HET)" : "-");

    // Plotly 72h Chart
    const p50 = (st.p50 || []).map(v => v * 100);
    const p10 = (st.p10 || []).map(v => v * 100);
    const p90 = (st.p90 || []).map(v => v * 100);
    const qTraj = st.q_traj || [];

    const traceP90 = { x: hours, y: p90, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false, hoverinfo: 'skip' };
    const traceP10 = { x: hours, y: p10, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(255, 138, 61, 0.16)', line: { width: 0 }, name: 'Pita 80% (P10-P90)' };
    const traceP50 = { x: hours, y: p50, type: 'scatter', mode: 'lines', line: { color: '#FF8A3D', width: 2.5 }, name: 'Peluang Stok (%)' };
    const traceQ = { x: hours, y: qTraj, type: 'scatter', mode: 'lines', yaxis: 'y2', line: { color: '#A1A1A1', width: 1.5, dash: 'dot' }, name: 'Antrean (Mnt)' };

    const layout = {
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      margin: { l: 45, r: 45, t: 25, b: 35 },
      font: { family: 'JetBrains Mono, monospace', color: '#A1A1A1', size: 10 },
      legend: { orientation: 'h', y: -0.22, x: 0.05 },
      xaxis: { gridcolor: '#1F1F1F', nticks: 10 },
      yaxis: { title: 'Peluang Stok (%)', range: [0, 105], gridcolor: '#1F1F1F' },
      yaxis2: { title: 'Waktu Antre (Mnt)', overlaying: 'y', side: 'right', range: [0, 55], showgrid: false }
    };

    Plotly.newPlot('spbuPlotlyChart', [traceP90, traceP10, traceP50, traceQ], layout, { responsive: true, displayModeBar: false });
  }

  // AREA MODULE
  function initAreaAnalysis(areaData) {
    if (!areaData || areaData.length === 0) return;

    Plotly.newPlot('areaPlotlyChart', [
      { x: areaData.map(a => a.area), y: areaData.map(a => a.area_csi), type: 'bar', name: 'Skor CSI Keparahan', marker: { color: '#FF8A3D' } },
      { x: areaData.map(a => a.area), y: areaData.map(a => a.pct_empty_stations), type: 'bar', name: '% SPBU Kosong', marker: { color: '#FF6B5A' } }
    ], {
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      margin: { l: 35, r: 20, t: 20, b: 70 },
      font: { family: 'JetBrains Mono, monospace', color: '#A1A1A1', size: 10 },
      barmode: 'group', legend: { orientation: 'h', y: 1.15 },
      xaxis: { gridcolor: '#1F1F1F', tickangle: -40 },
      yaxis: { gridcolor: '#1F1F1F', range: [0, 100] }
    }, { responsive: true, displayModeBar: false });

    const atb = document.getElementById("areaTableBody");
    if (!atb) return;
    atb.innerHTML = "";
    areaData.forEach(a => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:700; color:var(--ink);">${a.area}</td>
        <td style="font-weight:700; color:var(--accent);">${a.area_csi}</td>
        <td>${a.spbu_count}</td>
        <td>${a.pertamini_count}</td>
        <td style="color:var(--danger);">${a.pct_empty_stations}%</td>
        <td>${a.avg_queue_minutes} mnt</td>
        <td>${a.price_gouging_rate_pct}% kios</td>
        <td><span style="padding:2px 6px; border-radius:3px; font-size:10px; background:${a.status === 'Kritis' ? 'rgba(255,107,90,0.15)' : 'rgba(255,138,61,0.15)'}; color:${a.status === 'Kritis' ? 'var(--danger)' : 'var(--accent)'}">${a.status}</span></td>
      `;
      atb.appendChild(tr);
    });
  }

  // MONTE CARLO MODULE
  function initMonteCarlo(mc) {
    if (!mc) return;
    const fc = mc.fan_chart;
    if (fc && fc.timestamps) {
      Plotly.newPlot('fanPlotlyChart', [
        { x: fc.timestamps, y: fc.p95, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false },
        { x: fc.timestamps, y: fc.p5, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(255, 138, 61, 0.12)', line: { width: 0 }, name: 'Rentang 90%' },
        { x: fc.timestamps, y: fc.p75, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false },
        { x: fc.timestamps, y: fc.p25, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(255, 138, 61, 0.28)', line: { width: 0 }, name: 'Rentang 50%' },
        { x: fc.timestamps, y: fc.p50, type: 'scatter', mode: 'lines', line: { color: '#FF8A3D', width: 2.5 }, name: 'Median (P50)' }
      ], {
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        margin: { l: 35, r: 15, t: 15, b: 55 },
        font: { family: 'JetBrains Mono, monospace', color: '#A1A1A1', size: 9.5 },
        legend: { orientation: 'h', y: -0.25 },
        xaxis: { gridcolor: '#1F1F1F', tickangle: -30, nticks: 8 },
        yaxis: { gridcolor: '#1F1F1F', title: '% Stok', range: [0, 105] }
      }, { responsive: true, displayModeBar: false });
    }

    const histData = mc.histogram || [];
    if (histData.length > 0) {
      Plotly.newPlot('histPlotlyChart', [{
        x: histData.map(h => h.date), y: histData.map(h => h.percentage),
        type: 'bar', marker: { color: '#FF8A3D' }
      }], {
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        margin: { l: 35, r: 15, t: 15, b: 55 },
        font: { family: 'JetBrains Mono, monospace', color: '#A1A1A1', size: 9.5 },
        xaxis: { gridcolor: '#1F1F1F', tickangle: -30 },
        yaxis: { gridcolor: '#1F1F1F', title: 'Peluang (%)' }
      }, { responsive: true, displayModeBar: false });
    }
  }

  // HOTSPOTS MODULE
  function initHotspots(hotspots, stList, hours) {
    const htb = document.getElementById("hotspotTableBody");
    if (!htb) return;
    htb.innerHTML = "";
    hotspots.forEach((h, idx) => {
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      tr.onclick = () => {
        const match = stList.find(s => s.id === h.id);
        if (match) {
          selectStation(match, hours);
          switchTab('tabForecast');
        }
      };
      tr.innerHTML = `
        <td style="color:var(--ink-3); font-weight:700;">#${idx + 1}</td>
        <td style="font-weight:600; color:var(--ink);">${h.name}</td>
        <td><span style="font-size:10px; color:${h.kind === 'spbu' ? 'var(--accent)' : 'var(--ink-2)'}">[${(h.kind || 'spbu').toUpperCase()}]</span></td>
        <td>${h.area}</td>
        <td>${h.distance_terminal_km || h.distance_to_terminal_km || '-'} km</td>
        <td style="color:var(--danger); font-weight:700;">${Math.round((h.current_p_pertalite || 0.3) * 100)}%</td>
        <td>${h.queue_mins != null ? h.queue_mins + ' mnt' : '-'}</td>
        <td style="color:var(--accent); font-weight:700;">${h.vulnerability_score || '-'}</td>
        <td>${h.estimated_recovery_date || '-'}</td>
      `;
      htb.appendChild(tr);
    });
  }

  // TIMELINE MODULE
  function initTimeline(timeline) {
    const tw = document.getElementById("timelineWrap");
    if (!tw) return;
    tw.innerHTML = "";
    timeline.forEach(evt => {
      const div = document.createElement("div");
      div.style.padding = "10px 14px";
      div.style.borderRadius = "var(--r-sm)";
      div.innerHTML = `
        <div style="font-size:11px; font-weight:700; color:var(--accent); margin-bottom:2px;">[${evt.date} ${evt.time_wita || ''} WITA] — ${evt.source || 'Pertamina'}</div>
        <div style="font-size:12px; color:var(--ink); margin-bottom:4px;">${evt.event}</div>
        <div style="font-size:11px; color:var(--ink-3); font-style:italic;">Dampak: ${evt.impact || '-'}</div>
      `;
      tw.appendChild(div);
    });
  }

  // TAB SWITCHER
  window.switchTab = function (tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.user-pill').forEach(el => el.classList.remove('active'));

    const target = document.getElementById(tabId);
    if (target) target.style.display = 'block';

    const btn = Array.from(document.querySelectorAll('.user-pill')).find(b => b.getAttribute('onclick')?.includes(tabId));
    if (btn) btn.classList.add('active');

    if (tabId === 'tabMap' && mapInstance) {
      setTimeout(() => mapInstance.invalidateSize(), 100);
    }
    if (tabId === 'tabAreas') Plotly.relayout('areaPlotlyChart', { autosize: true });
    if (tabId === 'tabSimulation') {
      Plotly.relayout('fanPlotlyChart', { autosize: true });
      Plotly.relayout('histPlotlyChart', { autosize: true });
    }
    if (tabId === 'tabForecast') Plotly.relayout('spbuPlotlyChart', { autosize: true });
  };

  // SEARCH INPUT
  document.getElementById("searchInput").addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (q.length < 2 || !DATA_CACHE?.stations) return;
    const match = DATA_CACHE.stations.find(s =>
      (s.name && s.name.toLowerCase().includes(q)) ||
      (s.code && s.code.toLowerCase().includes(q)) ||
      (s.address && s.address.toLowerCase().includes(q)) ||
      (s.area && s.area.toLowerCase().includes(q))
    );
    if (match) {
      selectStation(match, DATA_CACHE.hours || []);
      switchTab('tabForecast');
    }
  });

  // THEME TOGGLE
  const themeBtn = document.getElementById("themeToggleBtn");
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme");
      if (cur === "light") {
        document.documentElement.removeAttribute("data-theme");
        themeBtn.textContent = "\u2600";
      } else {
        document.documentElement.setAttribute("data-theme", "light");
        themeBtn.textContent = "\u263E";
      }
    });
  }
  // CLICK BADGE TO FORCE REFRESH
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

  // START
  try {
    initMap([], []);
  } catch (mErr) {
    console.warn("[Map Init] Pre-init warning:", mErr);
  }
  loadData();
  startPolling();
})();
