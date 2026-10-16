# Petunjuk Kotak Masuk Manual (data/inbox/sosial/)
*Jalur Sah Pengumpulan Percakapan Publik Media Sosial BaliFuel*

Folder ini disediakan untuk memasukkan laporan komentar publik dari platform seperti Instagram dan Facebook secara **sah dan patuh hukum** (tanpa scraping otomatis yang melanggar ketentuan platform).

---

## Cara Menambahkan Laporan Warga
1. Buat file CSV baru di folder ini, misalnya `inbox_20261016.csv` (atau gunakan `TEMPLATE.csv`).
2. Kolom wajib:
   - `platform`: `Instagram` atau `Facebook`.
   - `url_postingan`: Tautan postingan publik (misal kiriman akun media/komunitas publik).
   - `tanggal`: Waktu komentar (format: `YYYY-MM-DD HH:MM WITA`).
   - `teks_komentar`: Teks komentar publik warga.
   - `suka`: Jumlah *likes* / *upvotes* pada komentar tersebut (angka integer).
3. **Aturan Privasi Wajib (Zero-PII)**:
   - JANGAN menyertakan nama akun pribadi (@username), nomor HP, plat nomor, atau identitas pribadi warga.
   - Sistem akan otomatis menghapus kata-kata sensitif dan mendeduplikasi teks menggunakan hash satu arah SHA-256.
4. Setiap kali pipeline berjalan (`run_pipeline.py`), modul `src/text_inbox.py` akan otomatis membaca seluruh file `.csv` di folder ini, memvalidasi formatnya, dan menggabungkannya ke dalam agregat sinyal sentimen krisis.
