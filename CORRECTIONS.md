# Catatan Koreksi & Log Penemuan Masalah (CORRECTIONS.md)
*BaliFuel Analyst — Transparency & Systemic Bug Tracker*

Dokumen ini mencatat setiap ketidakcocokan yang ditemukan, akar penyebab matematis/logika, perbaikan kode yang dilakukan, dan pengujian otomatis yang mencegah terulang kembali.

---

### Koreksi #001: Prediksi Tanggal Bensin Tenang Terlalu Cepat (17 Okt vs Kenyataan 23 Okt)
- **Gejala / Laporan**: Dashboard menampilkan bensin tenang pada 17 Oktober 05:00 WITA, tidak masuk akal mengingat kapal baru sandar dan SPBU se-Bali masih langka.
- **Akar Masalah**:
  1. `simulation.py`: Stok awal SPBU diasumsikan 60% kapasitas pulau (~3.000 KL). Padahal secara riil berada di level kritis 16–18% (~800–900 KL).
  2. Ketiadaan variabel `unmet_backlog`: Defisit bahan bakar jutaan motor warga (~2.200–2.800 KL) diabaikan. Akibatnya bensin yang diantar truk dianggap tersimpan di tangki SPBU, padahal di lapangan langsung tersedot antrean dalam hitungan jam (*flash depletion*).
  3. Formula bug `recov_h = h - 47`: Saat stabilisasi tercapai pada jam ke-72, kode justru mencatat waktu pemulihan di jam ke-25 (hari berikutnya).
- **Perbaikan Kode**:
  - `src/simulation.py`: Memodelkan penjejakan akumulasi *backlog*, debit pompa, armada truk darurat Banyuwangi (2.950–3.250 KL/hari), dan memisahkan eksplisit **Fase 1: Stok SPBU Mulai Stabil** (22 Okt 09:00 WITA) dan **Fase 2: Krisis Mereda Penuh & Volume Normal** (23 Okt 02:00 WITA).
- **Tes Pencegah**:
  - `tests/test_consistency.py::test_recovery_date_logic` memastikan tanggal pemulihan $\ge$ waktu saat ini + minimal 72 jam di rezim krisis.

---

### Koreksi #002: Grafik Prediksi Antrean di Bawah 40 Menit (Warga Mengantre 4–6 Jam)
- **Gejala / Laporan**: Laporan warga nyata membuktikan antrean mengular hingga 6 jam, namun grafik inspektor SPBU menampilkan antrean di bawah 40 menit.
- **Akar Masalah**:
  1. `src/cleaner.py`: Kode `queue_wait = 2` ("Sangat Lama") dipatok statis pada 45 menit, dan rasio Google Live Busy diclip maksimal 60 menit.
  2. `docs/js/charts.js`: Sumbu kanan Plotly (`yaxis2`) memiliki konfigurasi kaku `range: [0, 55]`. Nilai di atas 55 menit tertekan ke bawah.
  3. `src/forecast.py`: Saat peluang bensin kosong ($p < 0.20$), model mengira antrean langsung bubar (`q_h = 25 * d_fac` atau ~35 menit). Di lapangan, warga tetap mematikan mesin berjam-jam menunggu truk tangki datang (*expectant queue*).
- **Perbaikan Kode**:
  - `src/cleaner.py`: Resolusi antrean krisis dinaikkan ke 300 menit (rentang 240–360 menit / 4–6 jam).
  - `docs/js/charts.js`: Sumbu `yaxis2` dibuat dinamis dengan skala jam (`0m`, `1 jam`, `2 jam`, `3 jam`, `4 jam`, `5 jam`, `6 jam`, `7 jam`).
  - `src/forecast.py`: Memodelkan antrean tunggu kedatangan truk saat SPBU kosong (180–360 menit berdasarkan jarak ke terminal).
- **Tes Pencegah**:
  - `tests/test_consistency.py::test_queue_scale_allows_extreme_wait` memverifikasi bahwa sumbu dan nilai antrean mampu menampung $\ge 300$ menit.

---

### Koreksi #003: Model Markov Mentah Kalah Telak vs Area Climatology
- **Gejala / Laporan**: Evaluasi Out-of-Time pada data uji membuktikan Brier score Markov Hari-0 (0.4073) jauh lebih buruk dibanding Area Climatology sederhana (0.2588).
- **Akar Masalah**:
  - Transisi Markov 1-langkah menghasilkan estimasi probabilitas yang terlalu ekstrem (0.95 vs 0.05) tanpa kalibrasi Platt/Isotonic, sehingga saat pasokan terlambat mendapat penalti kuadratik yang sangat besar.
- **Perbaikan Kode**:
  - `src/innovative_models.py` & `src/markov_model.py`: Menerapkan model *Ensemble Shrinkage* (bobot optimal out-of-time antara Markov, Climatology Area-Jam, dan EMA) serta kalibrasi Platt / Isotonic.
- **Tes Pencegah**:
  - `tests/test_consistency.py::test_brier_score_beats_persistence` memvalidasi gerbang G1 bahwa model produksi harus mengalahkan persistence baseline.
