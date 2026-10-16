// BaliFuel Analyst — Plotly Charts Module
(function () {
  let CURRENT_STATION = null;
  let CURRENT_HOURS = [];

  function getThemeColors() {
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    return {
      isLight: isLight,
      fontColor: isLight ? "#475569" : "#A1A1A1",
      gridColor: isLight ? "#E2E8F0" : "#1F1F1F"
    };
  }

  function updateEmptyState() {
    const emptyCard = document.getElementById("forecastEmptyState");
    const gridContainer = document.getElementById("spbuGridContainer");

    if (!CURRENT_STATION) {
      if (emptyCard) emptyCard.style.display = "block";
      if (gridContainer) gridContainer.style.display = "none";
    } else {
      if (emptyCard) emptyCard.style.display = "none";
      if (gridContainer) gridContainer.style.display = "grid";
    }
  }

  function initHours(hours) {
    if (hours && hours.length > 0) CURRENT_HOURS = hours;
    updateEmptyState();
  }

  function selectStation(st, hours) {
    if (!st) return;
    CURRENT_STATION = st;
    if (hours && hours.length > 0) CURRENT_HOURS = hours;
    updateEmptyState();
    const badge = document.getElementById("cardBadgeKind");
    const code = document.getElementById("cardCode");
    const name = document.getElementById("cardName");
    const addr = document.getElementById("cardAddress");
    const prob = document.getElementById("cardProb");
    const qEl = document.getElementById("cardQueue");
    const distEl = document.getElementById("cardDist");
    const recovEl = document.getElementById("cardRecovery");
    const priceEl = document.getElementById("cardPrice");

    if (badge) badge.textContent = (st.kind || "spbu").toUpperCase();
    if (code) code.textContent = st.code || "-";
    if (name) name.textContent = st.name || `SPBU ${st.id}`;
    if (addr) addr.textContent = st.address || st.area || "-";

    const p = st.p_now != null ? st.p_now : 0.5;
    if (prob) {
      prob.textContent = `${Math.round(p * 100)}%`;
      prob.style.color = p >= 0.60 ? "var(--success)" : (p >= 0.35 ? "var(--accent)" : "var(--danger)");
    }
    function formatQueueTime(mins) {
      if (mins == null || isNaN(mins)) return "-";
      const m = Math.round(mins);
      if (m <= 5) return "Lancar (≤5 mnt)";
      if (m < 60) return `${m} menit`;
      const h = Math.floor(m / 60);
      const rem = m % 60;
      return rem > 0 ? `${h} jam ${rem} mnt (${m} mnt)` : `${h} jam (${m} mnt)`;
    }

    if (qEl) qEl.textContent = formatQueueTime(st.queue);
    if (distEl) distEl.textContent = st.distance_to_terminal_km ? `${st.distance_to_terminal_km} km` : "-";
    if (recovEl) recovEl.textContent = st.recov || "-";
    if (priceEl) priceEl.textContent = st.price ? `Rp ${Number(st.price).toLocaleString()} / L` : (st.kind === 'spbu' ? "Rp 10.000 / L (HET)" : "-");

    const p50 = (st.p50 || []).map(v => v * 100);
    const p10 = (st.p10 || []).map(v => v * 100);
    const p90 = (st.p90 || []).map(v => v * 100);
    const qTraj = st.q_traj || [];

    const tc = getThemeColors();

    const traceP90 = { x: CURRENT_HOURS, y: p90, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false, hoverinfo: 'skip' };
    const traceP10 = { x: CURRENT_HOURS, y: p10, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(255, 138, 61, 0.16)', line: { width: 0 }, name: 'Pita 80% (P10-P90)' };
    const traceP50 = { x: CURRENT_HOURS, y: p50, type: 'scatter', mode: 'lines', line: { color: '#FF8A3D', width: 2.5 }, name: 'Peluang Ada Bensin (%)' };
    const validQ = (qTraj || []).filter(v => v != null && !isNaN(v));
    const maxQ = validQ.length > 0 ? Math.max(...validQ) : 120;
    const y2Max = Math.max(120, Math.ceil(maxQ / 60) * 60 + 30);
    const tickVals = [0, 60, 120, 180, 240, 300, 360, 420, 480].filter(v => v <= y2Max);
    const tickTexts = ['0m', '1 jam', '2 jam', '3 jam', '4 jam', '5 jam', '6 jam', '7 jam', '8 jam'].slice(0, tickVals.length);

    const traceQ = {
      x: CURRENT_HOURS,
      y: qTraj,
      type: 'scatter',
      mode: 'lines',
      yaxis: 'y2',
      line: { color: 'var(--danger)', width: 2, dash: 'dot' },
      name: 'Estimasi Antrean (Jam)',
      hovertemplate: '%{y:.0f} mnt (%{customdata})<extra></extra>',
      customdata: (qTraj || []).map(m => m >= 60 ? `${(m/60).toFixed(1)} jam` : `${Math.round(m)} mnt`)
    };

    const layout = {
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      margin: { l: 45, r: 55, t: 25, b: 35 },
      font: { family: 'JetBrains Mono, monospace', color: tc.fontColor, size: 10 },
      legend: { orientation: 'h', y: -0.22, x: 0.05 },
      xaxis: { gridcolor: tc.gridColor, nticks: 10 },
      yaxis: { title: 'Peluang Ada Bensin (%)', range: [0, 105], gridcolor: tc.gridColor },
      yaxis2: {
        title: 'Waktu Antre (Jam / Menit)',
        overlaying: 'y',
        side: 'right',
        range: [0, y2Max],
        showgrid: false,
        tickvals: tickVals,
        ticktext: tickTexts
      }
    };
    Plotly.newPlot('spbuPlotlyChart', [traceP90, traceP10, traceP50, traceQ], layout, { responsive: true, displayModeBar: false });
  }

  function renderAreaChart(areaData) {
    if (!areaData || areaData.length === 0) return;
    const tc = getThemeColors();

    Plotly.newPlot('areaPlotlyChart', [
      { x: areaData.map(a => a.area), y: areaData.map(a => a.area_csi), type: 'bar', name: 'Skor Kesulitan Bensin', marker: { color: '#FF8A3D' } },
      { x: areaData.map(a => a.area), y: areaData.map(a => a.pct_empty_stations), type: 'bar', name: '% SPBU Kosong', marker: { color: '#FF6B5A' } }
    ], {
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      margin: { l: 35, r: 20, t: 20, b: 70 },
      font: { family: 'JetBrains Mono, monospace', color: tc.fontColor, size: 10 },
      barmode: 'group', legend: { orientation: 'h', y: 1.15 },
      xaxis: { gridcolor: tc.gridColor, tickangle: -40 },
      yaxis: { gridcolor: tc.gridColor, range: [0, 100] }
    }, { responsive: true, displayModeBar: false });
  }

  function renderMonteCarlo(mc) {
    if (!mc) return;
    const tc = getThemeColors();

    const fc = mc.fan_chart;
    if (fc && fc.timestamps) {
      Plotly.newPlot('fanPlotlyChart', [
        { x: fc.timestamps, y: fc.p95, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false },
        { x: fc.timestamps, y: fc.p5, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(255, 138, 61, 0.12)', line: { width: 0 }, name: 'Rentang 90%' },
        { x: fc.timestamps, y: fc.p75, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false },
        { x: fc.timestamps, y: fc.p25, type: 'scatter', mode: 'lines', fill: 'tonexty', fillcolor: 'rgba(255, 138, 61, 0.28)', line: { width: 0 }, name: 'Rentang 50%' },
        { x: fc.timestamps, y: fc.p50, type: 'scatter', mode: 'lines', line: { color: '#FF8A3D', width: 2.5 }, name: 'Titik Tengah Perkiraan' }
      ], {
        paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
        margin: { l: 35, r: 15, t: 15, b: 55 },
        font: { family: 'JetBrains Mono, monospace', color: tc.fontColor, size: 9.5 },
        legend: { orientation: 'h', y: -0.25 },
        xaxis: { gridcolor: tc.gridColor, tickangle: -30, nticks: 8 },
        yaxis: { gridcolor: tc.gridColor, title: 'Peluang Ada Bensin (%)', range: [0, 105] }
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
        font: { family: 'JetBrains Mono, monospace', color: tc.fontColor, size: 9.5 },
        xaxis: { gridcolor: tc.gridColor, tickangle: -30 },
        yaxis: { gridcolor: tc.gridColor, title: 'Peluang (%)' }
      }, { responsive: true, displayModeBar: false });
    }
  }

  // Update Plotly chart colors on theme change
  window.addEventListener("themechange", () => {
    const tc = getThemeColors();
    const update = {
      "font.color": tc.fontColor,
      "xaxis.gridcolor": tc.gridColor,
      "yaxis.gridcolor": tc.gridColor
    };
    ["spbuPlotlyChart", "areaPlotlyChart", "fanPlotlyChart", "histPlotlyChart"].forEach(id => {
      const el = document.getElementById(id);
      if (el && el.data) {
        Plotly.relayout(id, update);
      }
    });
  });

  // Listen to data update
  window.addEventListener("dataupdated", (e) => {
    const data = e.detail;
    const sum = data.summary || data;
    const areas = sum.areas || sum.metrics?.area_metrics || [];
    renderAreaChart(areas);
    renderMonteCarlo(sum.monte_carlo || {});
  });

  window.BaliCharts = {
    selectStation: selectStation,
    renderAreaChart: renderAreaChart,
    renderMonteCarlo: renderMonteCarlo,
    initHours: initHours,
    getSelectedStation: () => CURRENT_STATION,
    updateEmptyState: updateEmptyState
  };
})();
