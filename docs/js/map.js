// BaliFuel Analyst — Leaflet Map Module (100% Bebas API Key, OpenStreetMap Murni)
(function () {
  let mapInstance = null;
  let markersLayer = null;
  let STATIONS_DATA = [];
  let HOURS_DATA = [];

  function initMap() {
    if (mapInstance) return;
    const mapEl = document.getElementById("map");
    if (!mapEl) return;

    mapInstance = L.map("map", {
      attributionControl: true,
      zoomControl: true,
      touchZoom: true,
      scrollWheelZoom: true,
      doubleClickZoom: true,
      boxZoom: true,
      zoomSnap: 0.5,
      zoomDelta: 0.5,
      wheelDebounceTime: 40,
      wheelPxPerZoomLevel: 60,
      tap: false
    }).setView([-8.48, 115.18], 10);

    // Cegah peramban melakukan pinch-to-zoom pada level halaman web saat mencubit peta
    mapEl.addEventListener("touchstart", (e) => {
      // Izinkan touch normal, Leaflet internal touchZoom akan menangani perhitungan pinch
    }, { passive: true });

    mapEl.addEventListener("touchmove", (e) => {
      if (e.touches && e.touches.length > 1) {
        // Multi-touch: cegah browser zoom halaman web, serahkan zoom ke Leaflet
        if (e.cancelable) e.preventDefault();
      }
    }, { passive: false });

    // Cegah gesture pinch bawaan iOS Safari pada area peta
    mapEl.addEventListener("gesturestart", (e) => { if (e.cancelable) e.preventDefault(); }, { passive: false });
    mapEl.addEventListener("gesturechange", (e) => { if (e.cancelable) e.preventDefault(); }, { passive: false });
    mapEl.addEventListener("gestureend", (e) => { if (e.cancelable) e.preventDefault(); }, { passive: false });
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

    // Bind Filter Change Events
    const selKind = document.getElementById("filterKind");
    const selArea = document.getElementById("filterArea");
    const selStatus = document.getElementById("filterStatus");

    if (selKind) selKind.addEventListener("change", renderMapPins);
    if (selArea) selArea.addEventListener("change", renderMapPins);
    if (selStatus) selStatus.addEventListener("change", renderMapPins);

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

    // Tombol Zoom In & Zoom Out Toolbar
    const btnZoomIn = document.getElementById("btnZoomIn");
    if (btnZoomIn) {
      btnZoomIn.addEventListener("click", () => {
        if (mapInstance) mapInstance.zoomIn();
      });
    }

    const btnZoomOut = document.getElementById("btnZoomOut");
    if (btnZoomOut) {
      btnZoomOut.addEventListener("click", () => {
        if (mapInstance) mapInstance.zoomOut();
      });
    }

    setTimeout(() => mapInstance.invalidateSize(), 200);
  }

  function updateAreaDropdown(stations) {
    const areaSelect = document.getElementById("filterArea");
    if (!areaSelect || areaSelect.children.length > 2) return;
    const areaSet = new Set(stations.map(s => s.area).filter(Boolean));
    Array.from(areaSet).sort().forEach(a => {
      const opt = document.createElement("option");
      opt.value = a;
      opt.textContent = a;
      areaSelect.appendChild(opt);
    });
  }

  function renderMapPins() {
    if (!markersLayer) return;
    markersLayer.clearLayers();

    const fKind = document.getElementById("filterKind") ? document.getElementById("filterKind").value : "all";
    const fArea = document.getElementById("filterArea") ? document.getElementById("filterArea").value : "all";
    const fStatus = document.getElementById("filterStatus") ? document.getElementById("filterStatus").value : "all";

    const stations = STATIONS_DATA;
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
      let statusSymbol = "✖ KOSONG";
      let statusBadge = "[✖ KOSONG]";
      let dashStyle = "2, 3";
      if (p >= 0.60) {
        color = "#22C55E";
        statusSymbol = "✔ ADA BENSIN";
        statusBadge = "[✔ ADA BENSIN]";
        dashStyle = null;
      } else if (p >= 0.35) {
        color = "#FF8A3D";
        statusSymbol = "▲ ANTRE / MENIPIS";
        statusBadge = "[▲ ANTRE / MENIPIS]";
        dashStyle = "4, 2";
      }

      const isSpbu = kind === "spbu";
      const marker = L.circleMarker([lat, lng], {
        radius: isSpbu ? 7.5 : 4.5,
        fillColor: color,
        color: "#000000",
        weight: 1.8,
        opacity: 1.0,
        fillOpacity: 0.9,
        dashArray: dashStyle
      });

      const qText = s.queue != null ? (s.queue >= 60 ? `${Math.floor(s.queue/60)}j ${Math.round(s.queue%60)}m` : `${s.queue} mnt`) : "Belum ada laporan";
      const priceText = s.price ? `Rp ${Number(s.price).toLocaleString()}/L` : (isSpbu ? "Rp 10.000/L (HET)" : "-");

      const popupHtml = `
        <div style="font-size:11px; line-height:1.5; min-width:215px; font-family:var(--f-mono);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
            <div style="font-weight:700; color:var(--accent); font-size:12px;">${s.name || 'SPBU'}</div>
            <span style="font-size:10px; font-weight:700; color:${color};">${statusBadge}</span>
          </div>
          <div style="color:var(--ink-3); margin-bottom:6px;">${area} \u00B7 [${kind.toUpperCase()}]</div>
          <div style="border-top:1px solid var(--line-strong); padding:6px 0;">
            <div>Peluang ada bensin: <b style="color:${color}">${statusSymbol} · ${Math.round(p * 100)}%</b></div>
            <div>Waktu antre: <b>${qText}</b></div>
            <div>Harga Pertalite: <b>${priceText}</b></div>
          </div>
          <!-- FORM SURVEY WARGA -->
          <div style="border-top:1px dashed var(--line-strong); margin-top:6px; padding-top:6px;">
            <div style="font-weight:700; color:var(--ink); font-size:10px; margin-bottom:4px;">
              \uD83D\uDCE2 Anda sedang di SPBU ini? \u2014 Pertalite
            </div>
            <div style="display:flex; gap:4px; margin-bottom:5px;">
              <button id="pAvailYes_${s.id}" type="button" style="flex:1; padding:3px 0; font-size:10px; background:var(--surface); border:1px solid var(--line-strong); color:var(--ink); border-radius:3px; cursor:pointer;">
                \uD83D\uDC4D Ada
              </button>
              <button id="pAvailNo_${s.id}" type="button" style="flex:1; padding:3px 0; font-size:10px; background:var(--surface); border:1px solid var(--line-strong); color:var(--ink); border-radius:3px; cursor:pointer;">
                \u274C Tidak ada
              </button>
            </div>
            <div style="font-size:9px; color:var(--ink-3); margin-bottom:3px;">Waktu tunggu (opsional):</div>
            <div style="display:flex; gap:3px; margin-bottom:6px;">
              <button id="pWait0_${s.id}" type="button" style="flex:1; padding:2px; font-size:9px; background:var(--surface); border:1px solid var(--line-strong); color:var(--ink); border-radius:2px; cursor:pointer;">Singkat</button>
              <button id="pWait1_${s.id}" type="button" style="flex:1; padding:2px; font-size:9px; background:var(--surface); border:1px solid var(--line-strong); color:var(--ink); border-radius:2px; cursor:pointer;">Lama (&lt;2j)</button>
              <button id="pWait2_${s.id}" type="button" style="flex:1; padding:2px; font-size:9px; background:var(--surface); border:1px solid var(--line-strong); color:var(--ink); border-radius:2px; cursor:pointer;">Sangat Lama (&lt;5j)</button>
            </div>
            <button id="pSend_${s.id}" type="button" style="width:100%; height:24px; background:var(--accent); color:#000; border:0; border-radius:3px; font-weight:700; font-size:10px; cursor:pointer;">
              Kirim Laporan Bensin
            </button>
            <div id="pFeed_${s.id}" style="font-size:9px; margin-top:4px; text-align:center; display:none;"></div>
          </div>
          <button id="popBtn_${s.id}" style="margin-top:6px; width:100%; height:24px; background:transparent; color:var(--ink-2); border:1px solid var(--line-strong); border-radius:3px; font-size:10px; cursor:pointer;">
            Lihat Perkiraan 3 Hari ke Depan \u2193
          </button>
        </div>
      `;

      marker.bindPopup(popupHtml);
      marker.on("click", () => {
        if (window.BaliCharts && window.BaliCharts.selectStation) {
          window.BaliCharts.selectStation(s, HOURS_DATA);
        }
        if (window.BaliSurvey) {
          window.BaliSurvey.setStationId(s.id);
        }
      });
      marker.on("popupopen", () => {
        let popAvail = null;
        let popWait = null;
        const btnYes = document.getElementById(`pAvailYes_${s.id}`);
        const btnNo = document.getElementById(`pAvailNo_${s.id}`);
        const btnW0 = document.getElementById(`pWait0_${s.id}`);
        const btnW1 = document.getElementById(`pWait1_${s.id}`);
        const btnW2 = document.getElementById(`pWait2_${s.id}`);
        const btnSend = document.getElementById(`pSend_${s.id}`);
        const feedEl = document.getElementById(`pFeed_${s.id}`);

        if (btnYes && btnNo) {
          btnYes.onclick = () => {
            btnYes.style.background = "var(--accent)";
            btnYes.style.color = "#000";
            btnNo.style.background = "var(--surface)";
            btnNo.style.color = "var(--ink)";
            popAvail = true;
          };
          btnNo.onclick = () => {
            btnNo.style.background = "var(--accent)";
            btnNo.style.color = "#000";
            btnYes.style.background = "var(--surface)";
            btnYes.style.color = "var(--ink)";
            popAvail = false;
          };
        }

        [btnW0, btnW1, btnW2].forEach((b, idx) => {
          if (b) {
            b.onclick = () => {
              [btnW0, btnW1, btnW2].forEach(x => { if (x) { x.style.background = "var(--surface)"; x.style.color = "var(--ink)"; } });
              b.style.background = "var(--accent-soft)";
              b.style.color = "var(--accent)";
              popWait = idx;
            };
          }
        });

        if (btnSend) {
          btnSend.onclick = () => {
            if (popAvail === null) {
              if (feedEl) {
                feedEl.style.display = "block";
                feedEl.style.color = "var(--danger)";
                feedEl.textContent = "Pilih Ada / Tidak ada dulu.";
              }
              return;
            }
            if (window.submitPopupSurvey) {
              if (feedEl) feedEl.style.display = "block";
              window.submitPopupSurvey(s.id, popAvail, popWait, `pFeed_${s.id}`);
            }
          };
        }

        const btn = document.getElementById(`popBtn_${s.id}`);
        if (btn) {
          btn.onclick = () => {
            if (window.BaliCharts && window.BaliCharts.selectStation) {
              window.BaliCharts.selectStation(s, HOURS_DATA);
            }
            const fc = document.getElementById("tabForecast");
            if (fc) {
              fc.scrollIntoView({ behavior: "smooth", block: "start" });
            }
          };
        }
      });

      markersLayer.addLayer(marker);
    });
  }

  function setStations(stations, hours) {
    STATIONS_DATA = stations || [];
    HOURS_DATA = hours || [];
    initMap();
    updateAreaDropdown(STATIONS_DATA);
    renderMapPins();
    if (window.BaliCharts && window.BaliCharts.initHours) {
      window.BaliCharts.initHours(HOURS_DATA);
    }
  }

  // Listen to data updates from api.js
  window.addEventListener("dataupdated", (e) => {
    const data = e.detail;
    const stList = data.stations || [];
    const hours = data.hours || data.forecasts?.hours_label || [];
    setStations(stList, hours);
  });

  window.BaliMap = {
    init: initMap,
    setStations: setStations,
    renderPins: renderMapPins,
    invalidateSize: () => { if (mapInstance) mapInstance.invalidateSize(); },
    zoomIn: () => { if (mapInstance) mapInstance.zoomIn(); },
    zoomOut: () => { if (mapInstance) mapInstance.zoomOut(); },
    getStations: () => STATIONS_DATA
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMap);
  } else {
    initMap();
  }
})();
