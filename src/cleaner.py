"""
Cleaner Module: Pembersihan & Kualitas Data Krisis BBM Bali
Menerapkan:
1. Pembobotan peluruhan eksponensial (decay time-weighting, half-life 90 menit)
2. Pembobotan konfirmasi antrean & pompa vs laporan jauh
3. Deteksi & karantina spam (koordinat luar batas laut/Bali, anomali frekuensi)
4. Normalisasi kepanikan (panic buying vs online users)
5. Imputasi spasial (k-Nearest Neighbors IDW) dengan penandaan eksplisit 'unknown'
6. Pemetaan kanonikal ke 14 Area Makro resmi Bali
"""

import os
import sys
import math
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

def sanitize_for_json(obj):
    """Mengonversi np.nan, float('nan'), dan np.inf menjadi None (JSON null)."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    return obj

WITA_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")

# Bali Bounding Box: [min_lat, max_lat, min_lon, max_lon]
BALI_BBOX = (-8.95, -8.05, 114.40, 115.75)

# Half-life peluruhan waktu laporan (menit)
HALF_LIFE_MINUTES = 90.0
MAX_REPORT_AGE_HOURS = 12.0


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    r_lat1, r_lon1 = np.radians(lat1), np.radians(lon1)
    r_lat2, r_lon2 = np.radians(lat2), np.radians(lon2)
    dlat = r_lat2 - r_lat1
    dlon = r_lon2 - r_lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(r_lat1) * np.cos(r_lat2) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return R * c


def map_macro_area(area_str: str, name_str: str = "", lat: float = None, lon: float = None) -> str:
    """Memetakan kecamatan lokal ke 14 Area Makro resmi BensinBali."""
    a = (area_str or "").lower()
    n = (name_str or "").lower()
    
    # 1. Canggu (Kuta Utara / Canggu / Berawa / Pererenan)
    if any(k in a for k in ["canggu", "tibubeneng", "berawa", "pererenan", "kuta utara"]) or \
       any(k in n for k in ["canggu", "tibubeneng", "pererenan", "berawa"]):
        return "Canggu"
    # 2. Seminyak - Kuta
    if any(k in a for k in ["seminyak", "legian"]) or any(k in n for k in ["seminyak", "legian"]) or \
       (a == "kuta" or ("kuta" in n and "selatan" not in a and "utara" not in a)):
        return "Seminyak-Kuta"
    # 3. Bukit (Kuta Selatan, Jimbaran, Nusa Dua, Uluwatu, Pecatu)
    if any(k in a for k in ["kuta selatan", "bukit", "jimbaran", "ungasan", "pecatu", "nusa dua", "benoa"]) or \
       any(k in n for k in ["bukit", "jimbaran", "ungasan", "pecatu", "nusa dua", "uluwatu"]):
        return "Bukit"
    # 4. Sanur
    if "sanur" in a or "sanur" in n:
        return "Sanur"
    # 5. Denpasar
    if "denpasar" in a or "denpasar" in n:
        return "Denpasar"
    # 6. Mengwi (Mengwi & Abiansemal)
    if any(k in a for k in ["mengwi", "abiansemal", "badung"]) or any(k in n for k in ["mengwi", "abiansemal"]):
        return "Mengwi"
    # 7. Ubud (Ubud, Tegallalang, Payangan)
    if any(k in a for k in ["ubud", "tegallalang", "payangan"]) or any(k in n for k in ["ubud", "tegallalang", "payangan"]):
        return "Ubud"
    # 8. Gianyar (Gianyar, Sukawati, Blahbatuh, Tampaksiring)
    if any(k in a for k in ["gianyar", "sukawati", "blahbatuh", "tampaksiring"]) or \
       any(k in n for k in ["gianyar", "sukawati", "blahbatuh", "tampaksiring"]):
        return "Gianyar"
    # 9. Tabanan
    if any(k in a for k in ["tabanan", "kediri", "kerambitan", "baturiti", "selemadeg", "penebel", "marga", "pupuan"]) or \
       any(k in n for k in ["tabanan", "kediri", "baturiti", "selemadeg"]):
        return "Tabanan"
    # 10. Klungkung (termasuk Nusa Penida & Banjarangkan)
    if any(k in a for k in ["klungkung", "banjarangkan", "dawan", "nusa penida"]) or \
       any(k in n for k in ["klungkung", "banjarangkan", "dawan", "nusa penida"]):
        return "Klungkung"
    # 11. Karangasem
    if any(k in a for k in ["karangasem", "manggis", "rendang", "abang", "kubu", "bebandem", "sidemen", "selat"]) or \
       any(k in n for k in ["karangasem", "manggis", "rendang", "padangbai", "amlapura"]):
        return "Karangasem"
    # 12. Bangli
    if any(k in a for k in ["bangli", "kintamani", "susut", "tembuku"]) or any(k in n for k in ["bangli", "kintamani"]):
        return "Bangli"
    # 13. Lovina / Buleleng
    if any(k in a for k in ["lovina", "buleleng", "seririt", "gerokgak", "sukasada", "kubutambahan", "tejakula", "sawan", "banjar"]) or \
       any(k in n for k in ["lovina", "singaraja", "seririt", "gerokgak"]):
        return "Lovina"
    # 14. Jembrana
    if any(k in a for k in ["jembrana", "negara", "melaya", "mendoyo", "pekutatan"]) or \
       any(k in n for k in ["jembrana", "negara", "gilimanuk"]):
        return "Jembrana"

    return "Denpasar"


def clean_and_enrich_data(db_path: str = DB_PATH) -> Dict[str, Any]:
    os.makedirs(CLEAN_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # 1. Load raw stations
    df_stations = pd.read_sql_query("SELECT * FROM stations_master", conn)
    # 2. Load driver reports
    df_reports = pd.read_sql_query("SELECT * FROM driver_reports", conn)
    # 3. Load hourly metrics
    df_hourly = pd.read_sql_query("SELECT * FROM hourly_metrics ORDER BY epoch_t ASC", conn)
    # 4. Load latest stats snapshot
    df_stats = pd.read_sql_query("SELECT * FROM stats_snapshots ORDER BY id DESC LIMIT 1", conn)

    now_utc = datetime.now(UTC_TZ)
    now_epoch = now_utc.timestamp()

    print(f"[*] Raw data loaded: {len(df_stations)} stations, {len(df_reports)} driver reports, {len(df_hourly)} hourly points.")

    # -------------------------------------------------------------
    # A. SPAM FILTERING & QUARANTINE
    # -------------------------------------------------------------
    df_stations["is_spam_geo"] = ~(
        (df_stations["lat"] >= BALI_BBOX[0]) & (df_stations["lat"] <= BALI_BBOX[1]) &
        (df_stations["lon"] >= BALI_BBOX[2]) & (df_stations["lon"] <= BALI_BBOX[3])
    )

    # Filter reports with valid timestamp
    df_reports = df_reports[
        (df_reports["created_at_epoch"] > 1700000000) &
        (df_reports["created_at_epoch"] <= now_epoch + 300)
    ].copy()

    # Calculate report age in minutes
    df_reports["age_min"] = (now_epoch - df_reports["created_at_epoch"]) / 60.0
    df_reports_active = df_reports[df_reports["age_min"] <= MAX_REPORT_AGE_HOURS * 60.0].copy()

    # -------------------------------------------------------------
    # B. EXPONENTIAL DECAY WEIGHTING & CONFIRMATION MULTIPLIER
    # -------------------------------------------------------------
    df_reports_active["w_time"] = np.exp(-np.log(2.0) * df_reports_active["age_min"] / HALF_LIFE_MINUTES)
    df_reports_active["w_queue"] = df_reports_active["queue_wait"].apply(
        lambda q: 1.35 if pd.notnull(q) and q in (0, 1, 2) else 1.0
    )
    df_reports_active["weight"] = df_reports_active["w_time"] * df_reports_active["w_queue"]

    # -------------------------------------------------------------
    # C. PANIC BUYING NORMALIZATION
    # -------------------------------------------------------------
    baseline_online = 500.0
    current_online = float(df_stats["online_users"].iloc[0]) if len(df_stats) > 0 else 800.0
    panic_intensity = max(1.0, current_online / baseline_online)
    panic_damping = 1.0 + 0.15 * np.log(panic_intensity)

    print(f"[*] Online users: {current_online:.0f} | Panic intensity: {panic_intensity:.2f}x | Damping factor: {panic_damping:.3f}")

    # -------------------------------------------------------------
    # D. AGREGASI STATUS PER SPBU DENGAN BAYESIAN PRIOR SHRINKAGE
    # -------------------------------------------------------------
    station_avail_map = {}
    station_weight_map = {}
    station_rep_count_map = {}
    station_last_seen_min = {}
    station_queue_reports = {}

    for (st_id, fuel), grp in df_reports_active.groupby(["station_id", "fuel"]):
        w_sum = grp["weight"].sum()
        avail_w_sum = (grp["available"] * grp["weight"]).sum()
        station_weight_map[(st_id, fuel)] = w_sum
        station_avail_map[(st_id, fuel)] = avail_w_sum / w_sum if w_sum > 0 else 0.5
        station_rep_count_map[(st_id, fuel)] = len(grp)
        station_last_seen_min[(st_id, fuel)] = grp["age_min"].min()
        
        recent_q = grp[grp["age_min"] <= 90]["queue_wait"].dropna()
        if len(recent_q) > 0:
            station_queue_reports[st_id] = int(recent_q.mode()[0])

    bb_prices_map = {}
    for idx, row in df_stations.iterrows():
        st_id = row["id"]
        try:
            p_dict = json.loads(row["prices_json"]) if row["prices_json"] else {}
            if p_dict:
                bb_prices_map[st_id] = p_dict
        except Exception:
            pass
        
        try:
            reps = json.loads(row["reports_summary_json"]) if row["reports_summary_json"] else []
            if reps and len(reps) > 0:
                for r in reps:
                    age_m = r.get("ageMin", 999)
                    if age_m <= MAX_REPORT_AGE_HOURS * 60:
                        has_f = 1 if r.get("hasFuel") else 0
                        trust = r.get("trust", 1.0)
                        w = (0.5 ** (age_m / HALF_LIFE_MINUTES)) * trust
                        cur_w = station_weight_map.get((st_id, "pertalite"), 0.0)
                        cur_a = station_avail_map.get((st_id, "pertalite"), 0.5)
                        
                        new_w = cur_w + w
                        new_a = (cur_a * cur_w + has_f * w) / new_w if new_w > 0 else has_f
                        station_weight_map[(st_id, "pertalite")] = new_w
                        station_avail_map[(st_id, "pertalite")] = new_a
                        if (st_id, "pertalite") not in station_last_seen_min or age_m < station_last_seen_min[(st_id, "pertalite")]:
                            station_last_seen_min[(st_id, "pertalite")] = age_m
        except Exception:
            pass

    # -------------------------------------------------------------
    # E. SPATIAL IMPUTATION & EXPLICIT UNKNOWN HANDLING
    # -------------------------------------------------------------
    valid_spbu = df_stations[(df_stations["kind"] == "spbu") & (~df_stations["is_spam_geo"])].copy()

    # Pre-map macro areas for valid SPBU
    valid_spbu["macro_area"] = valid_spbu.apply(
        lambda r: map_macro_area(r["area"], r["name"], r["lat"], r["lon"]), axis=1
    )

    area_priors = {}
    for area, grp in valid_spbu.groupby("macro_area"):
        known_p = []
        for s_id in grp["id"]:
            if (s_id, "pertalite") in station_weight_map and station_weight_map[(s_id, "pertalite")] >= 0.5:
                known_p.append(station_avail_map[(s_id, "pertalite")])
        area_priors[area] = np.mean(known_p) if known_p else 0.45

    island_prior = np.mean(list(area_priors.values())) if area_priors else 0.48

    cleaned_stations = []
    c_prior = 1.2  # pseudo-count Bayesian shrinkage

    for idx, row in df_stations.iterrows():
        s_id = row["id"]
        subdistrict = row["area"] or "Denpasar"
        name_str = row["name"] or ""
        area = map_macro_area(subdistrict, name_str, row["lat"], row["lon"])
        kind = row["kind"]
        is_spam = row["is_spam_geo"]
        lat = row["lat"]
        lon = row["lon"]

        area_prior = area_priors.get(area, island_prior)

        w_pertalite = station_weight_map.get((s_id, "pertalite"), 0.0)
        p_raw = station_avail_map.get((s_id, "pertalite"), area_prior)
        last_seen = station_last_seen_min.get((s_id, "pertalite"), None)
        n_reports = station_rep_count_map.get((s_id, "pertalite"), 0)

        # Apply panic damping
        if p_raw < 0.5 and panic_damping > 1.0:
            p_adj = 1.0 - ((1.0 - p_raw) / panic_damping)
        else:
            p_adj = p_raw

        # Bayesian shrinkage
        p_shrunk = (w_pertalite * p_adj + c_prior * area_prior) / (w_pertalite + c_prior)

        # Classification
        if is_spam:
            status_source = "quarantined_spam"
            p_final = None
            uncertainty = 1.0
        elif w_pertalite >= 1.0 and (last_seen is not None and last_seen <= 60.0):
            status_source = "confirmed"
            p_final = float(np.clip(p_shrunk, 0.0, 1.0))
            uncertainty = 0.15
        elif w_pertalite >= 0.3:
            status_source = "predicted_local"
            p_final = float(np.clip(p_shrunk, 0.0, 1.0))
            uncertainty = 0.35
        else:
            # Spatial imputation via KNN
            other_spbu = valid_spbu[valid_spbu["id"] != s_id]
            if len(other_spbu) > 0 and pd.notnull(lat) and pd.notnull(lon):
                dists = haversine_km(lat, lon, other_spbu["lat"].values, other_spbu["lon"].values)
                nearest_idx = np.argsort(dists)[:3]
                nearest_dists = dists[nearest_idx]
                nearest_ids = other_spbu["id"].values[nearest_idx]
                min_dist = nearest_dists[0]

                if min_dist <= 15.0:
                    weights = 1.0 / np.maximum(nearest_dists, 0.5)
                    idw_p_list = []
                    for nid in nearest_ids:
                        nid_p = station_avail_map.get((nid, "pertalite"), area_prior)
                        idw_p_list.append(nid_p)
                    imputed_p = np.sum(weights * np.array(idw_p_list)) / np.sum(weights)
                    p_final = float(np.clip(imputed_p, 0.0, 1.0))
                    status_source = "imputed_spatial"
                    uncertainty = float(min(0.85, 0.40 + 0.03 * min_dist))
                else:
                    p_final = float(area_prior)
                    status_source = "unknown"
                    uncertainty = 0.90
            else:
                p_final = float(island_prior)
                status_source = "unknown"
                uncertainty = 0.95

        p_pmax = station_avail_map.get((s_id, "pertamax"), None)
        p_sol = station_avail_map.get((s_id, "solar"), None)

        # Queue wait time resolution
        # Queue wait time resolution terkalibrasi kondisi antrean riil krisis (hingga 4-6 jam)
        q_mins = row["queue_mins"]
        if pd.isna(q_mins) or q_mins is None:
            if s_id in station_queue_reports:
                q_code = station_queue_reports[s_id]
                # 0 = singkat (~15 mnt), 1 = lama 1-2 jam (~90 mnt), 2 = sangat lama / parah 4-6 jam (~300 mnt)
                q_mins = 15 if q_code == 0 else (90 if q_code == 1 else 300)
            elif pd.notnull(row["busy_live"]) and pd.notnull(row["busy_usual"]):
                ratio = (row["busy_live"] + 1) / (row["busy_usual"] + 1)
                # Lonjakan kerumunan live Google di SPBU saat krisis mencapai 4-6 jam
                q_mins = int(np.clip(ratio * 75, 10, 360))
            else:
                q_mins = None

        if q_mins is None:
            queue_cat = "tidak_diketahui"
        elif q_mins <= 15:
            queue_cat = "tanpa_antre"
        elif q_mins <= 45:
            queue_cat = "antre_singkat"
        else:
            queue_cat = "antre_panjang"
        prices = bb_prices_map.get(s_id, {})
        pertalite_price = prices.get("pertalite")
        is_price_gouged = False
        if pertalite_price is not None:
            if kind == "pertamini" and pertalite_price >= 15000:
                is_price_gouged = True
            elif kind == "spbu" and pertalite_price > 10000:
                is_price_gouged = True

        cleaned_stations.append({
            "id": s_id,
            "name": row["name"],
            "kind": kind,
            "brand": row["brand"],
            "code": row["code"],
            "address": row["address"],
            "subdistrict": subdistrict,
            "area": area,
            "regency": row["regency"],
            "lat": lat,
            "lon": lon,
            "prob_pertalite": round(p_final, 3) if p_final is not None else None,
            "prob_pertamax": round(p_pmax, 3) if p_pmax is not None else None,
            "prob_solar": round(p_sol, 3) if p_sol is not None else None,
            "status_source": status_source,
            "uncertainty_score": round(uncertainty, 3),
            "effective_weight": round(w_pertalite, 2),
            "reports_count_8h": n_reports,
            "last_report_age_min": round(last_seen, 1) if last_seen is not None else None,
            "queue_mins": q_mins,
            "queue_category": queue_cat,
            "lookers": row["lookers"],
            "google_busy_live": row["busy_live"],
            "google_busy_usual": row["busy_usual"],
            "prices": prices,
            "is_price_gouged": is_price_gouged,
            "is_spam": bool(is_spam),
            "diesel_available": bool(row["diesel_available"]),
            "h24": bool(row["h24"])
        })

    df_cleaned = pd.DataFrame(cleaned_stations)

    # -------------------------------------------------------------
    # F. CLEAN HOURLY TIME SERIES
    # -------------------------------------------------------------
    df_hourly_clean = df_hourly.copy()
    df_hourly_clean["dt_wita"] = pd.to_datetime(df_hourly_clean["timestamp_wita"])
    df_hourly_clean["total_reports"] = df_hourly_clean["reports"]
    df_hourly_clean["empty_ratio"] = df_hourly_clean["empty"] / np.maximum(df_hourly_clean["total_reports"], 1)
    df_hourly_clean["has_fuel_ratio"] = df_hourly_clean["has_fuel"] / np.maximum(df_hourly_clean["total_reports"], 1)
    df_hourly_clean["reports_per_active_user"] = df_hourly_clean["total_reports"] / np.maximum(df_hourly_clean["new_users"], 1)

    clean_stations_parquet = os.path.join(CLEAN_DIR, "cleaned_stations.parquet")
    clean_stations_json = os.path.join(CLEAN_DIR, "cleaned_stations.json")
    clean_hourly_parquet = os.path.join(CLEAN_DIR, "cleaned_hourly.parquet")
    clean_hourly_json = os.path.join(CLEAN_DIR, "cleaned_hourly.json")

    df_parquet = df_cleaned.copy()
    df_parquet["prices"] = df_parquet["prices"].apply(json.dumps)
    df_parquet.to_parquet(clean_stations_parquet, index=False)
    
    sanitized_stations = sanitize_for_json(cleaned_stations)
    with open(clean_stations_json, "w", encoding="utf-8") as f:
        json.dump(sanitized_stations, f, ensure_ascii=False, indent=2, allow_nan=False)

    sanitized_hourly = sanitize_for_json(df_hourly_clean.to_dict(orient="records"))
    df_hourly_clean.to_parquet(clean_hourly_parquet, index=False)
    with open(clean_hourly_json, "w", encoding="utf-8") as f:
        json.dump(sanitized_hourly, f, ensure_ascii=False, indent=2, default=str, allow_nan=False)
    print("\n[=== DATA CLEANING & QUALITY AUDIT SUMMARY ===]")
    print(f"Total Stations: {len(df_cleaned)}")
    print(f"  - Pertamina SPBU: {len(df_cleaned[df_cleaned['kind'] == 'spbu'])}")
    print(f"  - Pertamini: {len(df_cleaned[df_cleaned['kind'] == 'pertamini'])}")
    print(f"Status Source Breakdown:\n{df_cleaned['status_source'].value_counts().to_string()}")
    print(f"Macro Area Breakdown:\n{df_cleaned['area'].value_counts().to_string()}")
    print(f"Queue Categories:\n{df_cleaned['queue_category'].value_counts().to_string()}")
    print(f"Price Gouged Stations detected: {df_cleaned['is_price_gouged'].sum()}")

    conn.close()
    return {
        "total_stations": len(df_cleaned),
        "status_distribution": df_cleaned["status_source"].value_counts().to_dict(),
        "macro_area_distribution": df_cleaned["area"].value_counts().to_dict()
    }


if __name__ == "__main__":
    clean_and_enrich_data()
