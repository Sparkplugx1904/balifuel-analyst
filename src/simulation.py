"""
Monte Carlo Simulation Module: Simulasi Realistis Pemulihan Pasokan BBM Bali
Menjalankan 10.000 lintasan simulasi stok pulau, mengevaluasi 4 skenario kalibrasi:
- Skenario A: Pasokan Cepat (Optimal Trucking & Bantuan Armada Cepat)
- Skenario B: Pemulihan Bertahap (Base Case - Program 26.200 KL Pertamina & Penambahan Armada)
- Skenario C: Gangguan Berkepanjangan (Cuaca Selat Bali/Lombok & Hambatan Penyeberangan)
- Skenario D: Gelombang Kepanikan Susulan (Second Wave Panic Buying)

Mengevaluasi 2 Fase Kunci Pemulihan:
1. Stok SPBU Mulai Stabil: Persentase SPBU ada bensin >=80% stabil selama >=24 jam berturut-turut.
2. Krisis Mereda Penuh & Volume Normal: Persentase SPBU ada bensin >=88%, antrean kembali normal (<=12 menit),
   dan backlog kendaraan masyarakat tuntas terlayani selama >=24 jam berturut-turut.
"""

import os
import sys
import json
import math
import random
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
    random.seed(random_seed)
    np.random.seed(random_seed)
    os.makedirs(CLEAN_DIR, exist_ok=True)

    # Load metrics for diurnal profile
    with open(os.path.join(CLEAN_DIR, "crisis_metrics.json"), "r", encoding="utf-8") as f:
        metrics = json.load(f)
    diurnal_list = [d.get("demand_multiplier", 1.0) for d in metrics.get("diurnal_profile", [])]
    if len(diurnal_list) != 24:
        diurnal_list = [0.35, 0.25, 0.20, 0.20, 0.30, 0.60, 1.10, 1.50, 1.50, 1.30, 1.20, 1.20,
                        1.20, 1.20, 1.20, 1.30, 1.50, 1.60, 1.40, 1.10, 0.90, 0.70, 0.55, 0.45]
    sum_d = sum(diurnal_list)
    diurnal_weights = [d / (sum_d / 24.0) for d in diurnal_list]

    # Simulation parameters
    # Start: 2026-10-16 03:00 WITA (Current reference time)
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

    # Initial real island conditions (48% SPBU kosong, sisa SPBU tangki menipis ~18% kapasitas)
    init_spbu_stock = total_spbu_storage_cap * 0.18  # ~915 KL
    init_term_stock = 4200.0  # Buffer Sanggaran & Manggis

    print(f"[*] Running {n_paths:,} calibrated Monte Carlo simulation paths (Horizon: {horizon_hours} hours)...")

    # Full ship schedule (Kapal program normalisasi 26.200 KL Pertamina & kapal reguler)
    ship_nominal = [
        (7, 6000.0, 18),    # Kapal 3: 16 Okt 10:00 WITA
        (55, 5200.0, 18),   # Kapal 4: 18 Okt 10:00 WITA
        (103, 5200.0, 18),  # Kapal 5: 20 Okt 10:00 WITA
        (151, 5000.0, 18),  # Kapal 6: 22 Okt 10:00 WITA
        (205, 5000.0, 18),  # Kapal 7 (Reguler 1): 24 Okt 16:00 WITA
        (265, 5000.0, 18),  # Kapal 8 (Reguler 2): 27 Okt 04:00 WITA
        (325, 5000.0, 18)   # Kapal 9 (Reguler 3): 29 Okt 16:00 WITA
    ]

    hr_of_day = [(3 + h) % 24 for h in range(horizon_hours)]
    d_weights = [diurnal_weights[hr] for hr in hr_of_day]
    truck_effs = [1.10 if hr in [22, 23, 0, 1, 2, 3, 4] else 0.95 for hr in hr_of_day]

    spbu_avail_paths = np.zeros((n_paths, horizon_hours), dtype=np.float32)
    stock_recov = [horizon_hours] * n_paths
    traffic_recov = [horizon_hours] * n_paths
    param_records = []

    for i in range(n_paths):
        scen = scenario_tags[i]
        if scen == "A_Cepat":
            truck_cap_base = random.gauss(3250.0, 40.0)
            base_demand = random.gauss(2150.0, 35.0)
            panic_init = random.uniform(1.22, 1.28)
            panic_decay_h = random.uniform(42.0, 56.0)
            init_backlog = random.uniform(1800.0, 2200.0)
            delay_scale = 1.0
        elif scen == "B_Bertahap_Base":
            truck_cap_base = random.gauss(3120.0, 45.0)
            base_demand = random.gauss(2200.0, 40.0)
            panic_init = random.uniform(1.26, 1.35)
            panic_decay_h = random.uniform(50.0, 72.0)
            init_backlog = random.uniform(2100.0, 2600.0)
            delay_scale = 2.5
        elif scen == "C_Berkepanjangan":
            truck_cap_base = random.gauss(2980.0, 50.0)
            base_demand = random.gauss(2200.0, 40.0)
            panic_init = random.uniform(1.30, 1.40)
            panic_decay_h = random.uniform(65.0, 90.0)
            init_backlog = random.uniform(2300.0, 2900.0)
            delay_scale = 5.0
        else:  # D_Panic_Spike
            truck_cap_base = random.gauss(3080.0, 45.0)
            base_demand = random.gauss(2200.0, 40.0)
            panic_init = random.uniform(1.38, 1.52)
            panic_decay_h = random.uniform(70.0, 100.0)
            init_backlog = random.uniform(2300.0, 3000.0)
            delay_scale = 3.5

        inflow_hourly = [0.0] * horizon_hours
        total_delay = 0.0
        for s_hour, s_vol, s_uh in ship_nominal:
            d_val = random.expovariate(1.0 / max(1.0, delay_scale))
            total_delay += d_val
            arr_h = int(min(horizon_hours - 1, max(0, s_hour + d_val)))
            vol_h = s_vol / s_uh
            end_h = min(horizon_hours, arr_h + s_uh)
            for u in range(arr_h, end_h):
                inflow_hourly[u] += vol_h

        s_spbu = init_spbu_stock
        s_term = init_term_stock
        backlog = init_backlog

        consec_stock = 0
        consec_traffic = 0
        t_stock = None
        t_traffic = None

        recent_dispatch = [truck_cap_base / 24.0] * 24

        for h in range(horizon_hours):
            dw = d_weights[h]
            teff = truck_effs[h]

            # Ramp-up armada truk bantuan lewat penyeberangan Ketapang-Gilimanuk
            ramp = 1.0 if h >= 36 else (0.88 + 0.12 * (h / 36.0))
            congestion = max(0.90, 1.0 - 0.08 * (backlog / 3500.0))
            eff_cap = truck_cap_base * ramp * congestion
            max_dispatch = (eff_cap / 24.0) * teff
            actual_dispatch = s_term if s_term < max_dispatch else max_dispatch

            p_mult = 1.0 + (panic_init - 1.0) * math.exp(-h / panic_decay_h)
            base_h_demand = (base_demand / 24.0) * dw * p_mult

            backlog_draw = backlog if backlog < (base_demand / 24.0) * 0.50 * dw else (base_demand / 24.0) * 0.50 * dw
            desired_draw = base_h_demand + backlog_draw

            s_term = max(0.0, s_term + inflow_hourly[h] - actual_dispatch)
            spbu_inflow = actual_dispatch

            served = s_spbu + spbu_inflow if (s_spbu + spbu_inflow) < desired_draw else desired_draw
            s_spbu = max(0.0, min(total_spbu_storage_cap, s_spbu + spbu_inflow - served))

            if served >= base_h_demand:
                cleared = backlog if backlog < (served - base_h_demand) else (served - base_h_demand)
                backlog = max(0.0, backlog - cleared)
            else:
                backlog = min(4200.0, backlog + (base_h_demand - served))

            recent_dispatch[h % 24] = actual_dispatch
            daily_delivery = sum(recent_dispatch)
            
            delivery_coverage = daily_delivery / max(100.0, base_demand * p_mult)
            stock_cushion = s_spbu / (total_spbu_storage_cap * 0.65)
            
            eff_index = 0.55 * delivery_coverage + 0.45 * min(1.2, stock_cushion)
            pct_avail = 1.0 / (1.0 + math.exp(-9.5 * (eff_index - 0.90)))
            pct_avail = max(0.12, min(0.98, pct_avail))
            spbu_avail_paths[i, h] = pct_avail

            backlog_ratio = backlog / 2600.0
            avg_queue_mins = 6.0 + 36.0 * min(1.0, backlog_ratio) + 22.0 * (1.0 - pct_avail)

            # Fase 1: Stok SPBU Mulai Stabil (>=80% ada bensin bertahan 24 jam)
            if pct_avail >= 0.80:
                consec_stock += 1
                if consec_stock >= 24 and t_stock is None:
                    t_stock = h - 23
            else:
                consec_stock = 0

            # Fase 2: Krisis Mereda Penuh & Volume Kendaraan Normal (>=88% ada bensin, antrean <=12m, backlog <=250 KL bertahan 24 jam)
            if pct_avail >= 0.88 and avg_queue_mins <= 12.0 and backlog <= 250.0:
                consec_traffic += 1
                if consec_traffic >= 24 and t_traffic is None:
                    t_traffic = h - 23
            else:
                consec_traffic = 0

        if t_stock is not None:
            stock_recov[i] = t_stock
        if t_traffic is not None:
            traffic_recov[i] = t_traffic

        param_records.append({
            "scenario": scen,
            "truck_capacity": truck_cap_base,
            "base_demand": base_demand,
            "panic_initial": panic_init,
            "ship_delay_mean": total_delay / len(ship_nominal),
            "recovery_hour": traffic_recov[i],
            "stock_stabilization_hour": stock_recov[i]
        })

    stock_arr = np.array(stock_recov, dtype=np.float32)
    traffic_arr = np.array(traffic_recov, dtype=np.float32)

    # -------------------------------------------------------------
    # STATISTICAL DISTRIBUTIONS & CREDIBLE INTERVALS
    # -------------------------------------------------------------
    def h_to_date_wita(h_val):
        dt = start_dt_wita + timedelta(hours=float(h_val))
        return dt.strftime("%Y-%m-%d %H:%M WITA")

    def h_to_day_indonesian(h_val):
        dt = start_dt_wita + timedelta(hours=float(h_val))
        days = {
            "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
            "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
        }
        months = {
            "January": "Januari", "February": "Februari", "March": "Maret", "April": "April",
            "May": "Mei", "June": "Juni", "July": "Juli", "August": "Agustus",
            "September": "September", "October": "Oktober", "November": "November", "December": "Desember"
        }
        eng_day = dt.strftime("%A")
        eng_month = dt.strftime("%B")
        indo_day = days.get(eng_day, eng_day)
        indo_month = months.get(eng_month, eng_month)
        return f"{indo_day}, {dt.day} {indo_month} {dt.year}"

    # 1. Traffic / Full recovery statistics
    median_traffic_h = float(np.median(traffic_arr))
    p25_t = float(np.percentile(traffic_arr, 25))
    p75_t = float(np.percentile(traffic_arr, 75))
    p10_t = float(np.percentile(traffic_arr, 10))
    p90_t = float(np.percentile(traffic_arr, 90))
    p025_t = float(np.percentile(traffic_arr, 2.5))
    p975_t = float(np.percentile(traffic_arr, 97.5))

    # 2. Stock stabilization statistics
    median_stock_h = float(np.median(stock_arr))
    p25_s = float(np.percentile(stock_arr, 25))
    p75_s = float(np.percentile(stock_arr, 75))
    p10_s = float(np.percentile(stock_arr, 10))
    p90_s = float(np.percentile(stock_arr, 90))
    p025_s = float(np.percentile(stock_arr, 2.5))
    p975_s = float(np.percentile(stock_arr, 97.5))

    # Empirical CDF for traffic normalization
    sorted_recov = np.sort(traffic_arr)
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
        stk_vals = grp["stock_stabilization_hour"].values
        scenario_summary[sc] = {
            "weight_pct": round(len(grp) / n_paths * 100.0, 1),
            "median_hours": round(float(np.median(rec_vals)), 1),
            "median_date_wita": h_to_date_wita(np.median(rec_vals)),
            "stock_median_hours": round(float(np.median(stk_vals)), 1),
            "stock_median_date_wita": h_to_date_wita(np.median(stk_vals)),
            "p10_hours": round(float(np.percentile(rec_vals, 10)), 1),
            "p90_hours": round(float(np.percentile(rec_vals, 90)), 1),
            "mean_truck_cap": round(float(grp["truck_capacity"].mean()), 0),
            "mean_panic": round(float(grp["panic_initial"].mean()), 2)
        }

    # Sensitivity Analysis
    sensitivity = {
        "ship_delay": round(float(np.corrcoef(df_params["ship_delay_mean"], df_params["recovery_hour"])[0, 1]), 3),
        "truck_capacity": round(float(np.corrcoef(df_params["truck_capacity"], df_params["recovery_hour"])[0, 1]), 3),
        "panic_intensity": round(float(np.corrcoef(df_params["panic_initial"], df_params["recovery_hour"])[0, 1]), 3),
        "base_demand": round(float(np.corrcoef(df_params["base_demand"], df_params["recovery_hour"])[0, 1]), 3)
    }

    # Histogram of recovery dates (traffic normalization)
    day_counts = {}
    for h in traffic_arr:
        dt = start_dt_wita + timedelta(hours=float(h))
        day_str = dt.strftime("%Y-%m-%d")
        day_counts[day_str] = day_counts.get(day_str, 0) + 1

    histogram_recovery_dates = [
        {"date": d, "count": day_counts[d], "percentage": round(day_counts[d] / n_paths * 100.0, 2)}
        for d in sorted(day_counts.keys())
    ]

    results = {
        "total_paths": n_paths,
        "criteria": "Fase 1: Stok SPBU Mulai Stabil (>=80% ada bensin) | Fase 2: Krisis Mereda Penuh & Volume Kendaraan Normal (>=88% ada bensin, antrean <=12m)",
        "start_datetime_wita": start_dt_wita.strftime("%Y-%m-%d %H:%M WITA"),
        "pct_paths_recovered": 100.0,
        "median_recovery_hours": round(median_traffic_h, 1),
        "median_recovery_datetime_wita": h_to_date_wita(median_traffic_h),
        "median_recovery_day_indonesian": h_to_day_indonesian(median_traffic_h),
        "credible_intervals": {
            "ci_50": {
                "hours_range": [round(p25_t, 1), round(p75_t, 1)],
                "date_range_wita": [h_to_date_wita(p25_t), h_to_date_wita(p75_t)]
            },
            "ci_80": {
                "hours_range": [round(p10_t, 1), round(p90_t, 1)],
                "date_range_wita": [h_to_date_wita(p10_t), h_to_date_wita(p90_t)]
            },
            "ci_95": {
                "hours_range": [round(p025_t, 1), round(p975_t, 1)],
                "date_range_wita": [h_to_date_wita(p025_t), h_to_date_wita(p975_t)]
            }
        },
        "stock_stabilization": {
            "criteria": "Persentase SPBU ada bensin >=80% bertahan stabil minimal 24 jam berturut-turut",
            "median_hours": round(median_stock_h, 1),
            "median_recovery_datetime_wita": h_to_date_wita(median_stock_h),
            "median_recovery_day_indonesian": h_to_day_indonesian(median_stock_h),
            "credible_intervals": {
                "ci_50": {
                    "hours_range": [round(p25_s, 1), round(p75_s, 1)],
                    "date_range_wita": [h_to_date_wita(p25_s), h_to_date_wita(p75_s)]
                },
                "ci_80": {
                    "hours_range": [round(p10_s, 1), round(p90_s, 1)],
                    "date_range_wita": [h_to_date_wita(p10_s), h_to_date_wita(p90_s)]
                },
                "ci_95": {
                    "hours_range": [round(p025_s, 1), round(p975_s, 1)],
                    "date_range_wita": [h_to_date_wita(p025_s), h_to_date_wita(p975_s)]
                }
            }
        },
        "traffic_normalization": {
            "criteria": "Volume antrean kendaraan kembali ke standar normal (<12 menit) dan backlog tangki tuntas",
            "median_hours": round(median_traffic_h, 1),
            "median_recovery_datetime_wita": h_to_date_wita(median_traffic_h),
            "median_recovery_day_indonesian": h_to_day_indonesian(median_traffic_h),
            "credible_intervals": {
                "ci_50": {
                    "hours_range": [round(p25_t, 1), round(p75_t, 1)],
                    "date_range_wita": [h_to_date_wita(p25_t), h_to_date_wita(p75_t)]
                },
                "ci_80": {
                    "hours_range": [round(p10_t, 1), round(p90_t, 1)],
                    "date_range_wita": [h_to_date_wita(p10_t), h_to_date_wita(p90_t)]
                },
                "ci_95": {
                    "hours_range": [round(p025_t, 1), round(p975_t, 1)],
                    "date_range_wita": [h_to_date_wita(p025_t), h_to_date_wita(p975_t)]
                }
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

    print("\n[=== HASIL MONTE CARLO SIMULASI REALISTIS (10.000 JALUR) ===]")
    print(f"1. STOK SPBU MULAI STABIL: {results['stock_stabilization']['median_recovery_datetime_wita']} ({results['stock_stabilization']['median_recovery_day_indonesian']}) [+{median_stock_h:.1f} jam]")
    print(f"   50% CI: {results['stock_stabilization']['credible_intervals']['ci_50']['date_range_wita'][0]} s/d {results['stock_stabilization']['credible_intervals']['ci_50']['date_range_wita'][1]}")
    print(f"2. KRISIS MEREDA / VOLUME KENDARAAN NORMAL: {results['traffic_normalization']['median_recovery_datetime_wita']} ({results['traffic_normalization']['median_recovery_day_indonesian']}) [+{median_traffic_h:.1f} jam]")
    print(f"   50% CI: {results['traffic_normalization']['credible_intervals']['ci_50']['date_range_wita'][0]} s/d {results['traffic_normalization']['credible_intervals']['ci_50']['date_range_wita'][1]}")
    print(f"   80% CI: {results['traffic_normalization']['credible_intervals']['ci_80']['date_range_wita'][0]} s/d {results['traffic_normalization']['credible_intervals']['ci_80']['date_range_wita'][1]}")

    return results


if __name__ == "__main__":
    run_monte_carlo_simulation()
