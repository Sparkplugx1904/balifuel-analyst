"""
Forecast Module: Prediksi Ketersediaan BBM & Antrean per SPBU (72 Jam ke Depan)
Menghasilkan:
1. Probabilitas ketersediaan BBM per jam (0-71 jam) dengan pita ketidakpastian (P10, P50, P90)
2. Estimasi waktu hingga stok stabil pulih (hours to recovery)
3. Proyeksi waktu tunggu antrean (menit)
4. Identifikasi SPBU Hotspot paling rentan (ranking kerentanan krisis)
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

from src.cleaner import haversine_km, sanitize_for_json
from src.markov_model import BaliFuelMarkovEngine

DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")


def generate_station_forecasts(horizon_hours: int = 72) -> Dict[str, Any]:
    os.makedirs(CLEAN_DIR, exist_ok=True)
    
    # 1. Load cleaned stations
    with open(os.path.join(CLEAN_DIR, "cleaned_stations.json"), "r", encoding="utf-8") as f:
        stations = json.load(f)
        
    # 2. Load metrics
    with open(os.path.join(CLEAN_DIR, "crisis_metrics.json"), "r", encoding="utf-8") as f:
        metrics = json.load(f)

    # 3. Load external context
    with open(os.path.join(DATA_DIR, "external_context.json"), "r", encoding="utf-8") as f:
        context = json.load(f)

    # 4. Load Monte Carlo results for supply schedule alignment
    with open(os.path.join(CLEAN_DIR, "monte_carlo_results.json"), "r", encoding="utf-8") as f:
        mc_results = json.load(f)

    # Initialize Markov Engine
    engine = BaliFuelMarkovEngine(stations, context, metrics["diurnal_profile"])

    # Supply schedule over 72 hours:
    # Hour 0-7: Terminal running on remaining stock (~0.85x normal delivery)
    # Hour 7+: Kapal 3 bongkar muat (6,000 KL), pasokan meningkat bertahap ke 1.15x
    # Hour 24-48: Ritase truk penuh, 1.25x kapasitas
    # Hour 48-72: Pasokan melimpah, normalisasi stabil 1.10x
    supply_schedule = []
    for h in range(horizon_hours):
        if h < 7:
            supply_schedule.append(0.85)
        elif h < 24:
            supply_schedule.append(1.05 + 0.15 * ((h - 7) / 17.0))
        elif h < 48:
            supply_schedule.append(1.25)
        else:
            supply_schedule.append(1.10)

    start_dt_wita = datetime(2026, 10, 16, 3, 0, tzinfo=WITA_TZ)
    forecast_timestamps = [(start_dt_wita + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M WITA") for h in range(horizon_hours)]
    forecast_hours_label = [(start_dt_wita + timedelta(hours=h)).strftime("%d %b %H:00") for h in range(horizon_hours)]

    print(f"[*] Generating 72-hour forward forecasts for {len(stations)} stations...")

    forecasts = {}
    vulnerability_records = []

    for s in stations:
        s_id = s["id"]
        p0 = s.get("prob_pertalite")
        if p0 is None:
            p0 = 0.50
        uncertainty = s.get("uncertainty_score", 0.35)
        kind = s.get("kind", "spbu")
        area = s.get("area", "Denpasar")
        dist = engine.terminal_distances.get(s_id, 35.0)

        # Propagate Markov trajectory
        p_traj = engine.propagate_probabilities(s, p0, horizon_hours=horizon_hours, supply_schedule=supply_schedule)

        # Calculate uncertainty envelopes (P10, P50, P90)
        p50 = []
        p10 = []
        p90 = []
        q_proj = []

        q_initial = float(s.get("queue_mins") or 25.0)

        recovery_hour = None
        for h in range(horizon_hours):
            p_val = p_traj[h]
            # Uncertainty expands with horizon
            sigma_h = uncertainty * (1.0 + 0.012 * h) * 0.25
            lo = float(np.clip(p_val - 1.645 * sigma_h, 0.02, 0.98))
            hi = float(np.clip(p_val + 1.645 * sigma_h, 0.02, 0.98))
            med = float(np.clip(p_val, 0.02, 0.98))

            p50.append(round(med, 3))
            p10.append(round(lo, 3))
            p90.append(round(hi, 3))

            # Queue evolution: eases as availability increases
            # High queue when p_val is moderate (everyone rushes), eases when p_val > 0.85
            if p_val < 0.30:
                q_h = max(0.0, q_initial * 0.40)  # SPBU kosong, antrean bubar
            elif p_val < 0.75:
                q_h = max(10.0, q_initial * (1.0 - h / 90.0))  # masih antre
            else:
                q_h = max(3.0, q_initial * np.exp(-h / 24.0))  # pulih lancar
            q_proj.append(round(float(q_h), 1))

            # Recovery criteria for single SPBU: P >= 0.80 for 12 consecutive hours
            if recovery_hour is None and h >= 12 and all(p_traj[h_sub] >= 0.78 for h_sub in range(h - 11, h + 1)):
                recovery_hour = h - 11

        if recovery_hour is None:
            # Default to island median if not resolved in 72h
            recovery_hour = 48.0 if p0 >= 0.45 else 60.0

        recov_dt_wita = (start_dt_wita + timedelta(hours=float(recovery_hour))).strftime("%Y-%m-%d %H:%M WITA")

        # Vulnerability scoring (0 - 100):
        # 1. Initial emptiness: (1 - p0) * 35
        # 2. Distance to terminal: (dist / 70km) * 25
        # 3. Lookers / traffic pressure: min(20, lookers * 0.25)
        # 4. Kind factor: Pertamini more vulnerable to stockouts (+10)
        # 5. Non-24h penalty (+10)
        lookers = s.get("lookers", 0)
        vuln_score = (
            (1.0 - p0) * 35.0 +
            min(25.0, (dist / 70.0) * 25.0) +
            min(20.0, lookers * 0.25) +
            (10.0 if kind == "pertamini" else 0.0) +
            (0.0 if s.get("h24") else 10.0)
        )
        vuln_score = round(float(np.clip(vuln_score, 0.0, 100.0)), 1)

        forecasts[s_id] = {
            "id": s_id,
            "name": s["name"],
            "area": area,
            "kind": kind,
            "current_p_pertalite": round(p0, 3),
            "estimated_recovery_hours": round(float(recovery_hour), 1),
            "estimated_recovery_datetime_wita": recov_dt_wita,
            "vulnerability_score": vuln_score,
            "distance_to_terminal_km": round(dist, 1),
            "p50_traj": p50,
            "p10_traj": p10,
            "p90_traj": p90,
            "queue_traj_mins": q_proj
        }

        vulnerability_records.append({
            "id": s_id,
            "name": s["name"],
            "kind": kind,
            "code": s.get("code") or "-",
            "address": s.get("address") or "-",
            "area": area,
            "subdistrict": s.get("subdistrict") or "-",
            "lat": s.get("lat"),
            "lon": s.get("lon"),
            "current_p_pertalite": round(p0, 3),
            "queue_mins": s.get("queue_mins"),
            "distance_terminal_km": round(dist, 1),
            "vulnerability_score": vuln_score,
            "estimated_recovery_date": recov_dt_wita,
            "lookers": lookers
        })

    # Sort hotspots
    df_vuln = pd.DataFrame(vulnerability_records).sort_values("vulnerability_score", ascending=False)
    raw_hotspots = df_vuln.head(20).to_dict(orient="records")
    top_20_hotspots = sanitize_for_json(raw_hotspots)

    # Save outputs
    out_forecast = {
        "start_datetime_wita": start_dt_wita.strftime("%Y-%m-%d %H:%M WITA"),
        "timestamps": forecast_timestamps,
        "hours_label": forecast_hours_label,
        "stations_forecast": forecasts
    }

    forecast_json_path = os.path.join(CLEAN_DIR, "station_forecasts.json")
    with open(forecast_json_path, "w", encoding="utf-8") as f:
        json.dump(sanitize_for_json(out_forecast), f, ensure_ascii=False, indent=2, allow_nan=False)

    hotspots_json_path = os.path.join(CLEAN_DIR, "vulnerable_hotspots.json")
    with open(hotspots_json_path, "w", encoding="utf-8") as f:
        json.dump(top_20_hotspots, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f"[+] Forecast generated for {len(forecasts)} stations.")
    print(f"[+] Top 5 Most Vulnerable Hotspots:")
    for h in top_20_hotspots[:5]:
        print(f"    - [{h['kind'].upper()}] {h['name']} ({h['area']}) | Skor Kerentanan: {h['vulnerability_score']} | Jarak Terminal: {h['distance_terminal_km']} km | Pulih: {h['estimated_recovery_date']}")

    return {
        "forecast_path": forecast_json_path,
        "hotspots_path": hotspots_json_path,
        "total_stations": len(forecasts),
        "top_hotspots_count": len(top_20_hotspots)
    }


if __name__ == "__main__":
    generate_station_forecasts()
