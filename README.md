# Bali Fuel Crisis Analyst (Oktober 2026)

Sistem terintegrasi end-to-end untuk analisis, simulasi Monte Carlo, prediksi per SPBU, dan pelaporan visual krisis distribusi bahan bakar minyak (Pertalite, Pertamax, Solar) di Provinsi Bali pada Oktober 2026.

---

## 🚀 Fitur Utama & Kemampuan Sistem

1. **Pengumpulan Data Mentah JSON-First**:
   - Menghubungkan endpoint langsung dari `balifuelwatch.vercel.app` (`/api/stats`, `/api/metrics`, `/api/reports?w=day&f=2`, `/odbl-stations.json`) dan tag `<script id="fuel-data">` pada `bensinbali.com`.
   - Mengarsipkan JSON mentah ke `data/raw/` dan mengompilasi basis data relasional SQLite `data/balifuel.db` dengan stempel waktu UTC & WITA.
   - Mode polling periodik daemon/cron (`python src/collector.py --daemon --interval 300`) dengan perhitungan turunan laju (*rate derivatives*) yang tahan terhadap *counter reset*.

2. **Pembersihan & Kualitas Data Berstandar Statistik**:
   - **Pembobotan Peluruhan Waktu Eksponensial**: $\tau_{half} = 90$ menit untuk meredam laporan kedaluwarsa.
   - **Pengali Bobot Konfirmasi**: Bobot $1.35\times$ untuk laporan berstatus antrean dan $1.5\times$ untuk laporan langsung dari nosel pompa.
   - **Normalisasi Kepanikan Pengguna**: Meredam bias keluhan stok habis akibat lonjakan pengguna online.
   - **Imputasi Spasial k-NN IDW**: SPBU tanpa kabar diestimasi dari 3 SPBU terdekat dengan penandaan eksplisit `imputed_spatial` dan skor ketidakpastian. Titik liar di luar batas laut Bali dikarantina otomatis.
   - **Pemetaan Kanonikal 14 Area Makro**: Canggu, Seminyak-Kuta, Bukit, Sanur, Denpasar, Mengwi, Ubud, Gianyar, Tabanan, Klungkung, Karangasem, Bangli, Lovina, dan Jembrana.

3. **Pemodelan Markov & Evaluasi Backtest Objektif**:
   - *Inhomogeneous Continuous-Time Markov Chain* memodelkan probabilitas ketersediaan stok tiap jam berdasarkan penalti jarak depot TBBM Sanggaran/Manggis, jam operasional 24 jam, dan siklus jam sibuk diurnal.
   - Diuji menggunakan *rolling backtest* pada 4.571 laporan aktual:
     * **Markov Model**: Brier Score = **0.1872** (Terbaik), Akurasi = **71.8%**.
     * **Kaplan-Meier Survival**: Brier Score = 0.2405, Akurasi = 59.9%.
     * **Simple EMA Trend**: Brier Score = 0.1920, Akurasi = 71.5%.

4. **Simulasi Monte Carlo Pemulihan (10.000 Jalur)**:
   - Mengevaluasi 4 skenario terkalibrasi (*Fast Resupply*, *Gradual Base-Case 26.200 KL*, *Prolonged Disruption*, dan *Second Wave Panic*).
   - **Kriteria Krisis Mereda**: <10% SPBU kosong (&ge;90% ada stok) bertahan 48 jam berturut-turut.
   - **Median Tanggal Pemulihan**: **Minggu, 18 Oktober 2026, 05:00 WITA**.
   - Interval Kredibel 50% (17 Okt 09:00 – 19 Okt 06:00) dan 80% (17 Okt 02:00 – 22 Okt 07:00).
   - Analisis Sensitivitas: Kapasitas armada truk darat merupakan faktor paling sensitif ($r = -0.744$).

5. **Visualisasi Interaktif Standalone (Zero-Backend)**:
   - Dashboard HTML responsif tunggal (`output/dashboard.html`) memadukan Leaflet peta Bali, Plotly chart, filter interaktif (BBM, Area, SPBU/Pertamini), dark mode, dan pencarian instan.
   - Seluruh data ditanam langsung ke dalam file HTML sehingga bebas CORS dan dapat dibuka langsung via browser (`file:///...`).
   - Direktori `output/spbu/` berisi grafik mandiri (SVG/PNG) untuk setiap SPBU yang memuat kurva 72 jam, pita ketidakpastian (P10–P90), dan proyeksi antrean.

---

## 📁 Struktur Repositori

```text
balifuel-analyst/
├── data/
│   ├── raw/                       # Arsip JSON mentah dari setiap polling/snapshot
│   ├── clean/                     # Parquet & JSON bersih hasil rekayasa data
│   │   ├── cleaned_stations.json
│   │   ├── cleaned_hourly.json
│   │   ├── crisis_metrics.json
│   │   ├── markov_and_survival_analysis.json
│   │   ├── monte_carlo_results.json
│   │   ├── station_forecasts.json
│   │   └── vulnerable_hotspots.json
│   ├── balifuel.db                # Basis data relasional SQLite
│   ├── external_context.json      # Catatan fakta, berita resmi, dan parameter logistik
│   └── ENDPOINTS.md               # Dokumentasi endpoint, parameter, dan cache policy
├── src/
│   ├── collector.py               # Polling endpoint & bootstrap time series
│   ├── cleaner.py                 # Pembobotan waktu, spam filter, imputasi spasial
│   ├── metrics.py                 # Perhitungan CSI, analisis 14 area, CUSUM change-point
│   ├── markov_model.py            # Pemodelan Markov, Kaplan-Meier, & rolling backtest
│   ├── simulation.py              # Engine Monte Carlo 10.000 jalur & distribusi waktu
│   ├── forecast.py                # Proyeksi 72 jam per SPBU & ranking 20 hotspot rentan
│   ├── visualizer.py              # Generator visualisasi SVG/PNG per SPBU
│   └── dashboard_builder.py       # Pembangun dashboard interaktif mandiri
├── output/
│   ├── dashboard.html             # Dashboard interaktif utama (buka di browser)
│   ├── laporan.md                 # Laporan ilmiah & analisis teknis komprehensif
│   └── spbu/                      # Grafik visual mandiri tiap SPBU (.svg)
├── run_pipeline.py                # Script eksekusi satu perintah seluruh sistem
└── README.md                      # Dokumentasi teknis & panduan reproduksi
```

---

## ⚡ Cara Menjalankan Ulang (Reproduction Guide)

### 1. Menjalankan Seluruh Pipeline dengan Satu Perintah
Untuk mengeksekusi pengumpulan data, pembersihan, pemodelan Markov, simulasi Monte Carlo 10.000 jalur, peramalan per SPBU, hingga pembentukan dashboard HTML dan grafik:

```bash
python run_pipeline.py
```
*Opsi tambahan*:
```bash
python run_pipeline.py --all-charts   # Menghasilkan file SVG untuk seluruh 232 SPBU resmi + hotspot
```

### 2. Membuka Dashboard Visual
Buka file dashboard interaktif di browser web mana pun:
- Windows: Cukup klik ganda pada `output/dashboard.html` atau jalankan via terminal:
  ```bash
  start output/dashboard.html
  ```
- macOS:
  ```bash
  open output/dashboard.html
  ```
- Linux:
  ```bash
  xdg-open output/dashboard.html
  ```

### 3. Menjalankan Polling Berkala (Daemon / Cron Mode)
Untuk mengambil snapshot endpoint setiap 5 menit (300 detik) secara berkelanjutan ke SQLite dan `data/raw/`:

```bash
python src/collector.py --daemon --interval 300
```

### 4. Menjalankan Modul Individual
Setiap komponen dapat dijalankan secara terpisah:
```bash
# 1. Koleksi snapshot sekali jalan
python src/collector.py

# 2. Pembersihan & imputasi spasial
python src/cleaner.py

# 3. Hitung indeks keparahan krisis (CSI) & 14 area
python src/metrics.py

# 4. Uji model Markov & backtest
python src/markov_model.py

# 5. Simulasi Monte Carlo 10.000 jalur
python src/simulation.py

# 6. Buat ramalan 72 jam per SPBU & ranking hotspot
python src/forecast.py

# 7. Render grafik visual SPBU ke output/spbu/
python src/visualizer.py

# 8. Render dashboard HTML
python src/dashboard_builder.py
```

---

## 📊 Hasil Utama & Angka Ringkas

- **Skor Keparahan Krisis (CSI) Terkini**: **49.0 / 100** (Status: *Pemulihan Bertahap / Kuning*).
- **Puncak Keparahan Krisis**: **CSI 54.1** pada 15 Oktober 2026 pukul 23:00 WITA.
- **Prediksi Krisis Mereda**: **Minggu, 18 Oktober 2026, pukul 05:00 WITA** (+50 jam).
- **Rentang Kredibel 50%**: 17 Oktober 09:00 WITA s/d 19 Oktober 06:00 WITA.
- **Area Paling Kritis**: Ubud (CSI 60.1), Karangasem (CSI 60.0), Bukit Kuta Selatan (CSI 59.1).
- **Titik Paling Rentan**: SPBU dan Pertamini di Lovina (Buleleng) dan Jembrana yang berjarak >65 km dari TBBM Sanggaran/Manggis.
- **Kios Pertamini Mengalami Mark-Up**: 173 titik menjual Pertalite antara Rp 15.000 hingga Rp 40.000/liter.

---
*Dikembangkan secara otonom untuk riset krisis energi dan logistik publik Bali 2026.*
