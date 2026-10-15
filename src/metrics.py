"""
Metrics Module: Indeks Keparahan Krisis & Analisis Deret Waktu
Menghitung:
1. Composite Crisis Severity Index (CSI) per jam dan harian (skala 0-100)
2. Breakdown keparahan untuk tepat 14 Area Makro resmi di Bali
3. Deteksi titik balik perubahan (Change-point detection / CUSUM)
4. Pola siklus diurnal (efek jam sibuk vs malam)
5. Matriks korelasi spasial antar 14 area
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

WITA_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from src.cleaner import haversine_km

DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")

CANONICAL_14_AREAS = [
    "Canggu", "Seminyak-Kuta", "Bukit", "Sanur", "Denpasar", "Mengwi",
    "Ubud", "Gianyar", "Tabanan", "Klungkung", "Karangasem", "Bangli",
    "Lovina", "Jembrana"
]


def compute_crisis_metrics(db_path: str = DB_PATH) -> Dict[str, Any]:
    os.makedirs(CLEAN_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path)

    # 1. Load clean stations
    stations_path = os.path.join(CLEAN_DIR, "cleaned_stations.json")
    with open(stations_path, "r", encoding="utf-8") as f:
        stations = json.load(f)
    df_st = pd.DataFrame(stations)

    # 2. Load driver reports
    df_rep = pd.read_sql_query("SELECT * FROM driver_reports ORDER BY created_at_epoch ASC", conn)
    # 3. Load hourly metrics
    df_hm = pd.read_sql_query("SELECT * FROM hourly_metrics ORDER BY epoch_t ASC", conn)
    # 4. Load stats snapshot
    df_stats = pd.read_sql_query("SELECT * FROM stats_snapshots ORDER BY id DESC LIMIT 1", conn)

    print(f"[*] Computing Crisis Severity Index from {len(df_hm)} hourly epochs across 14 canonical areas...")

    # -----------------------------------------------------------------
    # A. HOURLY CRISIS SEVERITY INDEX (CSI)
    # -----------------------------------------------------------------
    csi_records = []
    df_rep["hour_epoch"] = (df_rep["created_at_epoch"] // 3600) * 3600
    queue_by_hour = df_rep.groupby("hour_epoch")["queue_wait"].apply(
        lambda s: {
            "long": int((s == 2).sum()),
            "short": int((s == 1).sum()),
            "none": int((s == 0).sum()),
            "total": int(len(s))
        }
    ).to_dict()

    for idx, row in df_hm.iterrows():
        t_epoch = row["epoch_t"]
        dt_utc = datetime.fromtimestamp(t_epoch, tz=timezone.utc)
        dt_wita = dt_utc.astimezone(WITA_TZ)

        tot_rep = max(1, row["reports"])
        empty_cnt = row["empty"]
        has_fuel_cnt = row["has_fuel"]
        empty_ratio = empty_cnt / tot_rep

        q_info = queue_by_hour.get(t_epoch, {"long": 0, "short": 0, "none": 0, "total": 0})
        q_tot = max(1, q_info["total"])
        queue_score = (q_info["long"] * 1.0 + q_info["short"] * 0.5) / q_tot

        # Stress factor from online activity
        reporters = row["reporters"]
        new_users = max(1, row["new_users"])
        user_stress = min(1.0, reporters / (0.10 * new_users + 1.0))

        # Island estimated empty SPBU share
        empty_station_share = np.clip(empty_ratio * 0.85 + 0.10, 0.05, 0.95)

        # Composite CSI [0 - 100]
        csi = (
            0.35 * (empty_ratio * 100.0) +
            0.25 * (queue_score * 100.0) +
            0.20 * (user_stress * 100.0) +
            0.20 * (empty_station_share * 100.0)
        )
        csi = float(np.clip(csi, 0.0, 100.0))

        if csi >= 70.0:
            status_label = "Kritis Akut (Merah)"
            traffic_light = "red"
        elif csi >= 50.0:
            status_label = "Siaga / Terganggu (Kuning-Oranye)"
            traffic_light = "amber"
        elif csi >= 25.0:
            status_label = "Pemulihan Bertahap (Kuning)"
            traffic_light = "yellow"
        else:
            status_label = "Terkendali / Normal (Hijau)"
            traffic_light = "green"

        csi_records.append({
            "epoch_t": t_epoch,
            "timestamp_wita": dt_wita.strftime("%Y-%m-%d %H:%M WITA"),
            "iso_wita": dt_wita.isoformat(),
            "date": dt_wita.strftime("%Y-%m-%d"),
            "hour": dt_wita.hour,
            "day_name": dt_wita.strftime("%A"),
            "total_reports": tot_rep,
            "empty_reports": empty_cnt,
            "has_fuel_reports": has_fuel_cnt,
            "empty_ratio": round(empty_ratio, 3),
            "reporters": reporters,
            "new_users": new_users,
            "queue_long_reports": q_info["long"],
            "queue_short_reports": q_info["short"],
            "csi": round(csi, 1),
            "status_label": status_label,
            "traffic_light": traffic_light
        })

    df_csi = pd.DataFrame(csi_records)

    # -----------------------------------------------------------------
    # B. CHANGE-POINT DETECTION (CUSUM ON CSI)
    # -----------------------------------------------------------------
    csi_vals = df_csi["csi"].values
    mean_csi = np.mean(csi_vals)
    std_csi = max(1.0, np.std(csi_vals))
    z_scores = (csi_vals - mean_csi) / std_csi

    s_pos = np.zeros(len(csi_vals))
    s_neg = np.zeros(len(csi_vals))
    threshold = 2.5
    drift = 0.4
    change_points = []

    for i in range(1, len(csi_vals)):
        s_pos[i] = max(0, s_pos[i - 1] + z_scores[i] - drift)
        s_neg[i] = min(0, s_neg[i - 1] + z_scores[i] + drift)
        if s_pos[i] > threshold:
            change_points.append({
                "index": i,
                "timestamp_wita": df_csi["timestamp_wita"].iloc[i],
                "direction": "Peningkatan Keparahan (Lonjakan Panic Buying)",
                "csi": df_csi["csi"].iloc[i]
            })
            s_pos[i] = 0
        elif abs(s_neg[i]) > threshold:
            change_points.append({
                "index": i,
                "timestamp_wita": df_csi["timestamp_wita"].iloc[i],
                "direction": "Penurunan Keparahan (Suplai Kapal Tanker Mulai Masuk)",
                "csi": df_csi["csi"].iloc[i]
            })
            s_neg[i] = 0

    # -----------------------------------------------------------------
    # C. AREA BREAKDOWN FOR EXACT 14 CANONICAL AREAS
    # -----------------------------------------------------------------
    area_metrics = []
    area_centroids = {}

    for area in CANONICAL_14_AREAS:
        st_area = df_st[df_st["area"] == area]
        spbu_area = st_area[st_area["kind"] == "spbu"]
        pertamini_area = st_area[st_area["kind"] == "pertamini"]
        
        tot_spbu = len(spbu_area)
        tot_pertamini = len(pertamini_area)
        lat_c = float(st_area["lat"].mean()) if len(st_area) > 0 else -8.5
        lon_c = float(st_area["lon"].mean()) if len(st_area) > 0 else 115.2
        area_centroids[area] = (lat_c, lon_c)

        # Average Pertalite availability
        valid_probs = spbu_area["prob_pertalite"].dropna()
        avg_prob_fuel = float(valid_probs.mean()) if len(valid_probs) > 0 else 0.45
        pct_empty_est = round((1.0 - avg_prob_fuel) * 100.0, 1)

        # Average Queue Minutes
        valid_q = spbu_area["queue_mins"].dropna()
        avg_queue_min = float(valid_q.mean()) if len(valid_q) > 0 else 22.0

        long_q_count = int((spbu_area["queue_category"] == "antre_panjang").sum())

        # Pertamini gouging count
        gouged_cnt = int(pertamini_area["is_price_gouged"].sum())
        gouged_rate = round((gouged_cnt / max(1, tot_pertamini)) * 100.0, 1)

        # Area Severity Score [0 - 100]
        area_csi = float(np.clip(
            0.50 * pct_empty_est +
            0.30 * min(100.0, avg_queue_min * 2.0) +
            0.20 * gouged_rate,
            0.0, 100.0
        ))

        area_metrics.append({
            "area": area,
            "spbu_count": tot_spbu,
            "pertamini_count": tot_pertamini,
            "total_stations": len(st_area),
            "lat": round(lat_c, 5),
            "lon": round(lon_c, 5),
            "avg_fuel_availability_pct": round(avg_prob_fuel * 100.0, 1),
            "pct_empty_stations": pct_empty_est,
            "avg_queue_minutes": round(avg_queue_min, 1),
            "long_queue_stations": long_q_count,
            "price_gouged_pertamini_count": gouged_cnt,
            "price_gouging_rate_pct": gouged_rate,
            "area_csi": round(area_csi, 1),
            "status": "Kritis" if area_csi >= 65 else ("Waspada" if area_csi >= 45 else "Moderat")
        })

    df_area = pd.DataFrame(area_metrics).sort_values("area_csi", ascending=False)

    # -----------------------------------------------------------------
    # D. DIURNAL PROFILE (EFEK JAM SIBUK / DAY-OF-WEEK)
    # -----------------------------------------------------------------
    hourly_agg = df_csi.groupby("hour").agg(
        avg_csi=("csi", "mean"),
        avg_empty_ratio=("empty_ratio", "mean"),
        avg_reports=("total_reports", "mean")
    ).reset_index()

    rep_mean = hourly_agg["avg_reports"].mean()
    hourly_agg["demand_multiplier"] = (hourly_agg["avg_reports"] / max(0.1, rep_mean)).round(2)
    diurnal_profile = hourly_agg.to_dict(orient="records")

    # -----------------------------------------------------------------
    # E. SPATIAL CORRELATION MATRIX (ANTAR 14 AREA)
    # -----------------------------------------------------------------
    spatial_corr = {}
    for a1 in CANONICAL_14_AREAS:
        spatial_corr[a1] = {}
        c1 = area_centroids[a1]
        for a2 in CANONICAL_14_AREAS:
            c2 = area_centroids[a2]
            dist_km = haversine_km(c1[0], c1[1], c2[0], c2[1])
            corr_val = np.exp(-dist_km / 28.0)
            spatial_corr[a1][a2] = round(float(corr_val), 3)

    # -----------------------------------------------------------------
    # F. SAVE METRICS OUTPUT
    # -----------------------------------------------------------------
    latest_csi = float(df_csi["csi"].iloc[-1]) if len(df_csi) > 0 else 49.0
    latest_status = df_csi["status_label"].iloc[-1] if len(df_csi) > 0 else "Pemulihan Bertahap (Kuning)"
    latest_traffic_light = df_csi["traffic_light"].iloc[-1] if len(df_csi) > 0 else "yellow"

    metrics_result = {
        "current_island_csi": latest_csi,
        "current_status": latest_status,
        "current_traffic_light": latest_traffic_light,
        "peak_csi": float(df_csi["csi"].max()),
        "peak_timestamp_wita": df_csi.loc[df_csi["csi"].idxmax()]["timestamp_wita"] if len(df_csi) > 0 else "",
        "latest_empty_spbu_pct": round(float(100.0 - (df_st[df_st["kind"]=="spbu"]["prob_pertalite"].mean()*100)), 1),
        "total_active_spbu": int((df_st["kind"] == "spbu").sum()),
        "total_pertamini": int((df_st["kind"] == "pertamini").sum()),
        "change_points": change_points,
        "diurnal_profile": diurnal_profile,
        "area_metrics": df_area.to_dict(orient="records"),
        "spatial_correlation": spatial_corr,
        "hourly_csi_timeseries": df_csi.to_dict(orient="records")
    }

    out_metrics_file = os.path.join(CLEAN_DIR, "crisis_metrics.json")
    with open(out_metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics_result, f, ensure_ascii=False, indent=2)

    df_csi.to_sql("crisis_severity_hourly", conn, if_exists="replace", index=False)
    df_area.to_sql("crisis_severity_area", conn, if_exists="replace", index=False)
    conn.close()

    print(f"[+] 14 Canonical Areas Processed:")
    for idx, r in df_area.iterrows():
        print(f"    - {r['area']:15} | CSI: {r['area_csi']:4.1f} | SPBU: {r['spbu_count']:2d} | Pertamini: {r['pertamini_count']:2d} | Kosong: {r['pct_empty_stations']:4.1f}%")

    return metrics_result


if __name__ == "__main__":
    compute_crisis_metrics()
