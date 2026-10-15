# BaliFuel Cloudflare Worker

Worker ini berfungsi sebagai:
1. **Papan Data Publik** (`GET /latest/<key>`): Menyajikan data live ke frontend GitHub Pages dengan CORS, Cache-Control 60 detik, dan dukungan ETag / 304 Not Modified.
2. **Pintu Masuk Ingest Data** (`PUT /ingest/<key>`): Menerima 4 berkas kontrak (`meta.json`, `summary.json`, `stations.json`, `history.json`) dari runner GitHub Actions menggunakan otentikasi Bearer token waktu-konstan (*timingSafeEqual*).
3. **Penyimpan State Relasional** (`GET|PUT /state/balifuel.db`): Menyimpan dan memulihkan basis data SQLite di Cloudflare R2 tanpa CORS (privat).
4. **Pemicu Otomatis (Cron Trigger 10 Menit)**: Memicu GitHub Actions `workflow_dispatch` untuk `.github/workflows/pipeline.yml` menggunakan `GH_TOKEN` dan `GH_REPO`.

## Konfigurasi Rahasia (Secrets)

Jalankan perintah berikut untuk mengonfigurasi rahasia Worker:

```bash
# Token untuk otentikasi runner pipeline
npx wrangler secret put INGEST_TOKEN

# GitHub Personal Access Token dengan izin repo & workflow
npx wrangler secret put GH_TOKEN
```

## Menjalankan Secara Lokal

```bash
cd worker
npx wrangler dev
```
Secara default, worker lokal berjalan di `http://127.0.0.1:8787`.

## Deploy ke Cloudflare

```bash
cd worker
npx wrangler deploy
```
