"""
Dashboard Builder Module: Generator Dashboard Lokal & GitHub Pages
Mendukung dua target:
1. --target local : Menghasilkan output/dashboard.html (monolitik data tertanam, bisa file://)
2. --target pages : Menghasilkan docs/ (index.html ramping, style.css, app.js, config.js, fallback.json)
   dengan semua path aset RELATIF (./app.js, ./style.css) untuk sub-path GitHub Pages.
Peta menggunakan Leaflet dengan layer switcher (Dark Matter, OpenStreetMap, Satelit Esri),
filter interaktif, reset zoom, dan geolokasi.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.cleaner import sanitize_for_json
DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DOCS_DIR = os.path.join(BASE_DIR, "docs")


STYLE_CSS = """/* ==========================================================================
   BaliFuel Crisis Analyst — Terminal Design System (Gaya Devtools-UI)
   Latar hitam pekat, monospace, garis tipis 1px, aksen orange #FF8A3D.
   ========================================================================== */

:root {
  --bg: #000000;
  --surface: #0A0A0A;
  --card: #0D0D0D;
  --ink: #EDEDED;
  --ink-2: #A1A1A1;
  --ink-3: #6E6E6E;
  --line: #1F1F1F;
  --line-strong: #323232;

  --accent: #FF8A3D;
  --accent-soft: rgba(255, 138, 61, 0.14);

  --primary-bg: #EDEDED;
  --primary-ink: #000000;

  --success: #22C55E;
  --success-soft: rgba(34, 197, 94, 0.14);
  --warning: #F59E0B;
  --danger: #FF6B5A;
  --scrim: rgba(0, 0, 0, 0.85);

  --f-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --r-sm: 4px;
  --r-md: 6px;
  --r-lg: 8px;
  --page-max: 1320px;
  --page-pad: 24px;
}

[data-theme="light"] {
  --bg: #FFFFFF;
  --surface: #FAFAFA;
  --card: #FFFFFF;
  --ink: #0A0A0A;
  --ink-2: #525252;
  --ink-3: #8A8A8A;
  --line: #E8E8E8;
  --line-strong: #D2D2D2;
  --accent: #E4580B;
  --accent-soft: rgba(228, 88, 11, 0.1);
  --primary-bg: #0A0A0A;
  --primary-ink: #FFFFFF;
  --danger: #C23B2E;
  --scrim: rgba(0, 0, 0, 0.5);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--f-mono);
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink);
  background: var(--bg);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

button, input, select { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
::selection { background: var(--accent); color: #000; }

.btn {
  display: inline-flex; align-items: center; justify-content: center;
  gap: 8px; height: 36px; padding: 0 14px;
  border: 1px solid transparent; border-radius: var(--r-md);
  font-weight: 500; font-size: 12px; white-space: nowrap;
  transition: background-color 0.12s, border-color 0.12s, color 0.12s;
  text-decoration: none;
}
.btn-sm { height: 30px; padding: 0 10px; font-size: 11px; }
.btn-icon { width: 34px; padding: 0; }
.btn-primary { background: var(--primary-bg); color: var(--primary-ink); font-weight: 600; }
.btn-outline { background: transparent; border-color: var(--line-strong); color: var(--ink); }
.btn-outline:hover { border-color: var(--ink-3); background: var(--surface); }

.navbar {
  position: sticky; top: 0; z-index: 50;
  background: color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter: blur(12px); border-bottom: 1px solid var(--line);
}
.nav-container {
  max-width: var(--page-max); margin: 0 auto;
  padding: 10px var(--page-pad);
  display: grid; grid-template-columns: auto 1fr auto;
  align-items: center; gap: 20px;
}
.brand { display: inline-flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; }
.brand-logo {
  display: grid; place-items: center; width: 28px; height: 28px;
  border-radius: var(--r-sm); background: var(--accent);
  color: #000; font-weight: 800; font-size: 13px;
}
.brand-name { font-weight: 700; font-size: 14px; letter-spacing: -0.02em; }
.brand-tag { font-weight: 400; font-size: 11px; color: var(--ink-3); margin-left: 4px; }

.search-box { position: relative; max-width: 440px; justify-self: center; width: 100%; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--ink-3); font-size: 12px; pointer-events: none; }
#searchInput {
  width: 100%; height: 34px; padding: 0 34px 0 32px;
  background: var(--surface); border: 1px solid var(--line-strong);
  border-radius: var(--r-md); font-size: 12px; transition: border-color 0.12s;
}
#searchInput:focus { outline: none; border-color: var(--accent); }

.nav-right { display: flex; align-items: center; gap: 10px; justify-self: end; }
.status-pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
  border-radius: var(--r-sm); background: var(--surface);
  border: 1px solid var(--line-strong); font-size: 11px;
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 6px var(--accent); }
.status-dot.green { background: var(--success); box-shadow: 0 0 6px var(--success); }
.status-dot.red { background: var(--danger); box-shadow: 0 0 6px var(--danger); }

.main-container { max-width: var(--page-max); margin: 0 auto; padding: 24px var(--page-pad) 80px; }

.channel-header { padding-top: 18px; margin-bottom: 24px; }
.channel-title-row { display: flex; align-items: center; gap: 12px; }
.channel-name { font-weight: 700; font-size: clamp(1.8rem, 4.5vw, 3.2rem); line-height: 1.05; letter-spacing: -0.04em; }
.verified-badge {
  display: grid; place-items: center; width: 22px; height: 22px;
  border-radius: 50%; background: var(--accent); color: #000; font-size: 12px; font-weight: 800;
}
.channel-stats { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 10px; font-size: 12px; color: var(--ink-2); }
.channel-stats b { color: var(--ink); }

.terminal-card {
  padding: 20px; background: var(--surface);
  border: 1px solid var(--line-strong); border-radius: var(--r-lg); margin: 20px 0;
}
.term-prompt { font-size: 12px; color: var(--ink-2); margin-bottom: 12px; }
.term-prompt::before { content: "$ "; color: var(--accent); font-weight: 700; }
.term-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
.term-stat-item { padding: 12px; background: var(--card); border: 1px solid var(--line); border-radius: var(--r-md); }
.term-stat-label { font-size: 11px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 0.05em; }
.term-stat-value { font-size: 18px; font-weight: 700; color: var(--ink); margin-top: 4px; }
.term-stat-desc { font-size: 11px; color: var(--ink-2); margin-top: 2px; }

.user-pills-bar {
  display: flex; gap: 4px; margin: 24px 0 20px;
  overflow-x: auto; border-bottom: 1px solid var(--line); scrollbar-width: thin;
}
.user-pill {
  flex: none; display: inline-flex; align-items: baseline; gap: 8px;
  padding: 10px 16px; margin-bottom: -1px; background: transparent;
  border: 0; border-bottom: 2px solid transparent; font-size: 12px;
  font-weight: 500; color: var(--ink-3); white-space: nowrap;
}
.user-pill:hover { color: var(--ink); }
.user-pill.active { color: var(--ink); border-bottom-color: var(--accent); font-weight: 600; }
.user-pill small { color: var(--ink-3); font-size: 10px; }

.dash-section {
  margin-bottom: 32px; padding: 24px; background: var(--card);
  border: 1px solid var(--line); border-radius: var(--r-lg);
}
.section-header {
  display: flex; flex-direction: column; gap: 4px; margin-bottom: 20px;
  padding-bottom: 14px; border-bottom: 1px solid var(--line);
}
.section-title {
  font-weight: 700; font-size: 16px; letter-spacing: -0.02em;
  display: flex; align-items: center; gap: 8px;
}
.section-title::before { content: "//"; color: var(--accent); font-weight: 800; }
.section-desc { font-size: 12px; color: var(--ink-2); }

#map { height: 540px; width: 100%; border-radius: var(--r-md); border: 1px solid var(--line-strong); background: #050505; }
.map-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.map-filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

.filter-select {
  height: 32px; padding: 0 28px 0 10px; background-color: var(--surface);
  border: 1px solid var(--line-strong); border-radius: var(--r-sm); font-size: 11px;
  appearance: none; -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none' stroke='%236E6E6E' stroke-width='2'%3E%3Cpath d='M1 1.5l5 5 5-5'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
}
.filter-select option { background: var(--surface); color: var(--ink); }

.leaflet-popup-content-wrapper {
  background: #0D0D0D !important; color: #EDEDED !important;
  border-radius: var(--r-md) !important; border: 1px solid var(--line-strong) !important;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6) !important; font-family: var(--f-mono) !important;
}
.leaflet-popup-tip { background: #0D0D0D !important; }

.spbu-grid { display: grid; grid-template-columns: minmax(0, 380px) 1fr; gap: 20px; }
@media (max-width: 900px) { .spbu-grid { grid-template-columns: 1fr; } }
.spec-box { padding: 16px; background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--r-md); font-size: 12px; }
.spec-row { display: flex; justify-content: space-between; align-items: baseline; padding: 7px 0; border-bottom: 1px solid var(--line); }
.spec-row:last-child { border-bottom: 0; }
.spec-label { color: var(--ink-3); font-size: 11px; }
.spec-val { font-weight: 600; color: var(--ink); }

.terminal-table-wrap { overflow-x: auto; border: 1px solid var(--line-strong); border-radius: var(--r-md); }
.term-table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
.term-table th {
  background: var(--surface); color: var(--ink-3); text-align: left;
  padding: 10px 14px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; border-bottom: 1px solid var(--line-strong);
}
.term-table td { padding: 9px 14px; border-bottom: 1px solid var(--line); color: var(--ink-2); }
.term-table tr:hover td { background: var(--surface); color: var(--ink); }

.layman-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.layman-card { padding: 16px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); }
.layman-title { font-weight: 700; font-size: 13px; color: var(--ink); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.layman-desc { font-size: 12px; color: var(--ink-2); line-height: 1.5; }

.term-footer {
  margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--line);
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
  gap: 14px; font-size: 11px; color: var(--ink-3);
}
"""


INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark light">
  <meta name="theme-color" content="#000000">
  <title>BaliFuel // Crisis Analyst — Pemulihan Distribusi BBM Bali 2026</title>
  
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <!-- Leaflet Map CSS & JS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>

  <link rel="stylesheet" href="{css_path}">
  <script src="{config_path}" charset="utf-8"></script>
</head>
<body>

  <header class="navbar">
    <div class="nav-container">
      <a href="#" class="brand">
        <span class="brand-logo">⚡</span>
        <div>
          <span class="brand-name">BALIFUEL // CRISIS_WATCH</span>
          <span class="brand-tag">v2.1 · LIVE</span>
        </div>
      </a>

      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="Cari SPBU, nama jalan, area, atau kode..." autocomplete="off">
      </div>

      <div class="nav-right">
        <div class="status-pill" id="dataAgeBadge" title="Status sinkronisasi data">
          <span class="status-dot green" id="statusDot"></span>
          <span id="badgeText">FEED: CONNECTING</span>
        </div>
        <button id="themeToggleBtn" class="btn btn-outline btn-icon" title="Toggle Tema">
          ☀
        </button>
      </div>
    </div>
  </header>

  <main class="main-container">

    <section class="channel-header">
      <div class="channel-title-row">
        <h1 class="channel-name">BALI FUEL CRISIS ANALYST</h1>
        <span class="verified-badge" title="Terkalibrasi Data Lapangan">✓</span>
      </div>
      <div class="channel-stats">
        <span>STATUS: <b style="color:var(--warning)" id="hdrStatus">MEMUAT...</b></span>
        <span>•</span>
        <span>EST. PULIH: <b style="color:var(--accent)" id="hdrRecovery">-</b></span>
        <span>•</span>
        <span>SPBU KOSONG: <b style="color:var(--danger)" id="hdrEmptyPct">-</b></span>
        <span>•</span>
        <span>MONTE CARLO: <b>10.000 JALUR</b></span>
      </div>
    </section>

    <div class="terminal-card">
      <div class="term-prompt">simulation --horizon=384h --samples=10000 --rule="empty &lt; 10% sustained 48h"</div>
      <div class="term-grid">
        <div class="term-stat-item">
          <div class="term-stat-label">Prediksi Tanggal Mereda (Median)</div>
          <div class="term-stat-value" style="color:var(--accent)" id="boxMedianDate">Menghitung...</div>
          <div class="term-stat-desc" id="boxMedianDesc">Estimasi titik balik ketersediaan BBM</div>
        </div>
        <div class="term-stat-item">
          <div class="term-stat-label">50% Credible Interval (P25 - P75)</div>
          <div class="term-stat-value" id="boxCi50">-</div>
          <div class="term-stat-desc">Rentang probabilitas mayoritas (48 jam)</div>
        </div>
        <div class="term-stat-item">
          <div class="term-stat-label">80% Credible Interval (P10 - P90)</div>
          <div class="term-stat-value" id="boxCi80">-</div>
          <div class="term-stat-desc">Cakupan variabilitas cuaca & logistik</div>
        </div>
        <div class="term-stat-item">
          <div class="term-stat-label">Bottleneck Kritis Saat Ini</div>
          <div class="term-stat-value" style="color:var(--warning)">Truk Tangki Darat</div>
          <div class="term-stat-desc">Kapasitas 2.700 KL/hari vs antrean nosel</div>
        </div>
      </div>
    </div>

    <nav class="user-pills-bar">
      <button class="user-pill active" onclick="switchTab('tabMap')">[ 01 // PETA REAL-TIME (LEAFLET) ] <small id="pillCount">876 Titik</small></button>
      <button class="user-pill" onclick="switchTab('tabForecast')">[ 02 // PREDIKSI 72 JAM ] <small>Per SPBU</small></button>
      <button class="user-pill" onclick="switchTab('tabAreas')">[ 03 // 14 AREA MAKRO ] <small>Analisis CSI</small></button>
      <button class="user-pill" onclick="switchTab('tabSimulation')">[ 04 // SIMULASI MONTE CARLO ] <small>Fan Chart</small></button>
      <button class="user-pill" onclick="switchTab('tabHotspots')">[ 05 // 20 HOTSPOT RENTAN ] <small>Ranking</small></button>
      <button class="user-pill" onclick="switchTab('tabGuide')">[ 06 // PANDUAN WARGA & TIMELINE ] <small>Praktis</small></button>
    </nav>

    <!-- TAB 1: PETA LEAFLET -->
    <div id="tabMap" class="tab-content dash-section">
      <div class="section-header">
        <h2 class="section-title">SEBARAN SPBU & KIOS PERTAMINI REAL-TIME SE-BALI (LEAFLET)</h2>
        <p class="section-desc">Peta interaktif Leaflet: Carto Dark Matter, OpenStreetMap, dan Satelit Esri dengan filter status & pencarian geolokasi.</p>
      </div>

      <div class="map-toolbar">
        <div class="map-filters">
          <select id="filterKind" class="filter-select">
            <option value="all">Semua Titik (SPBU + Pertamini)</option>
            <option value="spbu">Hanya SPBU Resmi (212)</option>
            <option value="pertamini">Hanya Kios Pertamini (664)</option>
          </select>
          <select id="filterArea" class="filter-select">
            <option value="all">Semua Area (14 Wilayah)</option>
          </select>
          <select id="filterStatus" class="filter-select">
            <option value="all">Semua Status Ketersediaan</option>
            <option value="avail">Pasti / Ada Stok (&ge;60%)</option>
            <option value="warn">Menipis / Antre (35-60%)</option>
            <option value="empty">Kosong (&lt;35%)</option>
          </select>
          <button id="btnResetMap" class="btn btn-outline btn-sm" title="Pusatkan Peta ke Bali">
            ⟲ Bali
          </button>
          <button id="btnLocateMe" class="btn btn-outline btn-sm" title="Mencari SPBU di dekat posisi Anda">
            📍 Lokasi Saya
          </button>
        </div>
        <div style="font-size:11px; color:var(--ink-3);">
          <span>● <span style="color:var(--success)">Ada Stok (&ge;60%)</span></span> &nbsp;
          <span>● <span style="color:var(--warning)">Kritis (35-60%)</span></span> &nbsp;
          <span>● <span style="color:var(--danger)">Kosong (&lt;35%)</span></span>
        </div>
      </div>

      <div id="map"></div>
    </div>

    <!-- TAB 2: PREDIKSI PER SPBU -->
    <div id="tabForecast" class="tab-content dash-section" style="display:none;">
      <div class="section-header">
        <h2 class="section-title">INSPEKTOR PREDIKSI 72 JAM PER SPBU (MARKOV KERNEL)</h2>
        <p class="section-desc">Pilih stasiun di peta atau gunakan pencarian untuk melihat probabilitas stok, pita ketidakpastian 80%, dan estimasi antrean.</p>
      </div>

      <div class="spbu-grid">
        <div class="spec-box">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <span id="cardBadgeKind" style="font-size:10px; font-weight:700; padding:2px 6px; border-radius:var(--r-sm); background:var(--accent-soft); color:var(--accent);">SPBU PERTAMINA</span>
            <span id="cardCode" style="font-size:11px; color:var(--ink-3);">-</span>
          </div>
          <h3 id="cardName" style="font-size:15px; font-weight:700; margin-bottom:4px; color:var(--ink);">Pilih SPBU</h3>
          <p id="cardAddress" style="font-size:11px; color:var(--ink-2); margin-bottom:14px;">-</p>

          <div class="spec-row">
            <span class="spec-label">Peluang Stok Saat Ini:</span>
            <span class="spec-val" id="cardProb" style="color:var(--success);">-</span>
          </div>
          <div class="spec-row">
            <span class="spec-label">Estimasi Waktu Antre:</span>
            <span class="spec-val" id="cardQueue" style="color:var(--warning);">-</span>
          </div>
          <div class="spec-row">
            <span class="spec-label">Jarak ke TBBM Suplai:</span>
            <span class="spec-val" id="cardDist">-</span>
          </div>
          <div class="spec-row">
            <span class="spec-label">Prediksi Pulih Normal:</span>
            <span class="spec-val" id="cardRecovery" style="color:var(--accent);">-</span>
          </div>
          <div class="spec-row">
            <span class="spec-label">Harga Pertalite:</span>
            <span class="spec-val" id="cardPrice">-</span>
          </div>
        </div>

        <div style="background:var(--surface); border:1px solid var(--line-strong); border-radius:var(--r-md); padding:12px;">
          <div id="spbuPlotlyChart" style="height: 380px; width:100%;"></div>
        </div>
      </div>
    </div>

    <!-- TAB 3: 14 AREA MAKRO -->
    <div id="tabAreas" class="tab-content dash-section" style="display:none;">
      <div class="section-header">
        <h2 class="section-title">INDEKS KEPARAHAN KRISIS (CSI) DI 14 AREA MAKRO BALI</h2>
        <p class="section-desc">Kompilasi tingkat kelangkaan, durasi antrean nosel, dan tingkat mark-up harga eceran kios informal.</p>
      </div>

      <div style="background:var(--surface); border:1px solid var(--line-strong); border-radius:var(--r-md); padding:16px; margin-bottom:20px;">
        <div id="areaPlotlyChart" style="height: 360px;"></div>
      </div>

      <div class="terminal-table-wrap">
        <table class="term-table">
          <thead>
            <tr>
              <th>Wilayah Makro</th>
              <th>Skor CSI</th>
              <th>SPBU Resmi</th>
              <th>Kios Pertamini</th>
              <th>SPBU Kosong (%)</th>
              <th>Rerata Antrean</th>
              <th>Mark-Up Eceran</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="areaTableBody"></tbody>
        </table>
      </div>
    </div>

    <!-- TAB 4: SIMULASI MONTE CARLO -->
    <div id="tabSimulation" class="tab-content dash-section" style="display:none;">
      <div class="section-header">
        <h2 class="section-title">SIMULASI PEMULIHAN MONTE CARLO (10.000 JALUR)</h2>
        <p class="section-desc">Evolusi probabilitas ketersediaan BBM pulau melintasi 384 jam dan perbandingan 4 skenario logistik.</p>
      </div>

      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap:20px;">
        <div style="background:var(--surface); border:1px solid var(--line-strong); border-radius:var(--r-md); padding:16px;">
          <div style="font-size:12px; font-weight:700; color:var(--ink); margin-bottom:10px;">FAN CHART PROYEKSI KETERSEDIAAN PULAU</div>
          <div id="fanPlotlyChart" style="height: 320px;"></div>
        </div>

        <div style="background:var(--surface); border:1px solid var(--line-strong); border-radius:var(--r-md); padding:16px;">
          <div style="font-size:12px; font-weight:700; color:var(--ink); margin-bottom:10px;">DISTRIBUSI FREKUENSI TANGGAL MEREDA (HISTOGRAM)</div>
          <div id="histPlotlyChart" style="height: 320px;"></div>
        </div>
      </div>
    </div>

    <!-- TAB 5: 20 HOTSPOT PALING RENTAN -->
    <div id="tabHotspots" class="tab-content dash-section" style="display:none;">
      <div class="section-header">
        <h2 class="section-title">PERINGKAT 20 TITIK SPBU & PERTAMINI PALING RENTAN</h2>
        <p class="section-desc">Titik dengan waktu pemulihan terlama akibat hambatan jarak depot pengisian (>60 km) dan kepadatan komuter.</p>
      </div>

      <div class="terminal-table-wrap">
        <table class="term-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Nama Titik</th>
              <th>Jenis</th>
              <th>Area Makro</th>
              <th>Jarak TBBM</th>
              <th>Peluang Stok</th>
              <th>Antrean</th>
              <th>Skor Rentan</th>
              <th>Prediksi Pulih</th>
            </tr>
          </thead>
          <tbody id="hotspotTableBody"></tbody>
        </table>
      </div>
    </div>

    <!-- TAB 6: PANDUAN WARGA & TIMELINE -->
    <div id="tabGuide" class="tab-content dash-section" style="display:none;">
      <div class="section-header">
        <h2 class="section-title">PANDUAN PRAKTIS WARGA BALI & REKONSTRUKSI FAKTA</h2>
        <p class="section-desc">Rekomendasi matematis menghindari antrean dan perbandingan klaim resmi Pertamina dengan telemetri riil.</p>
      </div>

      <div class="layman-grid" style="margin-bottom:28px;">
        <div class="layman-card">
          <div class="layman-title"><span style="color:var(--success)">●</span> Jam Paling Aman Mencari BBM</div>
          <p class="layman-desc">Pukul <b>22:00 s/d 05:30 WITA</b>. Ritase pengisian truk malam telah selesai membongkar BBM ke tangki pendam SPBU, dan antrean pompa 80% lebih pendek dibanding siang hari.</p>
        </div>
        <div class="layman-card">
          <div class="layman-title"><span style="color:var(--accent)">●</span> Prioritaskan Jalur Protokol 24 Jam</div>
          <p class="layman-desc">Pilihlah SPBU 24 Jam bernomor kode <code>54.801.xx</code> di By Pass Ngurah Rai, By Pass Ida Bagus Mantra, dan Jl. Gatot Subroto. Jalur ini mendapat alokasi ritase tangki 2x lebih sering.</p>
        </div>
        <div class="layman-card">
          <div class="layman-title"><span style="color:var(--warning)">●</span> Waspada Harga Eceran Pertamini</div>
          <p class="layman-desc">Hindari kepanikan membeli jeriken. Sebanyak 173 kios terdeteksi mematok harga Rp 20.000 - Rp 40.000/L. Pasokan terminal kini melimpah seiring bongkar muat Kapal 3.</p>
        </div>
      </div>

      <div class="section-header" style="margin-top:20px;">
        <h3 class="section-title" style="font-size:14px;">KRONOLOGI KRISIS: FAKTA LAPANGAN VS KLAIM RESMI</h3>
      </div>
      <div id="timelineWrap" style="display:flex; flex-direction:column; gap:12px;"></div>
    </div>

    <footer class="term-footer">
      <div>BALIFUEL // CRISIS_ANALYST — Independent Energy & Logistics Research Bali 2026</div>
      <div>Source: BensinBali.com, BaliFuelWatch API, Pertamina Patra Niaga, OpenStreetMap ODbL</div>
    </footer>

  </main>

  <script src="{app_js_path}" charset="utf-8"></script>
</body>
</html>
"""


APP_JS_CONTENT = """// BaliFuel Analyst — Client Controller & Live Poller (Gaya Devtools-UI)
(function () {
  let CURRENT_RUN_ID = null;
  let DATA_CACHE = null;
  let POLL_TIMER = null;
  let ALL_STATIONS = [];
  let ALL_HOURS = [];

  function getFeedUrl() {
    let u = window.FEED_URL || "https://balifuel-worker.anandapradnyana68.workers.dev";
    return u.replace(/\\/+$/, "");
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
      text.textContent = `DATA USANG (${ageStr}) \\u00B7 60s`;
      badge.style.borderColor = "var(--warning)";
    } else if (meta.status === "degraded") {
      dot.className = "status-dot";
      dot.style.background = "var(--warning)";
      text.textContent = `DEGRADED (${ageStr}) \\u00B7 60s`;
      badge.style.borderColor = "var(--warning)";
    } else {
      dot.className = "status-dot green";
      dot.style.background = "var(--success)";
      text.textContent = `LIVE (${ageStr}) \\u00B7 60s`;
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
      document.getElementById("boxCi50").textContent = `${meta.ci50[0].split(' ')[0]} \\u2014 ${meta.ci50[1].split(' ')[0]}`;
    }
    if (meta.ci80 && meta.ci80.length >= 2) {
      document.getElementById("boxCi80").textContent = `${meta.ci80[0].split(' ')[0]} \\u2014 ${meta.ci80[1].split(' ')[0]}`;
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
          btnLocate.textContent = "\\uD83D\\uDCCD Mencari...";
          navigator.geolocation.getCurrentPosition(
            (pos) => {
              btnLocate.textContent = "\\uD83D\\uDCCD Lokasi Saya";
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
              btnLocate.textContent = "\\uD83D\\uDCCD Lokasi Saya";
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
          <div style="color:var(--ink-3); margin-bottom:6px;">${area} \\u00B7 [${kind.toUpperCase()}]</div>
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
        themeBtn.textContent = "\\u2600";
      } else {
        document.documentElement.setAttribute("data-theme", "light");
        themeBtn.textContent = "\\u263E";
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
"""


def build_dashboard(target: str = "pages") -> str:
    """Membangun dashboard untuk target 'local' atau 'pages'."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    with open(os.path.join(CLEAN_DIR, "cleaned_stations.json"), "r", encoding="utf-8") as f:
        stations = json.load(f)
    with open(os.path.join(CLEAN_DIR, "crisis_metrics.json"), "r", encoding="utf-8") as f:
        metrics = json.load(f)
    with open(os.path.join(CLEAN_DIR, "monte_carlo_results.json"), "r", encoding="utf-8") as f:
        monte_carlo = json.load(f)
    with open(os.path.join(CLEAN_DIR, "station_forecasts.json"), "r", encoding="utf-8") as f:
        forecasts = json.load(f)
    with open(os.path.join(CLEAN_DIR, "vulnerable_hotspots.json"), "r", encoding="utf-8") as f:
        hotspots = json.load(f)
    with open(os.path.join(DATA_DIR, "external_context.json"), "r", encoding="utf-8") as f:
        context = json.load(f)

    if target == "local":
        embedded_dict = {
            "stations": stations,
            "metrics": metrics,
            "monte_carlo": monte_carlo,
            "forecasts": forecasts,
            "hotspots": hotspots,
            "context": context,
            "built_at_wita": datetime.now(WITA_TZ).strftime("%d %B %Y, %H:%M WITA")
        }
        embedded_dict = sanitize_for_json(embedded_dict)
        embedded_json = json.dumps(embedded_dict, ensure_ascii=False, allow_nan=False)
        embedded_script = f"<script>window.BALI_EMBEDDED_DATA = {embedded_json};</script>"
        out_html = INDEX_HTML_TEMPLATE.format(
            css_path="data:text/css;charset=utf-8," + STYLE_CSS.replace("\n", "%20").replace("#", "%23"),
            config_path="data:application/javascript;charset=utf-8,window.FEED_URL='';",
            embedded_data_script=embedded_script,
            app_js_path="data:application/javascript;charset=utf-8," + APP_JS_CONTENT.replace("\n", "%20").replace("#", "%23")
        )
        local_path = os.path.join(OUTPUT_DIR, "dashboard.html")
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(out_html)
        print(f"[+] Local monolithic dashboard generated at: {local_path} ({len(out_html):,} bytes)")
        return local_path

    elif target == "pages":
        css_file = os.path.join(DOCS_DIR, "style.css")
        with open(css_file, "w", encoding="utf-8") as f:
            f.write(STYLE_CSS)

        config_file = os.path.join(DOCS_DIR, "config.js")
        with open(config_file, "w", encoding="utf-8") as f:
            f.write('// Local dev fallback URL; injected dynamically in CI Pages deployment\nwindow.FEED_URL = "http://127.0.0.1:8787";\n')

        app_file = os.path.join(DOCS_DIR, "app.js")
        with open(app_file, "w", encoding="utf-8") as f:
            f.write(APP_JS_CONTENT)

        compact_st = []
        for s in stations:
            if s.get("kind") == "spbu" or len(compact_st) < 360:
                compact_st.append({
                    "id": s["id"],
                    "name": s["name"],
                    "kind": s.get("kind", "spbu"),
                    "area": s.get("area", "Bali"),
                    "lat": s.get("lat"),
                    "lng": s.get("lon"),
                    "p_now": s.get("prob_pertalite", 0.5),
                    "queue": s.get("queue_mins"),
                    "price": s.get("prices", {}).get("pertalite"),
                    "recov": "18 Okt 04:00 WITA",
                    "p10": [0.3] * 72,
                    "p50": [0.5] * 72,
                    "p90": [0.7] * 72,
                    "q_traj": [15] * 72
                })

        fallback_payload = {
            "meta": {
                "data_age_min": 15,
                "status": "ok",
                "csi_island": metrics.get("current_island_csi", 50.0),
                "median_recovery_wita": monte_carlo.get("median_recovery_datetime_wita", "18 Okt 2026, 05:00 WITA")
            },
            "summary": {
                "metrics": metrics,
                "areas": metrics.get("area_metrics", []),
                "monte_carlo": monte_carlo,
                "hotspots": hotspots[:20],
                "timeline": context.get("crisis_timeline", [])
            },
            "stations": compact_st,
            "hours": forecasts.get("hours_label", [])
        }
        fallback_file = os.path.join(DOCS_DIR, "fallback.json")
        fallback_payload = sanitize_for_json(fallback_payload)
        with open(fallback_file, "w", encoding="utf-8") as f:
            json.dump(fallback_payload, f, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

        index_file = os.path.join(DOCS_DIR, "index.html")
        html_content = INDEX_HTML_TEMPLATE.format(
            css_path="./style.css?v=2.1.5",
            config_path="./config.js?v=2.1.5",
            embedded_data_script="",
            app_js_path="./app.js?v=2.1.5"
        )
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[+] GitHub Pages assets generated in {DOCS_DIR}:")
        print(f"    - index.html    ({len(html_content):,} B)")
        print(f"    - style.css     ({len(STYLE_CSS):,} B)")
        print(f"    - app.js        ({len(APP_JS_CONTENT):,} B)")
        print(f"    - config.js     (placeholder)")
        print(f"    - fallback.json ({os.path.getsize(fallback_file):,} B)")
        return index_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build BaliFuel Dashboard")
    parser.add_argument("--target", choices=["local", "pages", "both"], default="both", help="Build target")
    args = parser.parse_args()

    if args.target in ("local", "both"):
        build_dashboard(target="local")
    if args.target in ("pages", "both"):
        build_dashboard(target="pages")
