# Audit Ketentuan & Akses Legal Platform (data/text/platforms.md)
*BaliFuel Analyst — Legal, Ethical & Privacy Compliance Ledger*
**Tanggal Audit Terakhir**: 2026-10-16 | **Status**: Aktif & Dipatuhi

Sistem mematuhi prinsip etika data: tidak ada scraping ilegal, tidak ada penembusan login wall/CAPTCHA, privasi warga dilindungi 100% (tanpa PII).

---

## 1. Matriks Kepatuhan Legal Lintas Platform

| Platform | Jalur Akses Sah | Status Akses Proyek | Alasan & Batasan Legal | Tanggal Cek Bukti |
| :--- | :--- | :---: | :--- | :---: |
| **Portal Berita & Media Lokal** | RSS Feed Resmi & HTTP GET Terbuka | **AKTIF (API/RSS)** | Sesuai robots.txt. Tidak mengambil halaman berbayar (*paywall*). Rate limit 1 req / 3 detik. User-Agent jujur. | 2026-10-16 |
| **YouTube** | YouTube Data API v3 Resmi | **AKTIF (API)** | Mengambil komentar publik pada liputan berita media terverifikasi (Antara, Detik Bali, Kompas TV). Batas kuota 10.000 unit/hari. | 2026-10-16 |
| **Reddit** | Reddit Data API Resmi | **TERBATAS (API)** | Subreddit publik r/bali & r/indonesia. Sesuai kebijakan Reddit Developer Terms 2024. Read-only agregat. | 2026-10-16 |
| **Google News RSS & Trends** | RSS Endpoint Publik & Trends Agregat | **AKTIF** | Pengambilan agregat volume berita krisis dan kata kunci panik per jam. Sesuai ketentuan Google. | 2026-10-16 |
| **Google Maps Reviews SPBU** | Places API Resmi | **TERBATAS (API)** | Hanya ulasan terbaru SPBU resmi melalui Google Cloud Places API resmi. Dilarang scraping antarmuka web Maps. | 2026-10-16 |
| **Instagram** | Kotak Masuk Manual (*Manual Inbox*) | **MANUAL INBOX (SAH)** | **DILARANG scraping otomatis** (melanggar Meta Platform Terms). Pemilik proyek menyalin komentar publik ke `data/inbox/sosial/` secara legal. | 2026-10-16 |
| **Facebook** | Kotak Masuk Manual (*Manual Inbox*) | **MANUAL INBOX (SAH)** | **DILARANG scraping otomatis** tanpa izin tertulis. Menggunakan templat CSV manual inbox untuk kiriman halaman publik. | 2026-10-16 |
| **TikTok** | Program Riset Resmi / Tidak Akses | **DILEWATI** | Akses komersial/scraping melanggar ToS. API riset memerlukan afiliasi universitas. Dilewati demi kepatuhan. | 2026-10-16 |
| **X (Twitter) & Threads** | X API v2 (Pro/Enterprise) | **DILEWATI** | Skema harga API berbayar tinggi ($100–$5.000/bln). Scraping tanpa API dilarang keras. Dilewati secara sadar. | 2026-10-16 |
| **Telegram** | Telegram Client API Resmi | **OPSIONAL (API)** | Hanya kanal publik komunitas pengemudi/warga yang bersifat terbuka tanpa login tertutup. | 2026-10-16 |
| **WhatsApp / DM / Grup Privat** | - | **DILARANG KERAS** | Melanggar privasi pribadi (UU PDP / GDPR). Sistem menolak memproses data percakapan privat. | 2026-10-16 |

---

## 2. Kebijakan Privasi & Sanitasi Data (Zero-PII)
1. **Pembersihan Otomatis**: Semua nama akun personal, nomor HP, plat kendaraan, dan alamat rumah warga wajib dihapus sebelum disimpan.
2. **Hashing Kredensial**: Jika diperlukan deduplikasi pelapor, identitas di-hash satu arah dengan garam SHA-256 (`HMAC-SHA256(text, salt)`).
3. **Keluaran Hanya Agregat**: Hasil yang dipublikasikan ke publik dan dashboard hanya berupa hitungan per jam/wilayah/kategori sentimen.
4. **Masa Retensi**: Teks mentah disimpan maksimal 30 hari untuk validasi silang, kemudian dihapus secara permanen.
