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
      marker.on("click", () => {
        if (window.BaliCharts && window.BaliCharts.selectStation) {
          window.BaliCharts.selectStation(s, HOURS_DATA);
        }
      });
      marker.on("popupopen", () => {
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
    getStations: () => STATIONS_DATA
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMap);
  } else {
    initMap();
  }
})();
