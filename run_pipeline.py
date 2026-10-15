"""
Master Pipeline Runner: Bali Fuel Crisis Analyst System
Menjalankan seluruh siklus sistem end-to-end dengan satu perintah:
1. Koleksi data mentah & snapshot time series (SQLite & raw JSON)
2. Pembersihan data, pembobotan eksponensial, & imputasi spasial
3. Kalkulasi metrik keparahan (CSI) & analisis 14 area
4. Pemodelan Markov, Kaplan-Meier, & backtest komparatif
5. Simulasi Monte Carlo 10.000 jalur & distribusi waktu pemulihan
6. Proyeksi stok & antrean 72 jam per SPBU + hotspot ranking
7. Pembuatan grafik SVG mandiri per SPBU di output/spbu/
8. Perakitan dashboard interaktif mandiri di output/dashboard.html
"""

import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def run_all(spbu_chart_limit: int = 50):
    t_start = time.time()
    print("=" * 70)
    print(" BALI FUEL CRISIS ANALYST — END-TO-END SYSTEM RUNNER")
    print("=" * 70)

    # 1. Collector
    print("\n[PHASE 1/8] Running Data Collection & History Bootstrap...")
    from src.collector import collect_snapshot
    res_collect = collect_snapshot()
    print(f"-> Collection finished: {res_collect.get('collected', {})}")

    # 2. Cleaner
    print("\n[PHASE 2/8] Running Data Cleaning, Weighting & Spatial Imputation...")
    from src.cleaner import clean_and_enrich_data
    res_clean = clean_and_enrich_data()
    print(f"-> Cleaning finished: {res_clean.get('total_stations')} stations processed.")

    # 3. Metrics
    print("\n[PHASE 3/8] Computing Crisis Severity Index & 14 Area Metrics...")
    from src.metrics import compute_crisis_metrics
    res_metrics = compute_crisis_metrics()
    print(f"-> Current Island CSI: {res_metrics.get('current_island_csi')} ({res_metrics.get('current_status')})")

    # 4. Markov & Survival
    print("\n[PHASE 4/8] Fitting Markov Chain & Kaplan-Meier Survival Analysis...")
    from src.markov_model import run_markov_pipeline
    res_markov = run_markov_pipeline()
    winner = res_markov.get("model_comparison", {}).get("best_model", "Markov")
    print(f"-> Model Comparison Winner: {winner}")

    # 5. Monte Carlo Simulation
    print("\n[PHASE 5/8] Running 10,000 Monte Carlo Simulation Paths...")
    from src.simulation import run_monte_carlo_simulation
    res_sim = run_monte_carlo_simulation(n_paths=10000, random_seed=42)
    print(f"-> Median Recovery: {res_sim.get('median_recovery_datetime_wita')} (+{res_sim.get('median_recovery_hours')}h)")

    # 6. Forecasting & Hotspots
    print("\n[PHASE 6/8] Generating 72-Hour Per-SPBU Forecasts & Hotspot Rankings...")
    from src.forecast import generate_station_forecasts
    res_fc = generate_station_forecasts()
    print(f"-> Forecast generated for {res_fc.get('total_stations')} stations.")

    # 7. Visualizer
    print(f"\n[PHASE 7/8] Generating Standalone SPBU Visual Charts (Top {spbu_chart_limit} + Hotspots)...")
    from src.visualizer import generate_spbu_charts
    gen_cnt = generate_spbu_charts(limit=spbu_chart_limit, format_ext="svg")
    print(f"-> Generated {gen_cnt} SVG charts in output/spbu/.")

    # 8. Dashboard Builder
    print("\n[PHASE 8/8] Building Standalone Interactive HTML Dashboard...")
    from src.dashboard_builder import build_dashboard
    dash_path = build_dashboard()
    print(f"-> Dashboard ready at: {dash_path}")

    elapsed = time.time() - t_start
    print("\n" + "=" * 70)
    print(f" ALL PHASES COMPLETED SUCCESSFULLY IN {elapsed:.2f} SECONDS!")
    print(f" Dashboard: {os.path.join(BASE_DIR, 'output', 'dashboard.html')}")
    print(f" Full Report: {os.path.join(BASE_DIR, 'output', 'laporan.md')}")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Master Runner for Bali Fuel Crisis Analyst")
    parser.add_argument("--all-charts", action="store_true", help="Generate SVG charts for all 232 priority SPBU")
    args = parser.parse_args()

    limit = None if args.all_charts else 50
    run_all(spbu_chart_limit=limit)
