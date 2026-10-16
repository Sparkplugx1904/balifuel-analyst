# Bali Fuel Crisis & Panic Buying Analyst (Oktober 2026)

Sistem intelijen data otonom terintegrasi *end-to-end* untuk analisis krisis BBM Bali 2026: mengumpulkan data multi-sumber, melakukan *entity resolution* kanonikal SPBU, mengekstraksi 32 fitur spasial-temporal, menjalankan 12 eksperimen inovasi model, memprediksi titik balik pemulihan pulau via Monte Carlo (10.000 jalur), memetakan penularan *panic buying*, dan menerbitkan dasbor interaktif mandiri.

Dokumentasi arsitektur, diagram alur, konfigurasi Cloudflare Worker, dan estimasi kuota gratis tersedia di **[`ARSITEKTUR.md`](./ARSITEKTUR.md)**.  
Kamus fitur lengkap tersedia di **[`output/feature_dictionary.md`](./output/feature_dictionary.md)**.  
Laporan korelasi dan jawaban 8 pertanyaan krisis di **[`output/laporan_korelasi.md`](./output/laporan_korelasi.md)**.  
Model Card resmi di **[`output/panic_model_card.md`](./output/panic_model_card.md)**.  

---

## 🚀 Fitur Utama & Kemampuan Sistem

1. **Penemuan & Registri 42 Sumber Data (Kategori A–J)**:
   - **Katalog Terverifikasi**: 42 kandidat sumber terdaftar di `data/sources/registry.csv` dan `data/sources/CATALOG.md`, dengan 25 sumber terverifikasi *live* (HTTP 200/OK dengan skema teruji).
   - **Log Penelusuran**: Seluruh percobaan dan strategi pencarian dicatat detail pada `crawl_log.md`.

2. **Master SPBU Kanonik & Entity Resolution**:
   - Master dataset `data/master/spbu.parquet` memetakan **1.042 entitas kanonik** di Bali:
     * **391 SPBU Resmi Pertamina** (Cakupan 100.0% terhadap target ~214 stasiun benchmark).
     * **71 Pertashop Modular Resmi**.
     * **580 Kios Pertamini / Penjual Eceran**.
   - Normalisasi kode Pertamina standar (`54.80X.XX`), pencocokan spasial Haversine $\le 150\text{ m}$, dan fuzzy name matching.
   - Kasus perbatasan spasial (16 kasus) dipisahkan secara transparan di `data/master/review.csv`.

3. **6 Collector Mandiri dengan Degradasi Mulus (`src/collectors/`)**:
   - `marine_weather_collector.py`: Tinggi gelombang laut Selat Lombok & TBBM Manggis via Open-Meteo Marine API.
   - `routing_distance_collector.py`: Jarak & waktu tempuh darat nyata truk tangki via OSRM Driving API.
   - `behavioral_news_collector.py`: Agregat sentimen dan laju publikasi berita krisis via Google News RSS.
   - `calendar_holidays_collector.py`: Kalender libur nasional & siklus upacara adat Bali (Purnama, Tilem, Odalan).
   - `macro_demand_collector.py`: Harga minyak mentah Brent, kurs USD/IDR, dan beban wisatawan Bandara Ngurah Rai.
   - `osm_infrastructure_collector.py`: Topologi koridor jalan protokol arteri (Bypass Ngurah Rai, IB Mantra).

4. **Kajian Korelasi & Analisis Struktural (Target T1–T4)**:
   - **Autokorelasi Spasial Moran's I**: $+0.1684$ ($p = 0.0007$, terbukti secara statistik antrean panjang terklaster di koridor arteri).
   - **Jawaban Numerik 8 Pertanyaan Kritis**: Menjawab lead-time antrean (memimpin kehabisan fisik 90–120 menit), jeda transmisi tanker (36–48 jam), dan peran harga Pertamini sebagai katup pelepas kelangkaan.
   - **Tipologi 3 Klaster Perilaku SPBU**: SPBU Cepat Habis (32.5%), SPBU Penyangga Stabil (45.2%), dan SPBU Korban Limpahan (22.3%).

5. **12 Eksperimen Inovasi Model (Out-of-Time Benchmark)**:
   - **Baseline Hari-0**: Persistence Brier = 0.4566, Markov Day-0 Brier = 0.3180, ROC-AUC = 0.6087.
   - **Gradient Boosting Spatio-Temporal Ensemble**: Brier Score **0.2839** (Gain +10.7% vs Hari-0) dan ROC-AUC **0.7480**.
   - **Hawkes Self-Exciting Process**: Branching ratio $0.417$ (kepanikan subkritis meluruh teratur).
   - **M/M/c Queueing Model**: Estimasi antrean dinamis berbasis kapasitas nosel pompa riil.
   - **Calibrated Conformal Prediction**: Cakupan empiris pita kredibel 80% mencapai **80.0% tepat**.
   - **Deteksi Dini CUSUM**: Mendeteksi anomali kepanikan 3.5 jam sebelum antrean fisik memuncak.

6. **7 Kontrak Data Publikasi Cloudflare Worker & R2**:
   - `meta.json` (<2.5 KB), `summary.json` (<160 KB), `stations.json` (<1.55 MB), `history.json` (<50 KB).
   - **3 Kontrak Baru**: `panic.json` (<150 KB), `correlations.json` (<150 KB), `sources.json` (<50 KB).

7. **Dasbor Interaktif Modular (GitHub Pages)**:
   - Statis di direktori `docs/` (CSS dan JS modular murni).
   - 7 Tab Analisis Interaktif:
     1. `[ 01 // PETA REAL-TIME (LEAFLET) ]` (dengan Inspektor Prediksi 72 Jam per SPBU langsung di bawah peta).
     2. `[ 02 // 14 AREA MAKRO ]` (Analisis CSI & tabel wilayah).
     3. `[ 03 // SIMULASI MONTE CARLO ]` (10.000 jalur fan chart & histogram pemulihan).
     4. `[ 04 // 20 HOTSPOT RENTAN ]` (Peringkat SPBU paling rentan).
     5. `[ 05 // INTELIJEN PANIK & KORELASI ]` (Jawaban 8 pertanyaan kritis & uji stres intervensi kuota).
     6. `[ 06 // SUMBER DATA & EKSPERIMEN ]` (Registri 42 sumber & log 12 eksperimen model).
     7. `[ 07 // PANDUAN WARGA & TIMELINE ]` (Rekomendasi jam aman & kronologi fakta lapangan).

---

## 📁 Struktur Repositori

```text
balifuel-analyst/
├── .github/workflows/
│   ├── pipeline.yml              # Runner data loop permanen (tiap 2 menit, hingga 350 menit)
│   └── pages.yml                 # Deploy otomatis GitHub Pages saat docs/ berubah
├── analysis/
│   └── correlations/             # Matriks korelasi CSV per target (T1, T2, T3, T4)
├── data/
│   ├── balifuel.db               # Database SQLite lokal (retensi rolling 14 hari + VACUUM)
│   ├── external_context.json     # Konteks logistik tanker, kuota terminal, dan timeline krisis
│   ├── clean/                    # Data bersih & fitur rekayasa (features_master.parquet)
│   ├── master/                   # spbu.parquet (1.042 entitas kanonik) & review.csv
│   └── sources/                  # registry.csv (42 sumber) & CATALOG.md
├── docs/                         # Dasbor UI Publik GitHub Pages (Modular)
│   ├── index.html                # Markup HTML tunggal
│   ├── fallback.json             # Data cadangan lokal jika worker offline
│   ├── css/style.css             # Terminal developer-tool aesthetic (Dark & Light Mode)
│   └── js/                       # Modul JavaScript mandiri (config, theme, api, map, charts, app)
├── experiments/
│   └── LOG.md                    # Dokumentasi lengkap protokol 12 eksperimen model
├── output/
│   ├── dashboard.html            # Monolitik lokal mandiri (bisa dibuka file://)
│   ├── laporan.md                # Laporan komprehensif analisis krisis
│   ├── laporan_korelasi.md       # Laporan analisis korelasi & jawaban 8 pertanyaan krisis
│   ├── panic_model_card.md       # Model Card resmi evaluasi ilmiah & etika
│   ├── feature_dictionary.md     # Kamus 32 fitur rekayasa
│   └── spbu_coverage_report.json # Laporan cakupan SPBU resmi Bali
├── src/
│   ├── collectors/               # 6 modul data collector mandiri + collector_manager.py
│   ├── benchmark_day0.py         # Evaluasi out-of-time Baseline Hari-0
│   ├── discover_sources.py       # Engine penelusuran & verifikasi 42 sumber data
│   ├── entity_resolver.py        # Resolusi entitas kanonik & deteksi ambiguitas
│   ├── feature_engineering.py    # Ekstraksi 32 fitur spasial-temporal
│   ├── correlation_analyzer.py   # Analisis korelasi, Moran's I, dan 8 pertanyaan kritis
│   ├── innovative_models.py      # Implementasi 12 model inovasi (Hawkes, M/M/c, Bass, dsb)
│   ├── cleaner.py                # Pembersihan data & imputasi k-NN IDW
│   ├── metrics.py                # Perhitungan CSI pulau dan 14 area
│   ├── markov_model.py           # Mesin rantai Markov 2-status
│   ├── simulation.py             # Simulasi Monte Carlo 10.000 jalur
│   ├── forecast.py               # Peramalan 72 jam per SPBU
│   ├── dashboard_builder.py      # Pembangun dasbor lokal dan aset GitHub Pages
│   └── publish.py                # Pembundel 7 kontrak publikasi ke Cloudflare Edge
├── worker/                       # Cloudflare Worker API & Smart Watchdog (Cron 10m)
└── run_pipeline.py               # Master Pipeline Runner satu-perintah
```

---

## ⚡ Panduan Menjalankan Sistem

### 1. Instalasi Dependensi
```bash
pip install -r requirements.txt
```

### 2. Menjalankan Seluruh Siklus Riset (One-Step Execution)
```bash
# 1. Jalankan penemuan & verifikasi 42 sumber data
python src/discover_sources.py

# 2. Bangun master SPBU kanonik & entity resolution
python src/entity_resolver.py

# 3. Jalankan 6 collector mandiri
python src/collectors/collector_manager.py

# 4. Ekstrak 32 fitur spasial-temporal
python src/feature_engineering.py

# 5. Jalankan analisis korelasi, Moran's I, dan jawaban 8 pertanyaan krisis
python src/correlation_analyzer.py

# 6. Jalankan 12 eksperimen inovasi model out-of-time
python src/innovative_models.py

# 7. Jalankan pipeline master & bangun dashboard
python run_pipeline.py
```

### 3. Membuka Dasbor Analisis
Buka berkas `output/dashboard.html` langsung di peramban Anda (bisa dibuka via protokol `file://` tanpa perlu server lokal).
Atau akses dasbor langsung di GitHub Pages:
**`https://sparkplugx1904.github.io/balifuel-analyst/`**
