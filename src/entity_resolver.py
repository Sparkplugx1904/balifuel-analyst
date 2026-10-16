"""
Entity Resolution & Canonical Master SPBU Generator
Menyatukan lintas sumber data stasiun BBM di Bali:
1. Normalisasi Kode SPBU Pertamina (54.80x.xx)
2. Pencocokan spasial (Haversine <= 150m) + Fuzzy string matching
3. Klasifikasi entitas: SPBU Resmi (COCO/DODO), Pertashop, Pertamini
4. Menghasilkan:
   - data/master/spbu.parquet (Master Kanonik)
   - data/master/review.csv (Kasus Ambigu)
   - output/spbu_coverage_report.json (Laporan Cakupan)
"""

import os
import sys
import re
import json
import sqlite3
import pandas as pd
import numpy as np
from difflib import SequenceMatcher
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_DIR = os.path.join(DATA_DIR, "master")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")


def normalize_pertamina_code(raw_code: Optional[str]) -> Optional[str]:
    """Menormalisasi kode SPBU Pertamina ke format standar 54.80X.XX."""
    if not raw_code or not isinstance(raw_code, str):
        return None
    c = raw_code.strip().replace(" ", "").replace("-", ".").replace("_", ".")
    match = re.search(r"(5[45])\.?(80[0-9])\.?([0-9]{2,3})", c)
    if match:
        reg, district, st_num = match.groups()
        return f"{reg}.{district}.{st_num}"
    match2 = re.search(r"(5[45]80[0-9]{3,4})", c)
    if match2:
        digits = match2.group(1)
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:]}"
    return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    return float(2.0 * R * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


def string_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower().strip(), s2.lower().strip()).ratio()


def run_entity_resolution():
    os.makedirs(MASTER_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("[*] Starting Entity Resolution across Station Data Sources...")

    conn = sqlite3.connect(DB_PATH)
    df_db_stations = pd.read_sql_query("SELECT * FROM stations_master", conn)
    conn.close()

    with open(os.path.join(DATA_DIR, "clean", "cleaned_stations.json"), "r", encoding="utf-8") as f:
        clean_stations = json.load(f)

    # 1. Koleksi semua kandidat mentah
    candidates = []
    for s in clean_stations:
        norm_c = normalize_pertamina_code(s.get("code") or s.get("name"))
        candidates.append({
            "source_id": s["id"],
            "raw_name": s.get("name", ""),
            "raw_code": s.get("code", ""),
            "norm_code": norm_c,
            "kind": s.get("kind", "spbu"),
            "brand": s.get("brand", "pertamina"),
            "lat": float(s["lat"]) if s.get("lat") else None,
            "lon": float(s["lon"]) if s.get("lon") else None,
            "area": s.get("area", "Bali"),
            "regency": s.get("regency", ""),
            "address": s.get("address", ""),
            "h24": bool(s.get("h24", False)),
            "source": "BensinBali+BaliFuelWatch"
        })

    # Tambahkan ODbL stations
    raw_files = [f for f in os.listdir(os.path.join(DATA_DIR, "raw")) if f.endswith("_odbl_stations.json")]
    if raw_files:
        latest_odbl = sorted(raw_files)[-1]
        with open(os.path.join(DATA_DIR, "raw", latest_odbl), "r", encoding="utf-8") as f:
            odbl_data = json.load(f)
            for os_st in odbl_data.get("stations", []):
                norm_c = normalize_pertamina_code(os_st.get("code") or os_st.get("name"))
                candidates.append({
                    "source_id": f"OSM-{os_st.get('id')}",
                    "raw_name": os_st.get("name", ""),
                    "raw_code": os_st.get("code", ""),
                    "norm_code": norm_c,
                    "kind": "spbu",
                    "brand": "pertamina",
                    "lat": float(os_st["lat"]) if os_st.get("lat") else None,
                    "lon": float(os_st["lon"]) if os_st.get("lon") else None,
                    "area": os_st.get("area", "Bali"),
                    "regency": os_st.get("regency", ""),
                    "address": os_st.get("addr", ""),
                    "h24": bool(os_st.get("h24", False)),
                    "source": "OpenStreetMap_ODbL"
                })

    print(f"[*] Aggregated {len(candidates)} raw station candidate records across sources.")

    # 2. Resolusi Entitas Hirarkis
    # Klasterisasi berdasarkan Kode Pertamina yang valid, atau Kedekatan Spasial <= 150m + Nama Mirip
    resolved_clusters = []
    review_cases = []

    # Map kode ternormalisasi
    code_groups: Dict[str, List[Dict[str, Any]]] = {}
    spatial_pool: List[Dict[str, Any]] = []

    for c in candidates:
        if c["norm_code"]:
            code_groups.setdefault(c["norm_code"], []).append(c)
        else:
            spatial_pool.append(c)

    # A. Buat entitas kanonik dari grup kode
    canonical_id_seq = 1000
    for code, group in code_groups.items():
        canonical_id_seq += 1
        cid = f"BALI-SPBU-{canonical_id_seq}"
        
        # Ekstrak representatif terbaik
        lats = [g["lat"] for g in group if g["lat"] is not None]
        lons = [g["lon"] for g in group if g["lon"] is not None]
        names = [g["raw_name"] for g in group if g["raw_name"]]
        best_name = names[0] if names else f"SPBU {code}"
        
        # Hitung sumber unik
        unique_sources = set(g["source"] for g in group)
        conf_score = 1.0 if len(unique_sources) >= 2 else 0.90

        resolved_clusters.append({
            "id_kanonik": cid,
            "kode_pertamina_normal": code,
            "nama": best_name,
            "tipe": "SPBU",
            "lat": float(np.mean(lats)) if lats else -8.45,
            "lon": float(np.mean(lons)) if lons else 115.15,
            "kabupaten": group[0].get("regency") or group[0].get("area", "Bali"),
            "kecamatan": group[0].get("area", "Bali"),
            "produk": ["Pertalite", "Pertamax", "Solar", "Dexlite"],
            "nozzle_estimasi": 6 if group[0].get("h24") else 4,
            "is_24_jam": any(g.get("h24") for g in group),
            "sumber_terverifikasi": list(unique_sources),
            "jumlah_sumber": len(unique_sources),
            "skor_keyakinan": conf_score
        })

    # B. Resolusi spasial untuk sisa kandidat
    unmatched = []
    for cand in spatial_pool:
        if cand["lat"] is None or cand["lon"] is None:
            continue
        
        # Cek jarak ke master SPBU yang sudah ada
        matched = False
        for ex in resolved_clusters:
            dist_m = haversine_m(cand["lat"], cand["lon"], ex["lat"], ex["lon"])
            sim = string_similarity(cand["raw_name"], ex["nama"])
            if dist_m <= 150 and sim >= 0.60:
                # Merge into existing entity
                if cand["source"] not in ex["sumber_terverifikasi"]:
                    ex["sumber_terverifikasi"].append(cand["source"])
                    ex["jumlah_sumber"] += 1
                    ex["skor_keyakinan"] = min(1.0, ex["skor_keyakinan"] + 0.05)
                matched = True
                break
            elif dist_m <= 250 and sim >= 0.45:
                # Ambiguous case for manual review
                review_cases.append({
                    "id_kandidat": cand["source_id"],
                    "nama_kandidat": cand["raw_name"],
                    "id_pembanding": ex["id_kanonik"],
                    "nama_pembanding": ex["nama"],
                    "jarak_meter": round(dist_m, 1),
                    "kemiripan_nama": round(sim, 3),
                    "alasan_ambigu": "Jarak dekat (150-250m) dengan nama agak mirip tapi kode tidak ada"
                })

        if not matched:
            unmatched.append(cand)

    # C. Masukkan unmatched sebagai entitas mandiri (bedakan SPBU, Pertashop, Pertamini)
    for u in unmatched:
        canonical_id_seq += 1
        cid = f"BALI-KIND-{canonical_id_seq}"
        raw_kind = (u.get("kind") or "pertamini").lower()
        if "pertashop" in u.get("raw_name", "").lower():
            tipe = "Pertashop"
            prod = ["Pertalite", "Pertamax"]
        elif raw_kind == "spbu" or "spbu" in u.get("raw_name", "").lower():
            tipe = "SPBU"
            prod = ["Pertalite", "Pertamax", "Solar"]
        else:
            tipe = "Pertamini"
            prod = ["Pertalite"]

        resolved_clusters.append({
            "id_kanonik": cid,
            "kode_pertamina_normal": u.get("norm_code"),
            "nama": u["raw_name"],
            "tipe": tipe,
            "lat": u["lat"],
            "lon": u["lon"],
            "kabupaten": u.get("regency") or u.get("area", "Bali"),
            "kecamatan": u.get("area", "Bali"),
            "produk": prod,
            "nozzle_estimasi": 4 if tipe == "SPBU" else (2 if tipe == "Pertashop" else 1),
            "is_24_jam": bool(u.get("h24", False)),
            "sumber_terverifikasi": [u["source"]],
            "jumlah_sumber": 1,
            "skor_keyakinan": 0.85 if tipe == "SPBU" else 0.75
        })

    master_df = pd.DataFrame(resolved_clusters)

    # 3. Simpan ke data/master/spbu.parquet
    parquet_path = os.path.join(MASTER_DIR, "spbu.parquet")
    # Convert list column to string representation for parquet compatibility
    master_df_save = master_df.copy()
    master_df_save["produk"] = master_df_save["produk"].apply(lambda p: ",".join(p))
    master_df_save["sumber_terverifikasi"] = master_df_save["sumber_terverifikasi"].apply(lambda s: ",".join(s))
    master_df_save.to_parquet(parquet_path, index=False)
    print(f"[+] Saved Canonical Master: {parquet_path} ({len(master_df_save)} canonical entities)")

    # 4. Simpan ke data/master/review.csv
    review_path = os.path.join(MASTER_DIR, "review.csv")
    review_df = pd.DataFrame(review_cases)
    review_df.to_csv(review_path, index=False)
    print(f"[+] Saved Ambiguity Review Cases: {review_path} ({len(review_df)} ambiguous cases flagged)")

    # 5. Hitung Cakupan Terhadap ~214 SPBU Resmi Bali
    official_spbu = master_df[master_df["tipe"] == "SPBU"]
    total_spbu = len(official_spbu)
    ge1_src = len(official_spbu[official_spbu["jumlah_sumber"] >= 1])
    ge2_src = len(official_spbu[official_spbu["jumlah_sumber"] >= 2])
    ge3_src = len(official_spbu[official_spbu["jumlah_sumber"] >= 3])

    coverage_report = {
        "timestamp_wita": datetime.now(WITA_TZ).strftime("%Y-%m-%d %H:%M:%S WITA"),
        "total_canonical_entities": len(master_df),
        "breakdown_by_type": master_df["tipe"].value_counts().to_dict(),
        "official_pertamina_spbu": {
            "target_benchmark": 214,
            "total_resolved": total_spbu,
            "coverage_pct_vs_benchmark": round((total_spbu / 214.0) * 100, 2),
            "sources_overlap": {
                "ge_1_source_count": ge1_src,
                "ge_1_source_pct": round(ge1_src / total_spbu * 100, 2),
                "ge_2_sources_count": ge2_src,
                "ge_2_sources_pct": round(ge2_src / total_spbu * 100, 2),
                "ge_3_sources_count": ge3_src,
                "ge_3_sources_pct": round(ge3_src / total_spbu * 100, 2)
            }
        },
        "ambiguous_cases_flagged": len(review_df)
    }

    coverage_path = os.path.join(OUTPUT_DIR, "spbu_coverage_report.json")
    with open(coverage_path, "w", encoding="utf-8") as f:
        json.dump(coverage_report, f, indent=2)

    print("\n" + "=" * 60)
    print(" CANONICAL SPBU MASTER ENTITY RESOLUTION REPORT")
    print("=" * 60)
    print(f" Total Canonical Entities Resolved : {len(master_df)}")
    print(f" Breakdown by Type                 : {coverage_report['breakdown_by_type']}")
    print(f" Official SPBU Resolved            : {total_spbu} (Target: ~214)")
    print(f" Coverage >= 1 Source              : {ge1_src} ({coverage_report['official_pertamina_spbu']['sources_overlap']['ge_1_source_pct']}%)")
    print(f" Coverage >= 2 Sources (Cross-Val) : {ge2_src} ({coverage_report['official_pertamina_spbu']['sources_overlap']['ge_2_sources_pct']}%)")
    print(f" Ambiguous Cases Flagged           : {len(review_df)}")
    print("=" * 60)

    return coverage_report


if __name__ == "__main__":
    run_entity_resolution()
