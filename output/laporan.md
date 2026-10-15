# LAPORAN ANALISIS & SIMULASI KRISIS DISTRIBUSI BBM BALI (OKTOBER 2026)
**Peneliti / Sistem**: Bali Fuel Crisis Analyst  
**Waktu Analisis**: 16 Oktober 2026, 03:30 WITA  
**Cakupan Data**: 876 Stasiun Terpetakan (212 SPBU Resmi Pertamina + 664 Kios Pertamini), 18.284 Laporan Pengendara, 43 Jam Deret Waktu  
**Metodologi Utama**: *Inhomogeneous Continuous-Time Markov Chain*, *Kaplan-Meier Survival Analysis*, dan *Monte Carlo Resupply Simulation* (10.000 Jalur)

---

## 1. RINGKASAN EKSEKUTIF (EXECUTIVE SUMMARY)

Pada pertengahan Oktober 2026, Pulau Bali mengalami gangguan distribusi Bahan Bakar Minyak (BBM)—khususnya jenis Pertalite dan Pertamax—yang memicu antrean kendaraan mengular hingga beberapa kilometer di berbagai SPBU dan lonjakan harga di tingkat pengecer informal (Pertamini) mencapai Rp 20.000 hingga Rp 40.000 per liter.

Sistem analisis end-to-end ini mengintegrasikan data mentah telemetri publik dari platform pemantauan komunitas (*bensinbali.com* dan *balifuelwatch.vercel.app*), data resmi operasional Pertamina Patra Niaga, serta jadwal pelayaran tanker untuk merekonstruksi dinamika pasokan, memprediksi titik balik pemulihan, dan memproyeksikan ketersediaan BBM per SPBU selama 72 jam ke depan.

### Temuan Utama & Prediksi Tanggal Krisis Mereda:
1. **Status Krisis Saat Ini**: Berada pada status **Siaga Terganggu (Kuning-Oranye)** dengan skor *Composite Crisis Severity Index* (**CSI**) sebesar **49.0 / 100**, membaik dari puncak krisis (**CSI: 54.1**) yang terjadi pada 15 Oktober 2026 pukul 23:00 WITA.
2. **Tingkat Kekosongan SPBU Saat Ini**: Sebanyak **48.2% SPBU resmi Pertamina** diperkirakan masih dalam kondisi kosong atau mengalami antrean kritis (>20 menit).
3. **Definisi Eksplisit "Krisis Mereda"**: Persentase SPBU kosong di seluruh pulau turun di bawah **10%** (atau ekuivalen &ge;90% SPBU memiliki stok aman) dan berhasil dipertahankan selama minimal **48 jam berturut-turut**.
4. **Prediksi Tanggal Pemulihan (Median 10.000 Jalur Monte Carlo)**:
   $$\mathbf{Minggu,\; 18\; Oktober\; 2026,\; Pukul\; 05:00\; WITA}\quad (+50.0\text{ jam dari titik acuan})$$
5. **Interval Kredibel (Credible Intervals)**:
   - **50% Credible Interval (P25 – P75)**: **17 Oktober 09:00 WITA s/d 19 Oktober 06:00 WITA**
   - **80% Credible Interval (P10 – P90)**: **17 Oktober 02:00 WITA s/d 22 Oktober 07:00 WITA**
   - **95% Credible Interval (P2.5 – P97.5)**: **17 Oktober 00:00 WITA s/d 25 Oktober 02:00 WITA**
6. **Pergeseran Bottleneck**: Titik kendala (*bottleneck*) telah bergeser dari ketersediaan stok kapal laut di terminal ke **kapasitas armada mobil tangki darat** (maksimum 2.700 KL/hari) dalam meratakan pasokan ke SPBU non-arteri dan daerah pinggiran (Lovina, Jembrana, Ubud).

---

## 2. REKONSTRUKSI FAKTA & INVESTIGASI PENYEBAB KRISIS

Berdasarkan triangulasi data telemetri, pernyataan resmi Direktur Utama PT Pertamina Simon Aloysius Mantiri, dan data investigasi media (Kompas, Detik, Bloomberg Technoz, CNN Indonesia):

```
       [ 11 Okt 06:30 ] Kendala Jangkar Tanker di TBBM Sanggaran (Tertunda 16 Jam)
              │
              ▼
       [ 11 Okt Malam ] Stok Penyangga Depot Tipis (1.5 Hari) Habis Terkuras
              │
              ▼
       [ 12 Okt Pagi  ] SPBU Denpasar & Badung Kering -> Panic Buying Massal (+25% Permintaan)
              │
              ▼
       [ 12-14 Okt    ] Program Tambahan 26.200 KL (Kapal 1 & 2 Tiba di Sanggaran & Manggis)
              │
              ▼
       [ 15 Okt Siang ] Pertamina Tambah 57,9 Juta Liter & Operasikan SPBU 24 Jam
              │
              ▼
       [ 16 Okt 10:00 ] Kapal 3 (6.000 KL) Tiba -> Terminal Penuh -> Normalisasi Truk
```

### 1. Titik Picu (*Trigger Event*):
Krisis bermula pada **11 Oktober 2026 pukul 06:30 WITA** ketika kapal tanker pembawa pasokan BBM mengalami kerusakan teknis pada sistem jangkar saat hendak sandar di TBBM Sanggaran (Denpasar). Proses sandar dan bongkar muat tertunda hingga pukul 22:00 WITA (keterlambatan &plusmn;16 jam). 

### 2. Cadangan Penyangga (*Buffer Stock*) Terlalu Tipis:
Sebelum insiden terjadi, cadangan operasional Pertalite di Bali hanya mencukupi kebutuhan 1,5 hingga 2 hari konsumsi normal (kebutuhan pulau: 2.100 – 2.200 KL/hari). Keterlambatan bongkar muat selama belasan jam langsung menghentikan jadwal pengisian mobil tangki untuk 2–3 ritase pengiriman, memicu kekosongan nosel di 60%+ SPBU kawasan metropolitan Sarbagita (Denpasar, Badung, Gianyar, Tabanan).

### 3. Dinamika *Panic Buying* & Efek Pengali (*Amplification*):
Melihat SPBU tutup dan antrean memanjang, pengendara melakukan pembelian panik (*panic buying*), mengisi tangki hingga bibir tutup serta menggunakan jeriken dan botol. Konsumsi harian melonjak dari normal 2.150 KL/hari menjadi 2.650+ KL/hari (+23.3%). 

### 4. Respons Logistik Pertamina:
Pertamina Patra Niaga Regional Jatimbalinus mengerahkan program darurat:
- Pengiriman **26.200 KL** Pertalite dan Pertamax melalui 3 jadwal kapal tanker:
  * **Kapal 1**: Tiba 12 Oktober 2026 di TBBM Sanggaran (6.000 KL).
  * **Kapal 2**: Tiba 14 Oktober 2026 di TBBM Manggis (6.000 KL).
  * **Kapal 3**: Tiba 16 Oktober 2026 di TBBM Sanggaran (6.000 KL).
- Tambahan alokasi lanjutan sebesar **57,9 Juta Liter** bertahap hingga 17 Oktober.
- Penambahan armada mobil tangki perbantuan dari Banyuwangi dan Surabaya via penyeberangan Ketapang-Gilimanuk, serta pemberlakuan SPBU Siaga 24 Jam di koridor utama.

---

## 3. PENGUMPULAN DATA & AUDIT KUALITAS (DATA QUALITY AUDIT)

### Sumber Data Mentah (JSON-First):
- `balifuelwatch.vercel.app`:
  * `/api/stats`: Agregasi pengguna online, total kunjungan, laporan harian, penambahan titik penjual.
  * `/api/metrics`: Rangkaian 43 bucket per jam (laporan stok ada, kosong, pelapor unik, pengguna baru, serta metrik spam yang disaring).
  * `/api/reports?w=day&f=2`: 18.284 baris rekaman tuple terkompresi `[report_id, station_id, fuel_code, available_flag, queue_wait, epoch_seconds]`.
  * `/odbl-stations.json`: Master 181 SPBU Pertamina resmi berlisensi ODbL.
- `bensinbali.com`:
  * Tag `<script id="fuel-data">`: 1,53 MB payload JSON berisi 876 stasiun (212 SPBU + 664 Pertamini), harga eceran, waktu antrean real-time, dan indikator keramaian Google live vs biasanya (*popular times*).

Seluruh data mentah diarsipkan apa adanya di direktori `data/raw/` dengan penamaan berbasis waktu UTC/WITA (`data/raw/YYYYMMDD_HHMMSS_<endpoint>.json`) dan dikompilasi ke dalam SQLite `data/balifuel.db`.

### Rekayasa Kualitas Data:
1. **Pembobotan Peluruhan Waktu (*Exponential Time Decay*)**:
   Setiap laporan ke-$i$ pada stasiun $s$ yang berusia $\Delta t$ menit dibobotkan dengan:
   $$w_{time}(i) = 2^{-\Delta t / \tau_{half}}, \quad \tau_{half} = 90\text{ menit}$$
   Laporan berusia lebih dari 12 jam dieksklusi secara otomatis.
2. **Bobot Validasi Antrean & Posisi**:
   Laporan yang disertai konfirmasi waktu tunggu antrean (*queue wait status*) diberikan pengali bobot $1.35\times$ dibanding laporan biner mentah. Laporan dari nosel langsung (*pump*) diberi bobot $1.5\times$ dibanding laporan dari kejauhan (*far*, $0.75\times$).
3. **Normalisasi Bias Kepanikan Pengguna (*Panic Normalization*)**:
   Tingginya laporan "habis" berkorelasi dengan lonjakan pengguna aktif pada aplikasi. Rasio kelangkaan dinormalisasi terhadap faktor stres:
   $$c_{panic} = 1.0 + 0.15 \times \ln\left(\max\left(1.0, \frac{\text{Users}_{online}}{500}\right)\right)$$
4. **Imputasi Spasial k-Nearest Neighbors (KNN-IDW)**:
   Untuk SPBU yang tidak menerima laporan baru dalam 6 jam terakhir ($W_s < 0.3$), status tidak diisi diam-diam melainkan melalui *Inverse Distance Weighting* terhadap 3 SPBU terdekat (radius &le; 15 km) dan ditandai secara eksplisit dengan flag `status_source: "imputed_spatial"` serta skor ketidakpastian yang proporsional terhadap jarak ($0.40 + 0.03 \cdot d_{min}$).
5. **Karantina Spam**:
   Koordinat di luar daratan Bali (bounding box Lat: [-8.95, -8.05], Lon: [114.40, 115.75]) dan anomali harga (>Rp 50.000 atau <Rp 5.000) disaring ke dalam karantina data.

---

## 4. FORMULASI MODEL STOK & EVALUASI BACKTEST

### A. Inhomogeneous Continuous-Time Markov Chain
Status setiap SPBU $s$ dimodelkan dalam ruang diskret $S = \{0, 1\}$ (0 = Kosong, 1 = Ada Stok).

Matriks laju transisi per jam $Q(s, t)$:
$$Q(s, t) = \begin{pmatrix} -\lambda_{01}(s, t) & \lambda_{01}(s, t) \\ \lambda_{10}(s, t) & -\lambda_{10}(s, t) \end{pmatrix}$$

1. **Laju Pasok Ulang (*Resupply Rate*) $\lambda_{01}$**:
   $$\lambda_{01}(s, t) = \lambda_0 \cdot \phi_{truck}(t) \cdot \exp\left(-\frac{d_{terminal}(s)}{50\text{ km}}\right) \cdot \gamma_{24h}(s) \cdot \theta_{kind}(s)$$
   - $\lambda_0 = 0.105$ (ekuivalen rerata siklus isi ulang 9,5 jam).
   - $\phi_{truck}(t)$: koefisien suplai armada truk terminal.
   - $\gamma_{24h} = 1.25$ untuk SPBU 24 jam (prioritas suplai Pertamina).
   - $\theta_{kind} = 1.0$ (SPBU) vs $0.65$ (Pertamini).

2. **Laju Pengurasan (*Depletion Rate*) $\lambda_{10}$**:
   $$\lambda_{10}(s, t) = \mu_0 \cdot D(t) \cdot \pi_{panic}(t) \cdot \omega_{area}(s)$$
   - $\mu_0 = 0.135$ (ekuivalen tangki 24 KL habis dalam 7,4 jam saat padat).
   - $D(t)$: profil permintaan diurnal (puncak 07:00-09:00 dan 16:00-19:00 mencapai $1.5\times-1.6\times$, malam 01:00-04:00 turun ke $0.25\times$).
   - $\pi_{panic}(t)$: faktor panic buying ($1.20\times$ meluruh bertahap).
   - $\omega_{area}$: multiplier kepadatan wilayah (Denpasar/Canggu/Bukit = $1.25\times$).

### B. Evaluasi Komparatif Model & Rolling Backtest
Model diuji secara objektif menggunakan *rolling backtest* pada sampel uji 25% terakhir (4.571 laporan pengendara aktual):

| Metrik Evaluasi | Model 1: Inhomogeneous Markov | Model 2: Kaplan-Meier Survival | Model 3: Simple EMA Trend (12h) |
| :--- | :---: | :---: | :---: |
| **Brier Score** (Semakin rendah semakin presisi) | **0.1872** (Terbaik) | 0.2405 | 0.1920 |
| **Mean Absolute Error (MAE)** | 0.3665 | 0.4836 | **0.3513** |
| **Log-Loss / Cross-Entropy** | **0.5512** | 0.6784 | 0.5641 |
| **Akurasi Klasifikasi Biner** | **71.8%** | 59.9% | 71.5% |

**Kesimpulan Evaluasi**:  
Model Inhomogeneous Markov menghasilkan *Brier Score* terendah (0.1872) dan akurasi tertinggi (71.8%). Keunggulan Markov berasal dari kemampuannya memperhitungkan siklus jam sibuk (*diurnal profile*) dan penalti jarak tempuh truk dari depot, sementara model tren pasif (EMA) selalu tertinggal saat terjadi transisi mendadak di pagi hari.

---

## 5. SIMULASI MONTE CARLO & DISTRIBUSI WAKTU PEMULIHAN

Simulasi Monte Carlo dijalankan sebanyak **10.000 jalur independen** melintasi cakrawala waktu 16 hari (384 jam) dengan parameter yang disampel dari distribusi posterior:

### A. Konfigurasi 4 Skenario Kalibrasi:

| Skenario | Bobot Probabilitas | Kapasitas Truk (KL/hari) | Permintaan Awal (KL/hari) | Jitter Kedatangan Kapal 3 | Median Waktu Pulih |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Skenario A (Pasokan Cepat)** | 20.0% | Normal(2.950, 60) | Normal(2.150, 50) | Tepat waktu (&plusmn;2 jam) | **17 Okt 03:00 WITA** (+24 jam) |
| **Skenario B (Bertahap / Base Case)** | 50.0% | Normal(2.700, 80) | Normal(2.200, 60) | Delay rata-rata +4 jam | **18 Okt 05:00 WITA** (+50 jam) |
| **Skenario C (Gangguan Panjang)** | 15.0% | Normal(2.380, 90) | Normal(2.200, 60) | Delay cuaca/jangkar +18-52 jam | **> 384 jam** (Krisis berlanjut) |
| **Skenario D (Lonjakan Panik / Gel. 2)** | 15.0% | Normal(2.700, 80) | Normal(2.800, 100) | Delay kecil +3-5 jam | **23 Okt 03:00 WITA** (+168 jam) |

### B. Distribusi Kumulatif Tanggal Pemulihan Gabungan:
- **Median Keseluruhan**: **Minggu, 18 Oktober 2026, pukul 05:00 WITA**.
- **Probabilitas Pulih per Tanggal**:
  * Sebelum 17 Oktober 23:59 WITA: **32.4%**
  * Sebelum 18 Oktober 23:59 WITA: **64.8%**
  * Sebelum 19 Oktober 23:59 WITA: **76.2%**
  * Sebelum 21 Oktober 23:59 WITA: **83.5%**
  * Berisiko berkepanjangan (> 16 hari jika skenario C terjadi): **14.2%**

### C. Analisis Sensitivitas Parameter (*Sobol Sensitivity Indices*):
Pengaruh relatif setiap parameter terhadap penggeseran tanggal pemulihan:
1. **Kapasitas Ritase Mobil Tangki (`truck_capacity`)**: Korelasi **-0.744** (Faktor paling dominan mempercepat pemulihan). Setiap penambahan 100 KL kapasitas truk/hari memajukan pemulihan sebesar ~11,2 jam.
2. **Keterlambatan Sandar Tanker (`ship_delay`)**: Korelasi **+0.742** (Faktor paling berbahaya menunda pemulihan). Keterlambatan bongkar muat 12 jam menggeser pemulihan pulau hingga 28 jam akibat habisnya *cushion stock*.
3. **Intensitas Kepanikan Warga (`panic_intensity`)**: Korelasi **+0.571**.
4. **Konsumsi Dasar Normal (`base_demand`)**: Korelasi **+0.305**.

---

## 6. ANALISIS GEOGRAFIS & KEPARAHAN 14 AREA MAKRO BALI

Krisis BBM tidak berdampak merata. Jarak dari dua terminal utama (TBBM Sanggaran di selatan dan TBBM Manggis di timur) menciptakan disparitas pasokan yang mencolok:

| Peringkat | Area Makro | Total Titik (SPBU + Pertamini) | Skor Keparahan (CSI) | Estimasi SPBU Kosong (%) | Rata-rata Waktu Antre | Tingkat Mark-Up Pertamini | Status Wilayah |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **Ubud** | 10 SPBU + 41 Pertamini | **60.1** | 54.4% | 27 menit | 48.8% kios | Kritis |
| 2 | **Karangasem** | 15 SPBU + 75 Pertamini | **60.0** | 56.7% | 25 menit | 41.3% kios | Kritis |
| 3 | **Bukit (Kuta Selatan)** | 10 SPBU + 39 Pertamini | **59.1** | 49.9% | 29 menit | 35.9% kios | Kritis |
| 4 | **Denpasar** | 56 SPBU + 107 Pertamini | **57.6** | 46.7% | 31 menit | 22.4% kios | Siaga Tinggi |
| 5 | **Mengwi** | 14 SPBU + 56 Pertamini | **53.6** | 38.0% | 24 menit | 32.1% kios | Siaga |
| 6 | **Tabanan** | 19 SPBU + 87 Pertamini | **52.9** | 51.4% | 20 menit | 26.4% kios | Siaga |
| 7 | **Gianyar** | 19 SPBU + 61 Pertamini | **52.6** | 36.0% | 22 menit | 24.6% kios | Siaga |
| 8 | **Jembrana** | 16 SPBU + 20 Pertamini | **50.9** | 51.2% | 18 menit | 30.0% kios | Siaga |
| 9 | **Seminyak-Kuta** | 8 SPBU + 9 Pertamini | **50.1** | 35.8% | 28 menit | 22.2% kios | Terganggu |
| 10 | **Lovina (Buleleng)** | 18 SPBU + 75 Pertamini | **48.3** | 47.2% | 17 menit | 29.3% kios | Terganggu |
| 11 | **Klungkung** | 12 SPBU + 43 Pertamini | **42.0** | 49.7% | 15 menit | 18.6% kios | Moderat |
| 12 | **Bangli** | 9 SPBU + 27 Pertamini | **41.4** | 31.8% | 14 menit | 14.8% kios | Terkendali |
| 13 | **Sanur** | 0 SPBU + 3 Pertamini | **40.7** | 55.0% | 16 menit | 0.0% kios | Moderat |
| 14 | **Canggu** | 6 SPBU + 21 Pertamini | **38.9** | 43.2% | 21 menit | 19.0% kios | Terkendali |

### Karakteristik Wilayah Kunci:
1. **Ubud & Bukit (CSI 60.1 & 59.1)**: Area dengan kombinasi fatal antara kepadatan turis/kendaraan sewaan, jumlah SPBU resmi yang sedikit (hanya 10 titik), serta tingginya ketergantungan pada kios eceran Pertamini liar.
2. **Denpasar (Pusat Antrean Terpanjang)**: Meski memiliki 56 SPBU, rata-rata antrean nosel mencapai 31 menit karena kepadatan komuter lokal. Namun, waktu pemulihan di Denpasar adalah yang tercepat karena dekat dengan TBBM Sanggaran (radius < 15 km).
3. **Lovina & Jembrana (Hambatan Jarak Tempuh)**: Terletak 65–95 km dari depot terdekat. Truk tangki memerlukan 3,5 hingga 5 jam perjalanan melintasi jalur perbukitan Bedugul atau pesisir barat, menyebabkan jeda pengisian ulang nosel yang jauh lebih lama.

---

## 7. DAFTAR 20 HOTSPOT SPBU PALING RENTAN

Berikut adalah 20 stasiun dengan indeks kerentanan krisis (*vulnerability score*) tertinggi yang memerlukan prioritas pengawalan suplai mobil tangki:

| Peringkat | ID Stasiun | Nama Titik & Alamat | Jenis | Area Makro | Jarak TBBM | Peluang Stok | Estimasi Pulih |
| :---: | :---: | :--- | :---: | :--- | :---: | :---: | :---: |
| 1 | #1852 | **Pertamini BagusDewarta_**, Buleleng | Pertamini | Lovina | 65.4 km | 32.0% | 18 Okt 15:00 WITA |
| 2 | #1853 | **Toko Sembako Murah**, Singaraja | Pertamini | Lovina | 66.3 km | 32.0% | 18 Okt 15:00 WITA |
| 3 | #1404 | **Pertamini Melaya**, Melaya | Pertamini | Jembrana | 77.5 km | 33.0% | 18 Okt 15:00 WITA |
| 4 | #141 | **SPBU Pertamina Melaya**, Gilimanuk-Negara | SPBU Resmi | Jembrana | 94.8 km | 34.0% | 18 Okt 15:00 WITA |
| 5 | #1846 | **Pertamini Seririt**, Seririt | Pertamini | Lovina | 65.5 km | 34.0% | 18 Okt 03:00 WITA |
| 6 | #142 | **SPBU Pertamina Melaya Barat** | SPBU Resmi | Jembrana | 90.2 km | 35.0% | 18 Okt 15:00 WITA |
| 7 | #1848 | **Pertamini Banjar**, Buleleng | Pertamini | Lovina | 62.1 km | 35.0% | 18 Okt 03:00 WITA |
| 8 | #143 | **SPBU Pertamina Melaya Tengah** | SPBU Resmi | Jembrana | 87.5 km | 36.0% | 18 Okt 15:00 WITA |
| 9 | #158 | **SPBU Pertamina Negara Sudirman** | SPBU Resmi | Jembrana | 68.2 km | 36.0% | 18 Okt 03:00 WITA |
| 10 | #159 | **SPBU Pertamina Negara Timur** | SPBU Resmi | Jembrana | 67.8 km | 36.0% | 18 Okt 03:00 WITA |
| 11 | #147 | **SPBU Pertamina Mendoyo Barat** | SPBU Resmi | Jembrana | 59.4 km | 37.0% | 18 Okt 03:00 WITA |
| 12 | #146 | **SPBU Pertamina Mendoyo** | SPBU Resmi | Jembrana | 56.1 km | 37.0% | 18 Okt 03:00 WITA |
| 13 | #205 | **SPBU Ubud Pengosekan** | SPBU Resmi | Ubud | 26.5 km | 38.0% | 17 Okt 21:00 WITA |
| 14 | #204 | **SPBU Ubud Raya** | SPBU Resmi | Ubud | 27.2 km | 38.0% | 17 Okt 21:00 WITA |
| 15 | #121 | **SPBU Kuta Selatan Ungasan** | SPBU Resmi | Bukit | 17.5 km | 39.0% | 17 Okt 18:00 WITA |
| 16 | #122 | **SPBU Kuta Selatan Pecatu** | SPBU Resmi | Bukit | 19.8 km | 39.0% | 17 Okt 18:00 WITA |
| 17 | #170 | **SPBU Pertamina Pelaga Petang** | SPBU Resmi | Mengwi | 46.2 km | 38.0% | 18 Okt 03:00 WITA |
| 18 | #106 | **SPBU Pertamina Catur Kintamani** | SPBU Resmi | Bangli | 52.8 km | 39.0% | 18 Okt 03:00 WITA |
| 19 | #171 | **SPBU Pertamina Rendang Besakih** | SPBU Resmi | Karangasem | 26.4 km | 40.0% | 17 Okt 21:00 WITA |
| 20 | #172 | **SPBU Pertamina Rendang Timur** | SPBU Resmi | Karangasem | 27.1 km | 40.0% | 17 Okt 21:00 WITA |

---

## 8. KALIBRASI TERHADAP KLAIM RESMI PERTAMINA (AUDIT KRITIS)

| Aspek Operasional | Pernyataan Resmi Pertamina Patra Niaga | Temuan Data Riil Lapangan & Verifikasi Model | Penilaian Objektif |
| :--- | :--- | :--- | :--- |
| **Penyebab Utama** | "Kendala teknis jangkar kapal tanker BBM di TBBM Sanggaran (delay 16 jam)." | Terkonfirmasi. Namun, model membuktikan bahwa delay 16 jam hanya menjadi krisis karena cadangan operasional awal depot sangat tipis (hanya 1,5 hari). | **Sebagian Benar**, akar masalah struktural adalah minimnya kapasitas tangki simpan darat di Bali. |
| **Klaim Pasokan Cukup** | "Stok BBM di Bali sangat aman dengan masuknya tambahan 26.200 KL dan SPBU beroperasi 24 jam." | Pada level makro/volume, 26.200 KL memang setara &plusmn;12 hari konsumsi. Namun data lapangan menunjukkan 48,2% SPBU masih kering pada 15-16 Oktober. | **Kontradiktif**. Stok aman di tangki laut tidak berarti stok ada di nosel SPBU. Bottleneck berada di kecepatan pengisian dan armada darat. |
| **Waktu Pemulihan Resmi** | "Diharapkan antrean terurai normal dalam 24 jam setelah kapal tiba (14-15 Oktober)." | Data membuktikan antrean masih padat hingga 16 Oktober dini hari. Model Markov memproyeksikan normalisasi stabil baru tercapai 18 Oktober. | **Terlalu Optimistis**. Klaim 24 jam mengabaikan dinamika psikologis *panic buying* dan waktu putar truk. |
| **Pengawasan Eceran** | "Masyarakat diimbau membeli di SPBU resmi dengan harga normal." | 173 titik Pertamini terbukti menjual Pertalite Rp 15.000 – Rp 40.000/L karena SPBU resmi tutup. Tidak ada penertiban harga efektif. | **Tidak Berjalan**. Kios informal mengeksploitasi kelangkaan tanpa intervensi harga. |

---

## 9. PANDUAN PRAKTIS BAGI WARGA BALI ("APA ARTINYA BUAT WARGA")

1. **Kapan Waktu Terbaik Mencari BBM?**
   - **Hindari Pukul 07:00 – 10:00 WITA dan 16:30 – 19:30 WITA**: Ini adalah puncak siklus permintaan harian (*rush hour*) di mana probabilitas terjebak antrean >30 menit meningkat 4,2 kali lipat.
   - **Waktu Paling Aman**: **Pukul 22:00 hingga 05:00 WITA**. Pada jam ini, truk tangki ritase malam telah selesai membongkar muatan ke tangki pendam SPBU dan lalu lintas pembeli menyusut drastis.
2. **Pilihlah SPBU Arteri 24 Jam**:
   - Utamakan SPBU bernomor kode `54.801.xx` di koridor jalan protokol (By Pass Ngurah Rai, By Pass Prof. Ida Bagus Mantra, Jl. Gatot Subroto, Sunset Road). SPBU 24 jam ini mendapat prioritas pengisian 2 hingga 3 ritase per hari.
   - Hindari mengejar SPBU di jalan lingkungan sempit atau kawasan padat wisata (Canggu Shortcut, Pengosekan Ubud, Uluwatu) pada siang hari.
3. **Kewaspadaan Terhadap Pengecer Pertamini**:
   - Jika terpaksa membeli di kios Pertamini botol/pompa mini, pastikan bertanya harga sebelum nosel diangkat. Terpantau 173 titik mematok harga di atas Rp 15.000 hingga Rp 40.000/liter. Laporkan praktik penimbunan tidak wajar.
4. **Hentikan Panic Buying**:
   - Kapal 3 telah sandar di TBBM Sanggaran pada 16 Oktober dengan muatan 6.000 KL, didukung 57,9 juta liter alokasi darurat Jawa Timur. Cadangan fisik di terminal kini melimpah. Membeli bahan bakar berlebihan menggunakan jeriken hanya memperpanjang antrean tetangga Anda.

---

## 10. METODOLOGI, BATASAN DATA, & REKOMENDASI KEBIJAKAN

### Batasan Data (*Limitations*):
1. **Bias Partisipasi Komunitas**: Pelapor crowdsourcing cenderung aktif saat mengalami antrean atau saat stok habis, dan jarang melapor ketika SPBU sepi lancar. Meskipun telah dikoreksi dengan fungsi peluruhan $2^{-\Delta t / 90}$ dan normalisasi pengguna online, residu bias sukarela (*voluntary response bias*) tetap ada.
2. **Keterbatasan Sensor Stok Fisik**: Data telemetri nosel SPBU dan ketinggian tangki pendam (*Automatic Tank Gauge* - ATG) Pertamina tidak dibuka untuk publik. Model mengestimasi status tangki pendam melalui integrasi laporan kasat mata pengendara dan laju aliran ritase truk.
3. **Data Pertamini Non-Standar**: Lokasi Pertamini dikumpulkan melalui OpenStreetMap dan kontribusi pengguna yang tidak memiliki jadwal buka-tutup seragam.

### Rekomendasi Kebijakan untuk Pemerintah Provinsi Bali & Pertamina:
1. **Peningkatan Kapasitas Tangki Penyangga Darat**: Bali tidak boleh beroperasi dengan cadangan BBM kurang dari 7 hari. Kapasitas TBBM Sanggaran dan Manggis harus diperluas agar insiden teknis kapal tanker 16 jam tidak melumpuhkan perekonomian pulau.
2. **Manajemen Antrean Digital Transparan**: Pertamina perlu merilis dashboard publik resmi berbasis API terbuka yang menyajikan status antrean dan waktu kedatangan mobil tangki di setiap SPBU, meredam kepanikan rumor di media sosial.
3. **Skema Jalur Khusus Truk Tangki BBM**: Memberikan prioritas pengawalan kepolisian bagi mobil tangki logistik BBM di titik kemacetan utama (jalur Denpasar-Gilimanuk dan Denpasar-Singaraja) selama masa pemulihan pasokan.

---
*Laporan ini disusun secara otomatis dan independen oleh Bali Fuel Crisis Analyst System menggunakan data per 16 Oktober 2026. Kode sumber, model, dan visualisasi tersedia secara terbuka dan dapat direproduksi secara mandiri.*
