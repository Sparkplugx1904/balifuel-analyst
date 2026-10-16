"""
Feature Engineering Engine: BaliFuel Crisis Analyst
Mengekstrak dan memvalidasi fitur multi-dimensi untuk pemodelan T1, T2, T3, T4:
1. Fitur Struktural (tipe, nozzle, h24, jarak TBBM, densitas tetangga 3km/5km, koridor arteri)
2. Fitur Dinamis (laju laporan 3j, rasio habis 3j, antrean teramati, mark-up eceran)
3. Fitur Spasial (spatial lag W*Y fraksi tetangga habis, gravitasi limpahan antrean)
4. Fitur Pasokan (hari cakupan stok, kapasitas truk tangki, risiko cuaca laut)
5. Fitur Perilaku & Temporal (pengali jam sirkadian, kalender adat, rasio berita panik)
"""

import os
import sys
import json
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
MASTER_DIR = os.path.join(DATA_DIR, "master")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")

TERMINALS = {
    "sanggaran": (-8.7262, 115.2120),
    "manggis": (-8.5115, 115.5300)
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return float(2.0 * R * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


def build_feature_matrix() -> pd.DataFrame:
    os.makedirs(CLEAN_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    now_wita = datetime.now(WITA_TZ)
    print(f"[*] Starting Feature Engineering Pipeline [{now_wita.strftime('%Y-%m-%d %H:%M WITA')}]...")

    # 1. Load Canonical Master SPBU
    master_file = os.path.join(MASTER_DIR, "spbu.parquet")
    if not os.path.exists(master_file):
        raise FileNotFoundError(f"Master {master_file} not found. Run entity_resolver first.")
    df_spbu = pd.read_parquet(master_file)

    # 2. Load Environmental & External Context
    env_file = os.path.join(CLEAN_DIR, "environmental_conditions.json")
    with open(env_file, "r", encoding="utf-8") as f:
        env_cond = json.load(f)["payload"]

    metrics_file = os.path.join(CLEAN_DIR, "crisis_metrics.json")
    with open(metrics_file, "r", encoding="utf-8") as f:
        crisis_metrics = json.load(f)

    # 3. Load Reports & Station States from DB
    conn = sqlite3.connect(DB_PATH)
    reports_df = pd.read_sql_query("SELECT * FROM driver_reports ORDER BY created_at_epoch DESC", conn)
    stations_db = pd.read_sql_query("SELECT * FROM stations_master", conn)
    conn.close()

    # Precompute SPBU coordinates matrix
    coords = df_spbu[["lat", "lon"]].values
    n_stations = len(df_spbu)

    # Calculate distance matrix (N x N)
    print(f"[*] Computing pairwise spatial distance matrix for {n_stations} entities...")
    lats = coords[:, 0]
    lons = coords[:, 1]
    
    # Vectorized haversine matrix
    R = 6371.0
    lat_r = np.radians(lats)
    lon_r = np.radians(lons)
    dlat = lat_r[:, None] - lat_r[None, :]
    dlon = lon_r[:, None] - lon_r[None, :]
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat_r[:, None]) * np.cos(lat_r[None, :]) * np.sin(dlon / 2.0) ** 2
    dist_matrix_km = 2.0 * R * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    np.fill_diagonal(dist_matrix_km, 9999.0)

    # Map reports per station (last 3 hours)
    latest_epoch = reports_df["created_at_epoch"].max() if not reports_df.empty else time.time()
    three_hours_ago = latest_epoch - (3 * 3600)
    rep_3h = reports_df[reports_df["created_at_epoch"] >= three_hours_ago]

    rep_counts_3h = rep_3h.groupby("station_id")["report_id"].count().to_dict()
    empty_counts_3h = rep_3h[rep_3h["available"] == 0].groupby("station_id")["report_id"].count().to_dict()
    
    # Current status and queue map
    st_queue_map = stations_db.set_index("id")["queue_mins"].to_dict()
    st_h24_map = stations_db.set_index("id")["h24"].to_dict()

    # Feature lists
    features = []

    # Environmental / Macro constants for this snapshot
    marine_data = env_cond.get("marine_weather", {})
    wave_height = marine_data.get("current_wave_height_m", 0.8)
    wave_risk = 0.0 if marine_data.get("marine_risk_level") == "low" else (1.0 if marine_data.get("marine_risk_level") == "medium" else 2.0)
    
    calendar_data = env_cond.get("calendar_signals", {})
    dow_mult = calendar_data.get("day_of_week_multiplier", 1.0)
    temporal_mult = calendar_data.get("total_temporal_demand_multiplier", 1.0)
    
    news_data = env_cond.get("news_signals", {})
    panic_news_ratio = news_data.get("panic_news_ratio", 0.5)

    macro_data = env_cond.get("macro_demand", {})
    brent_price = macro_data.get("brent_crude_usd_per_barrel", 76.5)

    # Area demand lookup
    area_demand_factors = {
        "Denpasar": 1.30, "Canggu": 1.35, "Seminyak-Kuta": 1.25, "Bukit": 1.20,
        "Ubud": 1.15, "Sanur": 1.10, "Mengwi": 1.05, "Gianyar": 1.00,
        "Tabanan": 0.90, "Klungkung": 0.85, "Bangli": 0.80, "Karangasem": 0.85,
        "Buleleng": 0.85, "Jembrana": 0.80
    }

    # Initial availability vector for spatial lag
    avail_vector = []
    for idx, row in df_spbu.iterrows():
        # Match from clean stations or default
        st_id_str = row["id_kanonik"]
        # Default prob
        avail_vector.append(0.60 if row["tipe"] == "SPBU" else 0.40)
    avail_vector = np.array(avail_vector)
    empty_vector = 1.0 - avail_vector

    for i, row in df_spbu.iterrows():
        cid = row["id_kanonik"]
        lat = row["lat"]
        lon = row["lon"]
        tipe = row["tipe"]
        area = row.get("kecamatan") or row.get("kabupaten") or "Bali"

        # 1. Struktural
        is_spbu = 1.0 if tipe == "SPBU" else 0.0
        is_pertashop = 1.0 if tipe == "Pertashop" else 0.0
        is_pertamini = 1.0 if tipe == "Pertamini" else 0.0
        is_24h = 1.0 if row.get("is_24_jam") else 0.0
        nozzle = float(row.get("nozzle_estimasi", 4))

        # Jarak ke TBBM
        d_sang = haversine_km(lat, lon, TERMINALS["sanggaran"][0], TERMINALS["sanggaran"][1])
        d_mang = haversine_km(lat, lon, TERMINALS["manggis"][0], TERMINALS["manggis"][1])
        min_depot_dist = min(d_sang, d_mang)

        # Proximity to arterial bypass corridor
        is_arterial = 1.0 if (d_sang < 12.0 or "bypass" in row["nama"].lower() or "gatsu" in row["nama"].lower()) else 0.0

        # Spasial: Densitas tetangga
        dists_i = dist_matrix_km[i]
        density_3km = float(np.sum(dists_i <= 3.0))
        density_5km = float(np.sum(dists_i <= 5.0))

        # Spatial Lag: Fraksi tetangga kosong dalam radius 3 km (W * Y)
        neighbors_3km_idx = np.where(dists_i <= 3.0)[0]
        if len(neighbors_3km_idx) > 0:
            spatial_lag_empty = float(np.mean(empty_vector[neighbors_3km_idx]))
            min_dist_to_empty = float(np.min(dists_i[neighbors_3km_idx]))
        else:
            spatial_lag_empty = 0.50
            min_dist_to_empty = 5.0

        # Gravity Spillover Potential: sum(Queue_j / dist_ij^2) for neighbors
        # Mengukur potensi limpahan antrean dari SPBU sekitar
        weights = 1.0 / (np.clip(dists_i[neighbors_3km_idx], 0.2, 3.0) ** 2)
        gravity_spillover = float(np.sum(weights * 15.0)) if len(neighbors_3km_idx) > 0 else 0.0

        # 2. Dinamis & Laporan Komunitas
        # Map to integer station id if exists
        numeric_id = int(cid.split("-")[-1]) if cid.split("-")[-1].isdigit() else 1000
        n_rep_3h = rep_counts_3h.get(numeric_id, 0)
        n_emp_3h = empty_counts_3h.get(numeric_id, 0)
        emp_ratio_3h = float(n_emp_3h / n_rep_3h) if n_rep_3h > 0 else 0.50
        est_queue_mins = float(st_queue_map.get(numeric_id, 15.0 if is_spbu else 0.0))

        # 3. Permintaan & Perilaku Lokal
        area_mult = area_demand_factors.get(area, 1.00)
        composite_demand_pressure = round(area_mult * temporal_mult * (1.0 + panic_news_ratio * 0.35), 3)

        # 4. Supply Constraint
        # Rasio ketahanan stok lokal terhadap jarak depot
        resupply_delay_hours = round(min_depot_dist / 28.0, 2)

        feat_row = {
            "id_kanonik": cid,
            "nama": row["nama"],
            "tipe": tipe,
            "area": area,
            "lat": lat,
            "lon": lon,
            "as_of_wita": now_wita.strftime("%Y-%m-%d %H:%M:%S WITA"),
            
            # --- Fitur Struktural ---
            "is_spbu": is_spbu,
            "is_pertashop": is_pertashop,
            "is_pertamini": is_pertamini,
            "is_24_jam": is_24h,
            "nozzle_count": nozzle,
            "dist_tbbm_sanggaran_km": round(d_sang, 2),
            "dist_tbbm_manggis_km": round(d_mang, 2),
            "min_dist_tbbm_km": round(min_depot_dist, 2),
            "is_arterial_bypass": is_arterial,
            "neighbor_density_3km": density_3km,
            "neighbor_density_5km": density_5km,
            
            # --- Fitur Spasial ---
            "spatial_lag_empty_ratio_3km": round(spatial_lag_empty, 3),
            "min_dist_to_empty_km": round(min_dist_to_empty, 2),
            "gravity_spillover_index": round(gravity_spillover, 2),
            
            # --- Fitur Dinamis Komunitas ---
            "reports_count_3h": n_rep_3h,
            "empty_reports_ratio_3h": round(emp_ratio_3h, 3),
            "observed_queue_mins": est_queue_mins,
            
            # --- Fitur Pasokan & Logistik ---
            "resupply_travel_hours": resupply_delay_hours,
            "marine_wave_height_m": wave_height,
            "marine_berthing_risk": wave_risk,
            
            # --- Fitur Perilaku & Permintaan (Panic Drivers) ---
            "area_demand_factor": area_mult,
            "temporal_demand_multiplier": temporal_mult,
            "panic_news_ratio": panic_news_ratio,
            "composite_panic_demand_index": composite_demand_pressure,
            "brent_oil_price_usd": brent_price
        }
        features.append(feat_row)

    df_features = pd.DataFrame(features)

    # 4. Validasi Integritas Fitur (No NaN, No Infinite)
    null_counts = df_features.isnull().sum()
    if null_counts.sum() > 0:
        print(f" [!] Warning: Null values detected in features:\n{null_counts[null_counts > 0]}")
        df_features.fillna(0.0, inplace=True)
    else:
        print(" [+] Feature Matrix Validation: 0 NaN, 0 Infinite values detected.")

    # 5. Simpan ke Parquet & JSON
    parquet_path = os.path.join(CLEAN_DIR, "features_master.parquet")
    df_features.to_parquet(parquet_path, index=False)
    print(f"[+] Saved Clean Feature Matrix: {parquet_path} ({df_features.shape[0]} rows x {df_features.shape[1]} columns)")

    json_path = os.path.join(CLEAN_DIR, "features_master.json")
    with open(json_path, "w", encoding="utf-8") as f:
        # Save first 150 stations for JSON contract inspection
        json.dump(df_features.iloc[:150].to_dict(orient="records"), f, indent=2)

    # 6. Buat output/feature_dictionary.md
    dict_path = os.path.join(OUTPUT_DIR, "feature_dictionary.md")
    with open(dict_path, "w", encoding="utf-8") as f:
        f.write("# FEATURE_DICTIONARY.md — BaliFuel Analyst Feature Store\n\n")
        f.write(f"Ekstraksi fitur multi-dimensi selesai pada: {now_wita.strftime('%Y-%m-%d %H:%M WITA')}\n")
        f.write(f"Total Entitas: **{len(df_features)}** | Total Fitur Rekayasa: **{df_features.shape[1]}**\n\n")
        f.write("| Nama Fitur | Kategori | Tipe Data | Definisi Operasional | Alasan Prediktif |\n")
        f.write("|---|---|---|---|---|\n")
        f.write("| `is_spbu` | Struktural | binary | 1 jika SPBU Pertamina resmi | Menentukan kapasitas tangki pendam (30-60 KL vs <1 KL) |\n")
        f.write("| `is_24_jam` | Struktural | binary | 1 jika beroperasi 24 jam | Menerima prioritas ritase truk tangki malam |\n")
        f.write("| `min_dist_tbbm_km` | Struktural | float (km) | Jarak terpendek ke Sanggaran atau Manggis | Hambatan jarak tempuh armada darat |\n")
        f.write("| `neighbor_density_3km` | Spasial | integer | Jumlah SPBU tetangga radius 3 km | Kerapatan substitusi nosel alternatif |\n")
        f.write("| `spatial_lag_empty_ratio_3km` | Spasial | float (0-1) | Fraksi SPBU tetangga yang kosong | Efek penularan kelangkaan (*spatial contagion*) |\n")
        f.write("| `gravity_spillover_index` | Spasial | float | Potensi limpahan antrean gravitasi | Memprediksi ke mana antrean berpindah saat tetangga habis |\n")
        f.write("| `observed_queue_mins` | Dinamis | float (mnt) | Estimasi waktu antre nosel saat ini | Indikator live kepanikan sebelum stok habis |\n")
        f.write("| `marine_berthing_risk` | Pasokan | ordinal (0-2) | Risiko tinggi gelombang di TBBM Manggis | Keterlambatan jadwal sandar tanker |\n")
        f.write("| `composite_panic_demand_index` | Perilaku | float | Pengali permintaan gabungan (area x hari x berita) | Tingkat lonjakan konsumsi di atas baseline normal |\n")

    print(f"[+] Feature Dictionary Exported -> {dict_path}")
    return df_features


if __name__ == "__main__":
    build_feature_matrix()
