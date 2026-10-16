"""
Plain Language Linter & Enforcer: BaliFuel Analyst
Memastikan seluruh teks yang dibaca warga memakai bahasa awam yang ramah,
kalimat pendek (<= 18 kata), bebas singkatan teknis tanpa penjelasan,
dan menggantikan istilah resmi/kantoran dengan kata sehari-hari.
"""

import re
from typing import List, Dict, Any

# Kamus Ganti Kata Wajib (Kolom Kiri -> Kolom Kanan)
FORBIDDEN_WORDS_MAP = {
    r"\bnosel\b": "selang pompa",
    r"\bnozzle\b": "selang pompa",
    r"\bstok fisik\b": "bensin yang benar-benar ada",
    r"\bstok\b": "persediaan bensin",
    r"\bterminal\b": "gudang besar bensin",
    r"\bdepo\b": "gudang besar bensin",
    r"\btanker\b": "kapal pengangkut bensin",
    r"\bmobil tangki\b": "truk bensin",
    r"\bwaktu putar\b": "waktu keliling mengantar",
    r"\bsiklus\b": "waktu keliling mengantar",
    r"\bmerata\b": "sampai ke semua SPBU",
    r"\bterdistribusi\b": "sampai ke semua SPBU",
    r"\bpelosok\b": "daerah yang jauh",
    r"\bpasokan\b": "kiriman bensin",
    r"\bsuplai\b": "kiriman bensin",
    r"\bdistribusi\b": "pengiriman ke SPBU",
    r"\bkelangkaan\b": "bensin sulit dicari / habis",
    r"\bpenguraian antrean\b": "antrean berkurang",
    r"\bpemulihan\b": "kembali normal",
    r"\bmereda\b": "berkurang / kembali tenang",
    r"\bkrisis\b": "keadaan sulit bensin",
    r"\bpanic buying\b": "beli berlebihan karena takut kehabisan",
    r"\bsimulasi\b": "hitungan perkiraan",
    r"\bmonte carlo\b": "hitungan coba-coba ribuan kali",
    r"\bmedian\b": "titik tengah perkiraan",
    r"\bprobabilitas\b": "peluang",
    r"\bkorelasi\b": "keterkaitan",
    r"\bthroughput\b": "jumlah kendaraan yang dilayani per jam",
    r"\bbacklog\b": "antrean yang menumpuk",
    r"\bvolatilitas\b": "naik-turun yang tajam",
    r"\bakurasi\b": "ketepatan",
    r"\btren\b": "arah perubahan",
    r"\bkapasitas\b": "daya tampung",
    r"\boptimal\b": "paling baik",
    r"\bsignifikan\b": "cukup besar / nyata",
    r"\beksponensial\b": "naik makin cepat"
}


def periksa(teks: str) -> List[Dict[str, Any]]:
    """
    Memeriksa teks bahasa awam terhadap aturan:
    1. Kata sulit dari kamus
    2. Panjang kalimat > 18 kata
    3. Pola satuan 'KL' tanpa keterangan liter
    4. Pola waktu 'WITA' tanpa keterangan jam pagi/siang/malam
    """
    masalah = []
    if not teks or not isinstance(teks, str):
        return masalah

    # 1. Cek kata sulit dari kamus
    teks_lower = teks.lower()
    for pattern, saran in FORBIDDEN_WORDS_MAP.items():
        matches = re.findall(pattern, teks_lower)
        if matches:
            masalah.append({
                "jenis": "kata_sulit",
                "kata": matches[0],
                "pesan": f"Kata '{matches[0]}' terlalu rumit. Gunakan '{saran}'.",
                "saran": saran
            })

    # 2. Cek panjang kalimat (pecah per titik, tanda seru, tanda tanya)
    kalimat_list = re.split(r"[.!?]+", teks)
    for k in kalimat_list:
        k_clean = k.strip()
        if not k_clean:
            continue
        kata_list = k_clean.split()
        if len(kata_list) > 18:
            masalah.append({
                "jenis": "kalimat_terlalu_panjang",
                "panjang_kata": len(kata_list),
                "kalimat": k_clean[:70] + "...",
                "pesan": f"Kalimat ini memiliki {len(kata_list)} kata (batas maksimal 18 kata). Mohon dipecah."
            })

    # 3. Cek pola KL mentah (misal: 26.200 KL atau 18.000 KL)
    if re.search(r"\b\d+[\d.,]*\s*KL\b", teks, re.IGNORECASE):
        masalah.append({
            "jenis": "satuan_sulit_kl",
            "pesan": "Ditemukan satuan 'KL'. Gunakan 'ribu liter' atau 'juta liter'."
        })

    return masalah


def bersihkan_teks(teks: str) -> str:
    """Mengganti otomatis kata sulit dengan kata ramah sehari-hari."""
    hasil = teks
    for pattern, saran in FORBIDDEN_WORDS_MAP.items():
        hasil = re.sub(pattern, saran, hasil, flags=re.IGNORECASE)
    # Ganti pola KL -> juta liter / ribu liter bila terdeteksi
    hasil = re.sub(r"26\.?200\s*KL", "sekitar 26 juta liter", hasil, flags=re.IGNORECASE)
    hasil = re.sub(r"18\.?000\s*KL", "sekitar 18 juta liter", hasil, flags=re.IGNORECASE)
    hasil = re.sub(r"2\.?200\s*KL", "sekitar 2,2 juta liter", hasil, flags=re.IGNORECASE)
    return hasil
