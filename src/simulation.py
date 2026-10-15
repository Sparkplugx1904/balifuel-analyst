"""
Monte Carlo Simulation Module: Simulasi Pemulihan Pasokan BBM Bali
Menjalankan 10.000 lintasan simulasi stok pulau, mengevaluasi 4 skenario kalibrasi:
- Skenario A: Pasokan Normal Cepat (Fast Resupply / Optimal Trucking)
- Skenario B: Pemulihan Bertahap (Base Case - Program 26.200 KL Pertamina)
- Skenario C: Gangguan Berkepanjangan (Prolonged Disruption / Cuaca & Keterlambatan)
- Skenario D: Gelombang Kedua / Panic Buying Lanjutan (Second Wave Spike)

Kriteria Krisis Mereda:
Persentase SPBU kosong <= 10% (ketersediaan >= 90%) dipertahankan selama 48 jam berturut-turut.
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

DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")


def run_monte_carlo_simulation(n_paths: int = 10000, random_seed: int = 42) -> Dict[str, Any]:
    np.random.seed(random_seed)
    os.makedirs(CLEAN_DIR, exist_ok=True)

    # Load metrics for diurnal profile
    with open(os.path.join(CLEAN_DIR, "crisis_metrics.json"), "r", encoding="utf-8") as f:
        metrics = json.load(f)
    diurnal_list = [d.get("demand_multiplier", 1.0) for d in metrics.get("diurnal_profile", [])]
    if len(diurnal_list) != 24:
        diurnal_list = [0.35, 0.25, 0.20, 0.20, 0.30, 0.60, 1.10, 1.50, 1.50, 1.30, 1.20, 1.20,
                        1.20, 1.20, 1.20, 1.30, 1.50, 1.60, 1.40, 1.10, 0.90, 0.70, 0.55, 0.45]
    diurnal_weights = np.array(diurnal_list)
    diurnal_weights = diurnal_weights / (np.sum(diurnal_weights) / 24.0)

    # Simulation parameters
    # Start: 2026-10-16 03:00 WITA (Current time)
    start_dt_wita = datetime(2026, 10, 16, 3, 0, tzinfo=WITA_TZ)
    horizon_hours = 16 * 24  # 384 jam (16 hari)

    # Scenario allocation
    # A (Fast): 20% | B (Base): 50% | C (Prolonged): 15% | D (Panic Spike): 15%
    n_a = int(0.20 * n_paths)
    n_b = int(0.50 * n_paths)
    n_c = int(0.15 * n_paths)
    n_d = n_paths - (n_a + n_b + n_c)
    scenario_tags = ["A_Cepat"] * n_a + ["B_Bertahap_Base"] * n_b + ["C_Berkepanjangan"] * n_c + ["D_Panic_Spike"] * n_d

    # Total SPBU Pertamina & Storage Capacity
    total_spbu = 212
    tank_capacity_per_spbu = 24.0  # KL
    total_spbu_storage_cap = total_spbu * tank_capacity_per_spbu  # 5,088 KL

    # Current initial conditions (derived from current data ~52% stocked SPBU)
    current_avail_ratio = 1.0 - (metrics.get("latest_empty_spbu_pct", 48.0) / 100.0)
    init_spbu_stock = total_spbu_storage_cap * (current_avail_ratio * 0.70 + 0.15)
    init_term_stock = 4600.0  # KL di Sanggaran & Manggis gabungan

    print(f"[*] Running {n_paths:,} Monte Carlo simulation paths (Horizon: {horizon_hours} hours)...")

    # Arrays to hold trajectories
    # Shape: (N, horizon_hours)
    spbu_stock_paths = np.zeros((n_paths, horizon_hours), dtype=np.float32)
    spbu_avail_paths = np.zeros((n_paths, horizon_hours), dtype=np.float32)

    # Scheduled Ship arrivals relative to start (2026-10-16 03:00 WITA):
    # Call 3: 2026-10-16 10:00 WITA -> hour 7
    # Ship 4: 2026-10-18 10:00 WITA -> hour 55
    # Ship 5: 2026-10-20 10:00 WITA -> hour 103
    # Ship 6: 2026-10-22 10:00 WITA -> hour 151
    # Ship 7: 2026-10-25 10:00 WITA -> hour 223
    ship_nominal = [
        {"hour": 7, "volume": 6000.0},
        {"hour": 55, "volume": 5200.0},
        {"hour": 103, "volume": 5200.0},
        {"hour": 151, "volume": 5000.0},
        {"hour": 223, "volume": 5000.0}
    ]

    recovery_hours = np.full(n_paths, np.nan, dtype=np.float32)

    # Sensitivity tracker
    param_records = []

    for i in range(n_paths):
        scen = scenario_tags[i]

        # Sample parameters per scenario
        if scen == "A_Cepat":
            truck_cap_daily = np.random.normal(2950.0, 60.0)
            base_demand_daily = np.random.normal(2150.0, 50.0)
            panic_initial = np.random.uniform(1.05, 1.12)
            panic_decay_hours = np.random.uniform(24.0, 48.0)
            ship_delays = np.random.normal(0.0, 2.0, size=len(ship_nominal))  # tepat waktu
        elif scen == "B_Bertahap_Base":
            truck_cap_daily = np.random.normal(2700.0, 80.0)
            base_demand_daily = np.random.normal(2200.0, 60.0)
            panic_initial = np.random.uniform(1.12, 1.22)
            panic_decay_hours = np.random.uniform(48.0, 84.0)
            ship_delays = np.random.exponential(4.0, size=len(ship_nominal))  # rata-rata delay 4 jam
        elif scen == "C_Berkepanjangan":
            truck_cap_daily = np.random.normal(2380.0, 90.0)
            base_demand_daily = np.random.normal(2200.0, 60.0)
            panic_initial = np.random.uniform(1.15, 1.28)
            panic_decay_hours = np.random.uniform(72.0, 140.0)
            ship_delays = np.random.uniform(18.0, 52.0, size=len(ship_nominal))  # delay 1-2 hari
        else:  # D_Panic_Spike
            truck_cap_daily = np.random.normal(2700.0, 80.0)
            base_demand_daily = np.random.normal(2200.0, 60.0)
            panic_initial = np.random.uniform(1.28, 1.45)  # lonjakan panik parah
            panic_decay_hours = np.random.uniform(96.0, 168.0)
            ship_delays = np.random.normal(3.0, 5.0, size=len(ship_nominal))

        # Build hourly ship arrivals for this path
        inflow_hourly = np.zeros(horizon_hours, dtype=np.float32)
        for s_idx, s in enumerate(ship_nominal):
            actual_arr_h = int(np.clip(s["hour"] + ship_delays[s_idx], 0, horizon_hours - 1))
            # Pembongkaran memakan waktu 12 jam merata
            unload_hours = 12
            vol_per_h = s["volume"] / unload_hours
            for uh in range(actual_arr_h, min(horizon_hours, actual_arr_h + unload_hours)):
                inflow_hourly[uh] += vol_per_h

        # Run hourly timeline
        s_term = init_term_stock
        s_spbu = init_spbu_stock

        consecutive_healthy = 0
        recov_h = np.nan

        for h in range(horizon_hours):
            hr_of_day = (3 + h) % 24
            d_weight = diurnal_weights[hr_of_day]

            # Current panic multiplier
            p_mult = 1.0 + (panic_initial - 1.0) * np.exp(-h / panic_decay_hours)

            # Hourly demand
            hourly_demand = (base_demand_daily / 24.0) * d_weight * p_mult

            # Hourly trucking dispatch from terminal to SPBU
            # Truck capacity is capped by available terminal stock
            max_dispatch = (truck_cap_daily / 24.0) * (0.85 if hr_of_day in [1, 2, 3, 4] else 1.05)
            actual_dispatch = min(s_term, max_dispatch)

            # Terminal state update
            s_term = max(0.0, s_term + inflow_hourly[h] - actual_dispatch)

            # SPBU state update (inflow from trucks, outflow from consumption)
            spbu_inflow = actual_dispatch
            spbu_outflow = min(s_spbu + spbu_inflow, hourly_demand)
            s_spbu = float(np.clip(s_spbu + spbu_inflow - spbu_outflow, 0.0, total_spbu_storage_cap))

            # Stocked SPBU percentage function
            # Nonlinear logistic mapping: 0 KL -> 5%, 2,500 KL -> 50%, 4,500 KL -> 95%
            stock_ratio = s_spbu / total_spbu_storage_cap
            pct_avail = 1.0 / (1.0 + np.exp(-10.0 * (stock_ratio - 0.45)))
            pct_avail = float(np.clip(pct_avail, 0.05, 0.98))

            spbu_stock_paths[i, h] = s_spbu
            spbu_avail_paths[i, h] = pct_avail

            # Check criteria: pct_empty <= 10% (pct_avail >= 90%) sustained for 48 consecutive hours
            if pct_avail >= 0.90:
                consecutive_healthy += 1
                if consecutive_healthy >= 48 and np.isnan(recov_h):
                    recov_h = h - 47  # waktu saat mulai stabil
            else:
                consecutive_healthy = 0

        recovery_hours[i] = recov_h
        param_records.append({
            "scenario": scen,
            "truck_capacity": truck_cap_daily,
            "base_demand": base_demand_daily,
            "panic_initial": panic_initial,
            "ship_delay_mean": float(np.mean(ship_delays)),
            "recovery_hour": recov_h if not np.isnan(recov_h) else horizon_hours
        })

    # -------------------------------------------------------------
    # STATISTICAL DISTRIBUTIONS & CREDIBLE INTERVALS
    # -------------------------------------------------------------
    valid_recov = recovery_hours[~np.isnan(recovery_hours)]
    pct_recovered = float(len(valid_recov) / n_paths * 100.0)

    # Median & Credible intervals in hours
    median_h = float(np.median(valid_recov)) if len(valid_recov) > 0 else 72.0
    p25_h = float(np.percentile(valid_recov, 25))
    p75_h = float(np.percentile(valid_recov, 75))
    p10_h = float(np.percentile(valid_recov, 10))
    p90_h = float(np.percentile(valid_recov, 90))
    p025_h = float(np.percentile(valid_recov, 2.5))
    p975_h = float(np.percentile(valid_recov, 97.5))

    # Convert hours to Datetime in WITA
    def h_to_date_wita(h_val):
        dt = start_dt_wita + timedelta(hours=float(h_val))
        return dt.strftime("%Y-%m-%d %H:%M WITA")

    def h_to_day_wita(h_val):
        dt = start_dt_wita + timedelta(hours=float(h_val))
        return dt.strftime("%A, %d %B %Y")

    median_datetime = h_to_date_wita(median_h)
    median_day_str = h_to_day_wita(median_h)

    # Empirical CDF
    sorted_recov = np.sort(valid_recov)
    cdf_points = []
    quantiles = np.linspace(0.01, 0.99, 50)
    for q in quantiles:
        val_h = float(np.percentile(sorted_recov, q * 100.0))
        cdf_points.append({
            "probability": round(float(q), 3),
            "hours": round(val_h, 1),
            "datetime_wita": h_to_date_wita(val_h)
        })

    # Fan chart percentiles across 384 hours
    fan_p5 = np.percentile(spbu_avail_paths * 100.0, 5, axis=0).round(1).tolist()
    fan_p25 = np.percentile(spbu_avail_paths * 100.0, 25, axis=0).round(1).tolist()
    fan_p50 = np.percentile(spbu_avail_paths * 100.0, 50, axis=0).round(1).tolist()
    fan_p75 = np.percentile(spbu_avail_paths * 100.0, 75, axis=0).round(1).tolist()
    fan_p95 = np.percentile(spbu_avail_paths * 100.0, 95, axis=0).round(1).tolist()

    timeline_hours = list(range(horizon_hours))
    timeline_timestamps = [(start_dt_wita + timedelta(hours=h)).strftime("%d %b %H:00") for h in timeline_hours]

    # Scenario Breakdown
    df_params = pd.DataFrame(param_records)
    scenario_summary = {}
    for sc, grp in df_params.groupby("scenario"):
        rec_vals = grp["recovery_hour"].values
        scenario_summary[sc] = {
            "weight_pct": round(len(grp) / n_paths * 100.0, 1),
            "median_hours": round(float(np.median(rec_vals)), 1),
            "median_date_wita": h_to_date_wita(np.median(rec_vals)),
            "p10_hours": round(float(np.percentile(rec_vals, 10)), 1),
            "p90_hours": round(float(np.percentile(rec_vals, 90)), 1),
            "mean_truck_cap": round(float(grp["truck_capacity"].mean()), 0),
            "mean_panic": round(float(grp["panic_initial"].mean()), 2)
        }

    # Sensitivity Analysis (Pearson correlation with recovery hours)
    sensitivity = {
        "ship_delay": round(float(np.corrcoef(df_params["ship_delay_mean"], df_params["recovery_hour"])[0, 1]), 3),
        "truck_capacity": round(float(np.corrcoef(df_params["truck_capacity"], df_params["recovery_hour"])[0, 1]), 3),
        "panic_intensity": round(float(np.corrcoef(df_params["panic_initial"], df_params["recovery_hour"])[0, 1]), 3),
        "base_demand": round(float(np.corrcoef(df_params["base_demand"], df_params["recovery_hour"])[0, 1]), 3)
    }

    # Histogram of recovery dates
    day_counts = {}
    for h in valid_recov:
        dt = start_dt_wita + timedelta(hours=float(h))
        day_str = dt.strftime("%Y-%m-%d")
        day_counts[day_str] = day_counts.get(day_str, 0) + 1
    
    histogram_recovery_dates = [
        {"date": d, "count": day_counts[d], "percentage": round(day_counts[d] / n_paths * 100.0, 2)}
        for d in sorted(day_counts.keys())
    ]

    results = {
        "total_paths": n_paths,
        "criteria": "<10% SPBU kosong (>=90% SPBU ada stok) selama 48 jam berturut-turut",
        "start_datetime_wita": start_dt_wita.strftime("%Y-%m-%d %H:%M WITA"),
        "pct_paths_recovered": pct_recovered,
        "median_recovery_hours": round(median_h, 1),
        "median_recovery_datetime_wita": median_datetime,
        "median_recovery_day_indonesian": median_day_str,
        "credible_intervals": {
            "ci_50": {
                "hours_range": [round(p25_h, 1), round(p75_h, 1)],
                "date_range_wita": [h_to_date_wita(p25_h), h_to_date_wita(p75_h)]
            },
            "ci_80": {
                "hours_range": [round(p10_h, 1), round(p90_h, 1)],
                "date_range_wita": [h_to_date_wita(p10_h), h_to_date_wita(p90_h)]
            },
            "ci_95": {
                "hours_range": [round(p025_h, 1), round(p975_h, 1)],
                "date_range_wita": [h_to_date_wita(p025_h), h_to_date_wita(p975_h)]
            }
        },
        "scenarios": scenario_summary,
        "sensitivity": sensitivity,
        "histogram_recovery_dates": histogram_recovery_dates,
        "cumulative_distribution_function": cdf_points,
        "fan_chart": {
            "timestamps": timeline_timestamps,
            "p5": fan_p5,
            "p25": fan_p25,
            "p50": fan_p50,
            "p75": fan_p75,
            "p95": fan_p95
        }
    }

    out_file = os.path.join(CLEAN_DIR, "monte_carlo_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n[=== MONTE CARLO SIMULATION RESULTS (10,000 PATHS) ===]")
    print(f"Kriteria: {results['criteria']}")
    print(f"Median Pemulihan: {median_datetime} ({median_day_str}) [+{median_h:.1f} jam]")
    print(f"50% Credible Interval (P25 - P75): {results['credible_intervals']['ci_50']['date_range_wita'][0]} s/d {results['credible_intervals']['ci_50']['date_range_wita'][1]}")
    print(f"80% Credible Interval (P10 - P90): {results['credible_intervals']['ci_80']['date_range_wita'][0]} s/d {results['credible_intervals']['ci_80']['date_range_wita'][1]}")
    print(f"95% Credible Interval (P2.5 - P97.5): {results['credible_intervals']['ci_95']['date_range_wita'][0]} s/d {results['credible_intervals']['ci_95']['date_range_wita'][1]}")
    print("\nRingkasan Skenario:")
    for sc, info in scenario_summary.items():
        print(f"  * {sc:20}: Median = {info['median_date_wita']} (+{info['median_hours']}h) [Bobot {info['weight_pct']}%]")
    print("\nSensitivitas Parameter (Korelasi terhadap waktu pemulihan):")
    for k, v in sensitivity.items():
        print(f"  * {k:20}: {v:+0.3f}")

    return results


if __name__ == "__main__":
    run_monte_carlo_simulation()
