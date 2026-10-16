# Audit Baseline Hari-0: BaliFuel Analyst Prediction System

**Waktu Audit**: 2026-10-16 16:05 WITA  
**Total Sampel Laporan**: 29.630 laporan pengemudi across 878 titik SPBU & Pertamini  
**Pemisahan Data Evaluasi Out-of-Time**:
- **Train Split (70%)**: 20.741 laporan (< 2026-10-16 07:10 WITA)
- **Test Split (30%)**: 8.889 laporan (>= 2026-10-16 07:10 WITA, data belum pernah dilihat)

---

## 1. Hasil Evaluasi Model Hari-0 vs Pembanding Sederhana

Tiga pembanding wajib (*Mandatory Baselines*):
1. **Persistence**: Status terakhir yang dilaporkan di SPBU tersebut bertahan.
2. **Area-Hour Climatology**: Rata-rata historis ketersediaan bensin per area makro dan jam harian (0–23 WITA).
3. **Markov Engine Hari-0**: Inhomogeneous Markov chain 2-state awal dengan faktor diurnal dan jarak.

| Model / Metode | Brier Score (Lebih rendah lebih baik) | Log-Loss | ROC-AUC | Catatan & Diagnosis |
| :--- | :---: | :---: | :---: | :--- |
| **Persistence Baseline** | `0.4777` | `6.5696` | `0.5216` | Sangat buruk saat rezim krisis karena SPBU berganti status cepat (flash depletion). |
| **Area Climatology Baseline** | `0.2588` | `0.8261` | `0.4997` | Menangkap pola jam buka/tutup wilayah dengan baik, namun tidak memiliki resolusi per-SPBU. |
| **Markov Model Hari-0 (Mentah)** | `0.4073` | `1.3708` | `0.5074` | Menang vs Persistence (+14.75%), namun kalah vs Climatology (-57.35%) karena *uncalibrated probabilities* (terlalu yakin/ekstrem). |

---

## 2. Metrik Tanggal Pemulihan Pulau (Monte Carlo Hari-0)

- **Prediksi Asli Hari-0**: 17 Oktober 2026 05:00 WITA (+26 jam dari awal krisis).
- **Kenyataan Lapangan**: Tidak mungkin pulih dalam 26 jam karena kapal tanker baru sandar, defisit *backlog* tangki warga menembus 2.500+ KL, dan armada truk Pertamina membutuhkan 4–6 hari bolak-balik untuk mengisi 212 SPBU.
- **Selisih Galat Hari-0**: Meleset lebih dari **120 jam** (5 hari lebih cepat dari kenyataan fisik).
- **Cakupan Rentang 80% (CI80) Hari-0**: Hanya mencakup 16–22 Okt, gagal mencakup ekor risiko penundaan cuaca maritim di Selat Bali.

---

## 3. Daftar Cacat Sistemik yang Ditemukan pada Audit Hari-0

1. **Kebocoran Waktu & Pengurangan Jam Palsu**:
   Formula `recov_h = h - 47` pada Monte Carlo memotong 47 jam dari waktu stabilisasi yang sebenarnya tercapai.
2. **Penyempitan Skala Antrean (Capped under 60 min)**:
   Input survei `queue_wait = 2` dipatok 45 menit di `cleaner.py`, dan sumbu grafik di `charts.js` dipatok kaku pada `range: [0, 55]`. Di lapangan warga antre 4–6 jam.
3. **Ketiadaan Variabel Backlog**:
   Model lama mengabaikan tangki jutaan motor yang kosong, sehingga mengira bensin di SPBU langsung utuh begitu truk tiba.
4. **Kalibrasi Probabilitas Bimodal**:
   Model Markov mentah memprediksi peluang 0.95 atau 0.05 tanpa smoothing/Platt scaling, menaikkan penalti Brier score saat SPBU terlambat diisi truk.
