# Bali Fuel Crisis Analyst (Oktober 2026)

Sistem terintegrasi end-to-end untuk analisis, simulasi Monte Carlo 10.000 jalur, prediksi per SPBU, otomasi pipeline data ke Cloudflare Edge, dan publikasi web interaktif di GitHub Pages.

Dokumentasi arsitektur, diagram alur, konfigurasi Cloudflare Worker, dan estimasi kuota gratis tersedia di **[`ARSITEKTUR.md`](./ARSITEKTUR.md)**.

---

## 🚀 Fitur Utama & Kemampuan Sistem

1. **Pengumpulan Data Mentah JSON-First & Cuaca Maritim**:
   - Menghubungkan endpoint langsung dari `balifuelwatch.vercel.app` (`/api/stats`, `/api/metrics`, `/api/reports?w=day&f=2`, `/odbl-stations.json`) dan tag `<script id="fuel-data">` pada `bensinbali.com`.
   - Mengumpulkan data maritim pendekatan terminal (TBBM Sanggaran & Manggis) via Open-Meteo Marine API, serta prakiraan BMKG.
   - Mengarsipkan data ke SQLite `data/balifuel.db` dengan stempel waktu UTC & WITA.

2. **Pembersihan & Kualitas Data Berstandar Statistik**:
   - **Pembobotan Peluruhan Waktu Eksponensial**: $\tau_{half} = 90$ menit untuk meredam laporan usang.
   - **Pengali Bobot Konfirmasi**: Bobot $1.35\times$ untuk status antrean terkonfirmasi dan $1.5\times$ untuk nosel pompa langsung.
   - **Normalisasi Kepanikan Pengguna**: Meredam bias keluhan akibat lonjakan pengguna online.
   - **Imputasi Spasial k-NN IDW**: SPBU tanpa kabar diestimasi dari 3 SPBU terdekat dengan penandaan eksplisit `imputed_spatial` dan skor ketidakpastian. Titik liar laut dikarantina.
   - **Pemetaan Kanonikal 14 Area Makro**: Canggu, Seminyak-Kuta, Bukit, Sanur, Denpasar, Mengwi, Ubud, Gianyar, Tabanan, Klungkung, Karangasem, Bangli, Lovina, dan Jembrana.

3. **Pemodelan Markov & Evaluasi Backtest Objektif**:
   - *Inhomogeneous Continuous-Time Markov Chain* memodelkan probabilitas ketersediaan stok tiap jam berdasarkan penalti jarak depot TBBM Sanggaran/Manggis, jam operasional 24 jam, dan siklus jam sibuk diurnal.
   - Diuji menggunakan *rolling backtest* pada 4.590 laporan aktual:
     * **Markov Model**: Brier Score = **0.1896** (Terbaik), Akurasi = **71.5%**.
     * **Kaplan-Meier Survival**: Brier Score = 0.2412, Akurasi = 59.4%.
     * **Simple EMA Trend**: Brier Score = 0.1943, Akurasi = 71.2%.

4. **Simulasi Monte Carlo Pemulihan (10.000 Jalur)**:
   - Mengevaluasi 4 skenario terkalibrasi (*Fast Resupply*, *Gradual Base-Case 26.200 KL*, *Prolonged Disruption*, dan *Second Wave Panic*).
   - **Kriteria Krisis Mereda**: <10% SPBU kosong (&ge;90% ada stok) bertahan 48 jam berturut-turut.
   - **Median Tanggal Pemulihan**: **Minggu, 18 Oktober 2026, 05:00 WITA**.
   - Interval Kredibel 50% (17 Okt 09:00 – 19 Okt 07:00) dan 80% (17 Okt 03:00 – 22 Okt 07:00).
   - Analisis Sensitivitas: Kapasitas armada truk darat merupakan faktor paling sensitif ($r = -0.745$).

5. **Lapisan Otomasi & Publikasi Edge (Cloudflare Worker + R2 + GitHub Pages)**:
   - **Pemicu**: Worker Cron Trigger setiap 10 menit memicu `.github/workflows/pipeline.yml` via GitHub API `workflow_dispatch`.
   - **Data Board Publik**: Worker menyajikan `/latest/meta.json` (<2 KB), `/latest/summary.json`, `/latest/stations.json` (<1.5 MB), dan `/latest/history.json` dengan CORS dan ETag caching 60 detik.
   - **State Persistence**: SQLite `balifuel.db` disimpan di R2 privat (`/state/balifuel.db`), diunduh di awal runner job, dipangkas retensi 14 hari + `VACUUM`, dan diunggah kembali di akhir job.
   - **Frontend GitHub Pages**: Statis di direktori `docs/` (terminal developer-tool aesthetic dengan JetBrains Mono & aksen orange `#FF8A3D`), mengambil data via polling live 120–180 detik.

---

## 📁 Struktur Repositori

```text
balifuel-analyst/
├── .github/
│   └── workflows/
│       ├── pipeline.yml           # Runner komputasi data (trigger: workflow_dispatch)
│       └── pages.yml              # Deploy GitHub Pages saat docs/** berubah
├── worker/                        # Cloudflare Worker data board & cron trigger
│   ├── src/index.js               # Route /latest, /ingest, /state, & scheduled handler
│   ├── wrangler.toml              # Konfigurasi R2 bucket balifuel-storage & cron 10m
│   └── package.json
├── docs/                          # Frontend GitHub Pages (terminal developer-tool aesthetic)
│   ├── index.html                 # Halaman utama ramping (aset relatif)
│   ├── style.css                  # Desain sistem monospace terminal
│   ├── app.js                     # Controller live polling, map Leaflet, Plotly chart
│   ├── config.js                  # Konfigurasi FEED_URL (disuntikkan di CI)
│   └── fallback.json              # Data cadangan darurat jika Worker offline
├── data/
│   ├── ENDPOINTS.md               # Dokumentasi endpoint API, parameter, & cache policy
│   ├── external_context.json      # Catatan fakta, berita resmi, & parameter logistik
│   └── clean/                     # Berkas artefak bersih
├── src/
│   ├── collector.py               # Polling endpoint data, cuaca maritim Open-Meteo & BMKG
│   ├── cleaner.py                 # Pembobotan waktu, spam filter, imputasi spasial
│   ├── metrics.py                 # Perhitungan CSI, analisis 14 area, CUSUM change-point
│   ├── markov_model.py            # Pemodelan Markov, Kaplan-Meier, & rolling backtest
│   ├── simulation.py              # Engine Monte Carlo 10.000 jalur & distribusi waktu
│   ├── forecast.py                # Proyeksi 72 jam per SPBU & ranking 20 hotspot rentan
│   ├── visualizer.py              # Generator visualisasi SVG/PNG per SPBU (lokal)
│   ├── publish.py                 # Bundler 4 kontrak data & sinkronisasi state R2
│   └── dashboard_builder.py       # Pembangun dashboard lokal (output/) & pages (docs/)
├── output/                        # Artefak lokal (dashboard.html monolitik, spbu/*.svg, laporan.md)
├── run_pipeline.py                # Runner master eksekusi seluruh sistem
├── ARSITEKTUR.md                  # Dokumentasi arsitektur, diagram alur, & kuota gratis
└── README.md                      # Dokumentasi teknis & panduan reproduksi
```

---

## ⚡ Cara Menjalankan

### 1. Menjalankan Analisis Lokal Lengkap
```bash
python run_pipeline.py
```
Membuka dashboard hasil build lokal:
- Windows: `start output/dashboard.html`
- macOS: `open output/dashboard.html`
- Linux: `xdg-open output/dashboard.html`

### 2. Menjalankan Pipeline Mode Publikasi (Dry-Run / Live)
```bash
# Uji coba pembuatan 4 kontrak data tanpa unggah (ke ./publish_out)
python run_pipeline.py --dry-run

# Publikasi ke Cloudflare Worker lokal / produksi
python run_pipeline.py --publish --worker-url "http://127.0.0.1:8787" --token "TOKEN_ANDA"
```

### 3. Menjalankan Polling Kolektor Berkelanjutan (Daemon)
```bash
python src/collector.py --daemon --interval 300
```

### 4. Menjalankan Worker Lokal
```bash
cd worker
npx wrangler dev
```

---

## 📊 Hasil Kunci Kuantitatif

- **Skor Keparahan Krisis (CSI) Terkini**: **50.0 / 100** (Status: *Pemulihan Bertahap / Kuning*).
- **Puncak Keparahan Krisis**: **CSI 54.1** pada 15 Oktober 2026 pukul 23:00 WITA.
- **Prediksi Krisis Mereda**: **Minggu, 18 Oktober 2026, pukul 05:00 WITA** (+50 jam).
- **Rentang Kredibel 50%**: 17 Oktober 09:00 WITA s/d 19 Oktober 07:00 WITA.
- **Area Paling Kritis**: Karangasem (CSI: 60.0), Ubud (CSI: 59.8), Bukit Kuta Selatan (CSI: 59.7).
- **Titik Paling Rentan**: SPBU dan Pertamini di Lovina (Buleleng) dan Jembrana (>65 km dari TBBM Sanggaran/Manggis).
- **Kios Pertamini Mengalami Mark-Up**: 173 titik menjual Pertalite antara Rp 15.000 hingga Rp 40.000/liter.
