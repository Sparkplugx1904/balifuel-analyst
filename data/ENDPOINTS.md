# Dokumentasi Endpoint & Sumber Data Krisis BBM Bali (Oktober 2026)

Dokumen ini mencatat seluruh endpoint API mentah, parameter query, struktur skema respons, header caching, dan temuan teknis dari investigasi mendalam terhadap platform pemantauan bahan bakar di Bali.

---

## 1. Domain 1: `balifuelwatch.vercel.app`

Platform berbasis Next.js/Vercel Serverless dengan caching CDN edge dan database Supabase di backend.

### A. Endpoint `/api/stats`
- **URL**: `https://balifuelwatch.vercel.app/api/stats`
- **Metode**: `GET`
- **Format Respons**: JSON (object)
- **Cache-Control**: `public, max-age=0, s-maxage=30, stale-while-revalidate=300`
- **Frekuensi Pembaruan Server**: ~30-60 detik.
- **Skema Payload**:
  ```json
  {
    "online": 889,
    "today": 25516,
    "total": 485706,
    "reports_total": 49653,
    "reports_today": 2338,
    "places_added": 3389,
    "at": "2026-10-15T19:19:06.348436+00:00"
  }
  ```
- **Keterangan Field**:
  - `online`: Pengguna aktif (realtime presence).
  - `today`: Pengunjung unik hari ini.
  - `total`: Total akumulasi pengunjung sejak insiden dimulai.
  - `reports_total`: Total laporan driver yang masuk (termasuk spam yang belum disaring).
  - `reports_today`: Laporan masuk hari ini.
  - `places_added`: Jumlah titik non-SPBU (Pertamini / Pertashop / penjual eceran) yang didaftarkan pengguna.
  - `at`: Timestamp snapshot UTC ISO-8601. Konversi ke WITA: `UTC + 8 jam`.

---

### B. Endpoint `/api/metrics`
- **URL**: `https://balifuelwatch.vercel.app/api/metrics`
- **Metode**: `GET`
- **Format Respons**: JSON (object)
- **Cache-Control**: `public, max-age=0, s-maxage=60, stale-while-revalidate=600`
- **Skema Payload**:
  - `totals`:
    - `users`: Total pengguna unik (contoh: 485,710)
    - `reports`: Total laporan valid
    - `reporters`: Jumlah pelapor unik (contoh: 29,252)
    - `places`: Total tempat terdaftar (3,389)
    - `reports_spam_hidden`: Jumlah laporan disaring karena spam (contoh: 10,011)
    - `places_spam_hidden`: Penjual liar/spam dihapus (contoh: 9,840)
    - `reports_has_fuel`: Total laporan stok ada (22,624)
    - `reports_empty`: Total laporan stok habis (27,029)
  - `fuel`: Distribusi laporan per jenis BBM (`solar`: 436, `pertalite`: 37,049, `pertamax`: 12,168)
  - `hourly`: Rangkaian time series riwayat per jam:
    ```json
    [
      {
        "t": 1791939600,
        "reports": 5,
        "has_fuel": 2,
        "empty": 3,
        "reporters": 3,
        "new_users": 233,
        "places": 0
      }
    ]
    ```
  - `online`: Riwayat deret waktu pengguna daring.
  - `top_stations`: SPBU dengan aktivitas dan interaksi terbanyak.

---

### C. Endpoint `/api/reports` (High-Resolution Driver Reports)
- **URL**: `https://balifuelwatch.vercel.app/api/reports`
- **Metode**: `GET`
- **Parameter Query**:
  - `w`: Rentang waktu (`day` untuk 24 jam terakhir, `recent` untuk 20 menit terakhir)
  - `f`: Versi format kompresi (`f=2` mengembalikan tuple array padat)
- **Cache-Control**: `public, max-age=0, s-maxage=60, stale-while-revalidate=300` (untuk `w=day`), `s-maxage=10` (untuk `w=recent`).
- **Skema Respons (`f=2`)**:
  ```json
  {
    "v": 2,
    "rows": [
      [44093, 157, 0, 1, 2, 1792063226]
    ]
  }
  ```
- **Pemetaan Indeks Tuple Array**:
  - `rows[0]`: ID Laporan (`int`)
  - `rows[1]`: `station_id` (ID referensi SPBU sesuai master station, `int`)
  - `rows[2]`: Jenis BBM (`int`):
    - `0`: `pertalite`
    - `1`: `pertamax`
    - `2`: `solar`
  - `rows[3]`: Ketersediaan BBM (`int`/`bool`): `1` = Ada (`has_fuel`), `0` = Habis (`empty`)
  - `rows[4]`: Status Antrean (`int`):
    - `0`: Tanpa antre (`no wait`)
    - `1`: Antre singkat / pendek (`short`)
    - `2`: Antre panjang / mengular (`long`)
    - `null`: Tidak dilaporkan
  - `rows[5]`: Waktu laporan dalam detik Epoch Unix (`int`).

---

### D. Endpoint `/api/places` (User-Contributed Points & Pertamini)
- **URL**: `https://balifuelwatch.vercel.app/api/places`
- **Metode**: `GET`
- **Format**: JSON (list of objects)
- **Item Fields**:
  - `id`: Integer (ID user place >= 100,000)
  - `kind`: `"pertamini"` | `"pertashop"` | `"kiosk"`
  - `name`: Nama tempat / keterangan
  - `lat`: Latitude (`float`)
  - `lon`: Longitude (`float`)

---

### E. Static Dataset `/odbl-stations.json`
- **URL**: `https://balifuelwatch.vercel.app/odbl-stations.json`
- **Metode**: `GET`
- **Skema**:
  - `stations`: 181 SPBU resmi Pertamina di seluruh Bali
    - `id`, `name`, `code`, `diesel` (boolean), `lat`, `lon`, `area`, `reg` (kabupaten), `h24` (24 jam)
  - `small_sellers`: 114 titik penjual eceran terverifikasi OSM.

---

### F. Backend Supabase & RPC
- **Supabase URL**: `https://rmfdvcfbaljwaocwgqov.supabase.co`
- **Public Anon Key**: Terkonfirmasi di client bundle (`sb_publishable_...`).
- **RPC**: `/rest/v1/rpc/fuel_ping` (pengukuran kehadiran/presence user).

---

## 2. Domain 2: `bensinbali.com`

Aplikasi statis yang menginjeksi dataset lengkap real-time langsung ke dalam DOM HTML melalui tag `<script type="application/json" id="fuel-data">`.

### A. Embedded Master Payload (`id="fuel-data"`)
- **URL**: `https://bensinbali.com/`
- **Ukuran**: ~1.53 MB JSON mentah
- **Top-level Keys**:
  - `stations`: 876 stasiun (212 SPBU resmi Pertamina + 664 Pertamini)
  - `people`: 5,258 (pengunjung aktif saat snapshot)
  - `sharers`: 188
  - `queuing`: Metrik pengguna sedang mengantre
  - `queueStats`: Statistik waktu antrean per wilayah
  - `reports`: Ringkasan metrik laporan
  - `places`: Total titik penjual
- **Skema Detail Setiap Station**:
  ```json
  {
    "id": 1487,
    "kind": "pertamini", // atau "spbu"
    "added": false,
    "name": "SPBU...",
    "brand": "pertamini" | "pertamina",
    "address": "Jl. ...",
    "area": "Gianyar",
    "lat": -8.543285,
    "lng": 115.317629,
    "placeId": "ChIJ...",
    "code": "54.805...",
    "lookers": 72,
    "queue": null | 0 | 1 | 2,
    "reports": [
      {
        "hasFuel": true,
        "ageMin": 514.3,
        "from": "pump" | "far",
        "fuels": ["pertalite"],
        "prices": {"pertalite": 12000},
        "stock": 2,
        "trust": 1.5
      }
    ]
  }
  ```
- **Karakteristik Kunci**:
  - Menyediakan data harga eceran (`prices`), memverifikasi fenomena Pertamini menjual Pertalite di atas HET resmi (Rp 12.000 hingga Rp 40.000/liter).
  - Menyediakan nilai reliabilitas pelapor (`trust`, `from: "pump"` vs `"far"`).
  - Menyediakan umur laporan dalam menit presisi (`ageMin`).

### B. Halaman Area Spesifik
- 14 Area resmi Bali:
  `canggu`, `seminyak-kuta`, `bukit`, `sanur`, `denpasar`, `mengwi`, `ubud`, `gianyar`, `tabanan`, `klungkung`, `karangasem`, `bangli`, `lovina`, `jembrana`.
- Masing-masing memiliki snapshot lokal yang cocok dengan agregasi root.

---

## 3. Parameter Model Logistik & Fisik Terkonfirmasi (Ground Truth Lapangan)

Berdasarkan data operasional Pertamina Patra Niaga dan model logistik Bali:
- **Konsumsi Pertalite Normal**: 2.000 – 2.200 KL/hari (pulau Bali).
- **Konsumsi Selama Krisis (Panic Buying)**: 2.500 – 2.700 KL/hari (+12% hingga +25%).
- **Kapasitas Distribusi Mobil Tangki**: Maksimal 2.700 KL/hari.
- **Rata-rata Kapasitas Tangki SPBU**: 24 KL Pertalite / SPBU.
- **Terminal Suplai Utama**:
  1. TBBM Sanggaran (Denpasar): `-8.7262, 115.2120`
  2. TBBM Manggis (Karangasem): `-8.5115, 115.5300`
- **Jadwal Tanker 26.200 KL**:
  - Kapal 1: 12 Oktober 2026 10:00 WITA (TBBM Sanggaran) ~6.000 KL
  - Kapal 2: 14 Oktober 2026 10:00 WITA (TBBM Manggis) ~6.000 KL
  - Kapal 3: 16 Oktober 2026 10:00 WITA (TBBM Sanggaran) ~6.000 KL
  - Alokasi lanjutan 14-17 Oktober: 57,9 Juta Liter.

---

## 4. Kebijakan Polling & Rate Limit
- Polling endpoint `/api/stats` dan `/api/reports?w=recent&f=2` dilakukan tiap 5-15 menit (tidak melebihi s-maxage server).
- Menyertakan header `User-Agent: BaliFuelCrisisResearch/1.0` yang jujur dan sopan.
- Memanfaatkan caching `If-None-Match` (ETag) untuk mencegah transmisi payload berulang jika tidak ada perubahan data.
