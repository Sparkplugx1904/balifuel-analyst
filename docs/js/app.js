// BaliFuel Analyst — Main Coordinator Module
(function () {
  let LATEST_DATA = null;

  function renderMetricsAndHeader(data) {
    if (!data) return;
    const meta = data.meta || data.summary?.metrics || {};
    const sum = data.summary || data;
    const stList = data.stations || [];

    const csiVal = meta.csi_island != null ? meta.csi_island : (sum.metrics?.current_island_csi || 50.0);
    const statusTxt = sum.metrics?.current_status || "Pemulihan Bertahap";
    const recoveryTxt = meta.median_recovery_wita || (sum.monte_carlo?.median_hours ? `${sum.monte_carlo?.median_hours} Jam` : "18 Okt 2026, 05:00 WITA");
    const emptyPct = sum.metrics?.latest_empty_spbu_pct != null ? sum.metrics?.latest_empty_spbu_pct : 48.2;

    const hdrStatus = document.getElementById("hdrStatus");
    const hdrRecovery = document.getElementById("hdrRecovery");
    const hdrEmpty = document.getElementById("hdrEmptyPct");
    const boxMedian = document.getElementById("boxMedianDate");
    const boxCi50 = document.getElementById("boxCi50");
    const boxCi80 = document.getElementById("boxCi80");
    const pillCount = document.getElementById("pillCount");

    if (hdrStatus) hdrStatus.textContent = `${statusTxt.toUpperCase()} (CSI: ${csiVal})`;
    if (hdrRecovery) hdrRecovery.textContent = recoveryTxt;
    if (hdrEmpty) hdrEmpty.textContent = `${emptyPct}%`;
    if (boxMedian) boxMedian.textContent = recoveryTxt;
    if (pillCount) pillCount.textContent = `${stList.length} Titik`;

    if (meta.ci50 && meta.ci50.length >= 2 && boxCi50) {
      boxCi50.textContent = `${meta.ci50[0].split(' ')[0]} \u2014 ${meta.ci50[1].split(' ')[0]}`;
    }
    if (meta.ci80 && meta.ci80.length >= 2 && boxCi80) {
      boxCi80.textContent = `${meta.ci80[0].split(' ')[0]} \u2014 ${meta.ci80[1].split(' ')[0]}`;
    }

    // Render Hotspots & Timeline
    renderHotspots(sum.hotspots || [], stList, data.hours || []);
    renderTimeline(sum.timeline || []);
  }

  function renderHotspots(hotspots, stList, hours) {
    const htb = document.getElementById("hotspotTableBody");
    if (!htb) return;
    htb.innerHTML = "";

    hotspots.forEach((h, idx) => {
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      tr.onclick = () => {
        const match = stList.find(s => s.id === h.id);
        if (match && window.BaliCharts && window.BaliCharts.selectStation) {
          window.BaliCharts.selectStation(match, hours);
          window.switchTab('tabForecast');
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

  function renderTimeline(timeline) {
    const tw = document.getElementById("timelineWrap");
    if (!tw) return;
    tw.innerHTML = "";
    timeline.forEach(evt => {
      const div = document.createElement("div");
      div.style.padding = "10px 14px";
      div.style.background = "var(--surface)";
      div.style.border = "1px solid var(--line)";
      div.style.borderRadius = "var(--r-sm)";
      div.innerHTML = `
        <div style="font-size:11px; font-weight:700; color:var(--accent); margin-bottom:2px;">[${evt.date} ${evt.time_wita || ''} WITA] \u2014 ${evt.source || 'Pertamina'}</div>
        <div style="font-size:12px; color:var(--ink); margin-bottom:4px;">${evt.event}</div>
        <div style="font-size:11px; color:var(--ink-3); font-style:italic;">Dampak: ${evt.impact || '-'}</div>
      `;
      tw.appendChild(div);
    });
  }

  // Global Tab Switcher
  window.switchTab = function (tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.user-pill').forEach(el => el.classList.remove('active'));

    const target = document.getElementById(tabId);
    if (target) target.style.display = 'block';

    const btn = Array.from(document.querySelectorAll('.user-pill')).find(b => b.getAttribute('onclick')?.includes(tabId));
    if (btn) btn.classList.add('active');

    if (tabId === 'tabMap' && window.BaliMap) {
      window.BaliMap.invalidateSize();
    }
    if (typeof Plotly !== "undefined") {
      if (tabId === 'tabAreas') Plotly.relayout('areaPlotlyChart', { autosize: true });
      if (tabId === 'tabSimulation') {
        Plotly.relayout('fanPlotlyChart', { autosize: true });
        Plotly.relayout('histPlotlyChart', { autosize: true });
      }
      if (tabId === 'tabForecast') Plotly.relayout('spbuPlotlyChart', { autosize: true });
    }
  };

  // Search Input Handler
  function setupSearch() {
    const input = document.getElementById("searchInput");
    if (!input) return;

    input.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (q.length < 2) return;
      const stations = window.BaliMap ? window.BaliMap.getStations() : [];
      if (!stations || stations.length === 0) return;

      const match = stations.find(s =>
        (s.name && s.name.toLowerCase().includes(q)) ||
        (s.code && s.code.toLowerCase().includes(q)) ||
        (s.address && s.address.toLowerCase().includes(q)) ||
        (s.area && s.area.toLowerCase().includes(q))
      );

      if (match && window.BaliCharts && window.BaliCharts.selectStation) {
        window.BaliCharts.selectStation(match, []);
        window.switchTab('tabForecast');
      }
    });
  }

  // Listen to dataupdated event from api.js
  window.addEventListener("dataupdated", (e) => {
    LATEST_DATA = e.detail;
    renderMetricsAndHeader(LATEST_DATA);
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupSearch);
  } else {
    setupSearch();
  }
})();
