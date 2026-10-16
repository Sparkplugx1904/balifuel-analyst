"""
Benchmark Day-0 Evaluation Script: BaliFuel Analyst
Mengukur performa baseline model out-of-time untuk target T1 dan T3:
- Persistence Baseline
- Area Climatology Baseline
- Current Markov Engine (Hari-0)
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.markov_model import BaliFuelMarkovEngine

DB_PATH = os.path.join(BASE_DIR, "data", "balifuel.db")
CLEAN_DIR = os.path.join(BASE_DIR, "data", "clean")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


def compute_brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def compute_log_loss(y_true: np.ndarray, y_prob: np.ndarray, eps: float = 1e-6) -> float:
    p = np.clip(y_prob, eps, 1.0 - eps)
    return float(-np.mean(y_true * np.log(p) + (1.0 - y_true) * np.log(1.0 - p)))


def compute_roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    from scipy.stats import rankdata
    n_pos = np.sum(y_true == 1)
    n_neg = np.sum(y_true == 0)
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = rankdata(y_prob)
    rank_sum = np.sum(ranks[y_true == 1])
    u_stat = rank_sum - (n_pos * (n_pos + 1)) / 2.0
    return float(u_stat / (n_pos * n_neg))


def run_day0_benchmark() -> Dict[str, Any]:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # Load reports and sort chronologically
    df = pd.read_sql_query("SELECT * FROM driver_reports ORDER BY created_at_epoch ASC", conn)
    stations_df = pd.read_sql_query("SELECT * FROM stations_master", conn)
    conn.close()

    print(f"[*] Loaded {len(df)} reports across {len(stations_df)} stations.")

    # Chronological Out-of-Time Split (70% Train, 30% Test)
    split_idx = int(len(df) * 0.70)
    df_train = df.iloc[:split_idx].copy()
    df_test = df.iloc[split_idx:].copy()

    split_time = datetime.fromtimestamp(df_test["created_at_epoch"].min(), tz=WITA_TZ)
    print(f"[*] Train set: {len(df_train)} reports (< {split_time.strftime('%Y-%m-%d %H:%M WITA')})")
    print(f"[*] Test set : {len(df_test)} reports (>= {split_time.strftime('%Y-%m-%d %H:%M WITA')})")

    # Target: Ketersediaan (available == 1, empty == 0)
    y_test = df_test["available"].values.astype(float)

    # 1. Baseline 1: Persistence
    # Ambil status terakhir teramati pada stasiun tersebut dari df_train
    last_known = df_train.groupby("station_id")["available"].last().to_dict()
    global_mean_train = df_train["available"].mean()
    p_persistence = np.array([last_known.get(s_id, global_mean_train) for s_id in df_test["station_id"]])

    # 2. Baseline 2: Area Climatology
    st_area_map = stations_df.set_index("id")["area"].to_dict()
    df_train["area"] = df_train["station_id"].map(st_area_map)
    df_train["hour"] = pd.to_datetime(df_train["created_at_epoch"], unit="s").dt.tz_localize("UTC").dt.tz_convert(WITA_TZ).dt.hour
    area_climatology = df_train.groupby(["area", "hour"])["available"].mean().to_dict()

    df_test["area"] = df_test["station_id"].map(st_area_map)
    df_test["hour"] = pd.to_datetime(df_test["created_at_epoch"], unit="s").dt.tz_localize("UTC").dt.tz_convert(WITA_TZ).dt.hour
    p_climatology = np.array([area_climatology.get((a, h), global_mean_train) for a, h in zip(df_test["area"], df_test["hour"])])

    # 3. Model Hari-0: Markov Model
    with open(os.path.join(CLEAN_DIR, "cleaned_stations.json"), "r", encoding="utf-8") as f:
        stations_list = json.load(f)
    with open(os.path.join(BASE_DIR, "data", "external_context.json"), "r", encoding="utf-8") as f:
        ext_context = json.load(f)
    with open(os.path.join(CLEAN_DIR, "crisis_metrics.json"), "r", encoding="utf-8") as f:
        metrics = json.load(f)

    engine = BaliFuelMarkovEngine(stations_list, ext_context, metrics.get("diurnal_profile", []))
    st_dict = {s["id"]: s for s in stations_list}

    p_markov = []
    for s_id, h, cur_t in zip(df_test["station_id"], df_test["hour"], df_test["created_at_epoch"]):
        s_obj = st_dict.get(s_id)
        if s_obj is None:
            p_markov.append(global_mean_train)
            continue
        p0 = last_known.get(s_id, 0.50)
        # Transisi 1 langkah Markov
        P = engine.get_transition_matrix(s_obj, h, supply_multiplier=1.0, panic_factor=1.15)
        state_vec = np.array([1.0 - p0, p0]) @ P
        p_markov.append(float(state_vec[1]))
    p_markov = np.array(p_markov)

    # Evaluasi Metrik
    results = {
        "evaluation_timestamp_wita": datetime.now(WITA_TZ).strftime("%Y-%m-%d %H:%M:%S WITA"),
        "total_test_samples": len(y_test),
        "split_cutoff_epoch": int(df_test["created_at_epoch"].min()),
        "baselines": {
            "persistence": {
                "brier_score": round(compute_brier_score(y_test, p_persistence), 4),
                "log_loss": round(compute_log_loss(y_test, p_persistence), 4),
                "roc_auc": round(compute_roc_auc(y_test, p_persistence), 4)
            },
            "area_climatology": {
                "brier_score": round(compute_brier_score(y_test, p_climatology), 4),
                "log_loss": round(compute_log_loss(y_test, p_climatology), 4),
                "roc_auc": round(compute_roc_auc(y_test, p_climatology), 4)
            },
            "markov_day0": {
                "brier_score": round(compute_brier_score(y_test, p_markov), 4),
                "log_loss": round(compute_log_loss(y_test, p_markov), 4),
                "roc_auc": round(compute_roc_auc(y_test, p_markov), 4)
            }
        },
        "relative_gain_over_persistence_pct": round((compute_brier_score(y_test, p_persistence) - compute_brier_score(y_test, p_markov)) / compute_brier_score(y_test, p_persistence) * 100, 2),
        "relative_gain_over_climatology_pct": round((compute_brier_score(y_test, p_climatology) - compute_brier_score(y_test, p_markov)) / compute_brier_score(y_test, p_climatology) * 100, 2)
    }

    out_file = os.path.join(OUTPUT_DIR, "day0_benchmark.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print(" DAY-0 BASELINE BENCHMARK RESULTS (OUT-OF-TIME EVALUATION)")
    print("=" * 60)
    for model_name, m in results["baselines"].items():
        print(f" {model_name:18}: Brier={m['brier_score']:.4f} | ROC-AUC={m['roc_auc']:.4f} | Log-Loss={m['log_loss']:.4f}")
    print(f"\n Relative Brier Gain Markov vs Persistence : +{results['relative_gain_over_persistence_pct']}%")
    print(f" Relative Brier Gain Markov vs Climatology : +{results['relative_gain_over_climatology_pct']}%")
    print("=" * 60)
    return results


if __name__ == "__main__":
    run_day0_benchmark()
