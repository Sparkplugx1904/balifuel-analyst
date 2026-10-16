"""
Master Pipeline Runner: Bali Fuel Crisis Analyst System
Menjalankan siklus analisis end-to-end dengan dukungan mode lokal dan publikasi:
- Mode Lokal: menjalankan seluruh modul analisis, menghasilkan output/dashboard.html
- Mode Publikasi (--publish / --dry-run): membundel 4 kontrak data & mengunggah ke Cloudflare Worker
- Manajemen State: --restore-state (unduh DB dari R2) dan --save-state (kompaksi & unggah DB ke R2)
- Target Eksekusi: < 5 menit per run, seed deterministik dari run_id, log durasi tiap fase.
"""

import os
import sys
import time
import json
import hashlib
import argparse
from datetime import datetime, timezone, timedelta

WITA_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")


def should_refit_markov(max_age_hours: float = 6.0) -> bool:
    """Cek apakah model Markov perlu di-fit ulang (default setiap 6 jam)."""
    markov_cache_file = os.path.join(CLEAN_DIR, "markov_and_survival_analysis.json")
    if not os.path.exists(markov_cache_file):
        return True
    mtime = os.path.getmtime(markov_cache_file)
    age_hours = (time.time() - mtime) / 3600.0
    return age_hours >= max_age_hours


def run_pipeline(
    publish: bool = False,
    dry_run: bool = False,
    all_charts: bool = False,
    worker_url: str = None,
    token: str = None,
    spbu_chart_limit: int = 50,
    force_markov_refit: bool = False
):
    total_start = time.time()
    from src.publish import generate_run_id
    run_id = generate_run_id()

    # Seed diturunkan dari run_id
    seed = int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16) % 1_000_000

    print("=" * 72)
    print(f" BALI FUEL CRISIS ANALYST // PIPELINE RUNNER")
    print(f" Run ID : {run_id}")
    print(f" Seed   : {seed}")
    print(f" Mode   : {'PUBLISH' if publish else ('DRY-RUN' if dry_run else 'LOCAL')}")
    print("=" * 72)

    phase_timings = {}

    # -------------------------------------------------------------
    # FASE 1: KOLEKSI DATA (SNAPSHOT, HISTORY & 6 COLLECTORS MANDIRI)
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 1/7] Running Data Collection & History Bootstrap...")
    from src.collector import collect_snapshot
    res_collect = collect_snapshot()
    
    # Jalankan 6 collector mandiri (Marine weather, OSRM routing, News RSS, Calendar, Macro, OSM)
    try:
        from src.collectors.collector_manager import run_all_collectors
        run_all_collectors()
    except Exception as coll_err:
        print(f"-> Collectors warning (degraded): {coll_err}")

    phase_timings["1_collector"] = round(time.time() - t0, 2)
    print(f"-> Phase 1 completed in {phase_timings['1_collector']}s (Reports: {res_collect.get('collected', {}).get('reports_count')})")
    # -------------------------------------------------------------
    # FASE 2: PEMBERSIHAN DATA & IMPUTASI SPASIAL
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 2/7] Running Data Cleaning, Weighting & Spatial Imputation...")
    from src.cleaner import clean_and_enrich_data
    res_clean = clean_and_enrich_data()
    phase_timings["2_cleaner"] = round(time.time() - t0, 2)
    print(f"-> Phase 2 completed in {phase_timings['2_cleaner']}s ({res_clean.get('total_stations')} stations)")

    # -------------------------------------------------------------
    # FASE 3: METRIK KEPARAHAN & 14 AREA MAKRO
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 3/7] Computing Crisis Severity Index & 14 Area Metrics...")
    from src.metrics import compute_crisis_metrics
    res_metrics = compute_crisis_metrics()

    # Rekayasa Fitur Spasial-Temporal (32 Fitur)
    try:
        from src.feature_engineering import build_feature_matrix
        build_feature_matrix()
    except Exception as feat_err:
        print(f"-> Feature engineering warning: {feat_err}")

    phase_timings["3_metrics"] = round(time.time() - t0, 2)
    print(f"-> Phase 3 completed in {phase_timings['3_metrics']}s (Island CSI: {res_metrics.get('current_island_csi')})")

    # -------------------------------------------------------------
    # FASE 4: KECERDASAN NON-ANGKA & PROSES TEKS PUBLIK (SAH)
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 4/9] Processing Non-Numeric Public Text & Claims Ledger...")
    try:
        from src.text_nlp import process_all_text_sources, validate_nlp_models
        validate_nlp_models()
        res_text = process_all_text_sources()
        phase_timings["4_text_nlp"] = round(time.time() - t0, 2)
        print(f"-> Phase 4 completed in {phase_timings['4_text_nlp']}s (Signals: {res_text.get('signals_count')})")
    except Exception as text_err:
        phase_timings["4_text_nlp"] = round(time.time() - t0, 2)
        print(f"-> Text intelligence warning (degraded): {text_err}")

    # -------------------------------------------------------------
    # FASE 5: PEMODELAN MARKOV & SURVIVAL (SETIAP 6 JAM)
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 5/9] Checking Markov Chain & Survival Analysis Cache...")
    if force_markov_refit or should_refit_markov(max_age_hours=6.0):
        print("-> Running full Markov fitting & backtest (Cache expired > 6 hours)...")
        from src.markov_model import run_markov_pipeline
        res_markov = run_markov_pipeline()
        winner = res_markov.get("model_comparison", {}).get("best_model", "Markov")
        phase_timings["5_markov"] = round(time.time() - t0, 2)
        print(f"-> Phase 5 refit completed in {phase_timings['5_markov']}s (Model: {winner})")
    else:
        phase_timings["5_markov"] = round(time.time() - t0, 2)
        print(f"-> Reusing cached Markov model (< 6h old). Phase 5 skipped in {phase_timings['5_markov']}s.")

    # -------------------------------------------------------------
    # FASE 6: SIMULASI MONTE CARLO (10.000 JALUR)
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 6/9] Running 10,000 Monte Carlo Simulation Paths...")
    from src.simulation import run_monte_carlo_simulation
    res_sim = run_monte_carlo_simulation(n_paths=10000, random_seed=seed)
    phase_timings["6_simulation"] = round(time.time() - t0, 2)
    print(f"-> Phase 6 completed in {phase_timings['6_simulation']}s (Median: {res_sim.get('median_recovery_datetime_wita')})")

    # -------------------------------------------------------------
    # FASE 7: PROYEKSI 72 JAM PER SPBU & HOTSPOT RANKING
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 7/9] Generating 72-Hour Per-SPBU Forecasts & Hotspot Rankings...")
    from src.forecast import generate_station_forecasts
    res_fc = generate_station_forecasts(horizon_hours=72)
    phase_timings["7_forecast"] = round(time.time() - t0, 2)
    print(f"-> Phase 7 completed in {phase_timings['7_forecast']}s ({res_fc.get('total_stations')} stations)")

    # -------------------------------------------------------------
    # FASE 8: GERBANG AKURASI (G1-G5) & AUDIT KONSISTENSI DATA
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 8/9] Evaluating Accuracy Gates (G1-G5) & Data Consistency...")
    from src.accuracy_gates import evaluate_accuracy_gates
    from src.consistency import check_data_consistency, generate_prediction_scorecard
    res_gates = evaluate_accuracy_gates()
    generate_prediction_scorecard()
    res_cons = check_data_consistency()
    phase_timings["8_consistency"] = round(time.time() - t0, 2)
    print(f"-> Phase 8 completed in {phase_timings['8_consistency']}s (Keyakinan: {res_gates.get('status_keyakinan')})")

    if res_cons.get("status") != "PASSED":
        print(f" [!] CRITICAL: Consistency check failed: {res_cons.get('issues_found')}")
        if publish:
            raise RuntimeError(f"Publish cancelled due to consistency failure: {res_cons.get('issues_found')}")

    # -------------------------------------------------------------
    # FASE 9: PUBLIKASI KONTRAK ATAU BUILD DASHBOARD LOKAL
    # -------------------------------------------------------------
    t0 = time.time()
    print("\n[PHASE 9/9] Output Generation & Publishing...")
    if publish or dry_run:
        from src.publish import publish_pipeline_artifacts
        w_url = worker_url or os.getenv("WORKER_URL", "http://127.0.0.1:8787")
        tok = token or os.getenv("INGEST_TOKEN", "")
        pub_res = publish_pipeline_artifacts(worker_url=w_url, token=tok, dry_run=dry_run, run_id=run_id)
        phase_timings["7_publish"] = round(time.time() - t0, 2)
        print(f"-> Publication completed in {phase_timings['7_publish']}s. Sizes: {pub_res.get('sizes')}")
    else:
        # Local mode: build dashboard and optionally SVG charts
        if all_charts:
            from src.visualizer import generate_spbu_charts
            gen_cnt = generate_spbu_charts(limit=None, format_ext="svg")
            print(f"-> Generated {gen_cnt} SVG charts in output/spbu/.")
        elif spbu_chart_limit > 0:
            from src.visualizer import generate_spbu_charts
            gen_cnt = generate_spbu_charts(limit=spbu_chart_limit, format_ext="svg")
            print(f"-> Generated {gen_cnt} SVG charts in output/spbu/.")

        from src.dashboard_builder import build_dashboard
        dash_path = build_dashboard(target="local")
        phase_timings["7_publish"] = round(time.time() - t0, 2)
        print(f"-> Local dashboard ready at: {dash_path}")

    total_elapsed = round(time.time() - total_start, 2)
    print("\n" + "=" * 72)
    print(f" PIPELINE FINISHED IN {total_elapsed}s (Target < 300s: {'PASSED' if total_elapsed < 300 else 'SLOW'})")
    print(" Durasi Tiap Fase:")
    for ph, dur in phase_timings.items():
        print(f"   * {ph:15}: {dur:6.2f}s")
    print("=" * 72)

    return {
        "run_id": run_id,
        "seed": seed,
        "total_seconds": total_elapsed,
        "phase_timings": phase_timings
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Master Pipeline Runner for Bali Fuel Crisis Analyst")
    parser.add_argument("--publish", action="store_true", help="Publish 4 contract files to Cloudflare Worker ingest API")
    parser.add_argument("--dry-run", action="store_true", help="Bundle and validate 4 contracts into ./publish_out without uploading")
    parser.add_argument("--worker-url", type=str, default=None, help="Cloudflare Worker URL")
    parser.add_argument("--token", type=str, default=None, help="Ingest Bearer Token")
    parser.add_argument("--all-charts", action="store_true", help="Generate SVG charts for all 232 priority SPBU (local only)")
    parser.add_argument("--spbu-limit", type=int, default=20, help="SPBU chart count limit for local mode (default: 20)")
    parser.add_argument("--force-markov", action="store_true", help="Force refit of Markov model regardless of cache")
    parser.add_argument("--restore-state", action="store_true", help="Download state/balifuel.db from Cloudflare Worker")
    parser.add_argument("--save-state", action="store_true", help="Compact and upload state/balifuel.db to Cloudflare Worker")
    parser.add_argument("--loop", action="store_true", help="Loop terus-menerus sampai proses dihentikan (untuk runner CI/lokal)")
    parser.add_argument("--interval", type=int, default=120, help="Interval antar iterasi loop dalam detik (default: 120)")
    parser.add_argument("--max-runtime", type=int, default=21000, help="Batas total runtime loop dalam detik sebelum keluar bersih (default: 21000 = 350 menit)")
    args = parser.parse_args()

    # State management actions (tidak masuk loop)
    if args.restore_state:
        from src.publish import download_state
        w_url = args.worker_url or os.getenv("WORKER_URL", "http://127.0.0.1:8787")
        tok = args.token or os.getenv("INGEST_TOKEN", "")
        download_state(w_url, tok)
    elif args.save_state:
        from src.publish import upload_state
        w_url = args.worker_url or os.getenv("WORKER_URL", "http://127.0.0.1:8787")
        tok = args.token or os.getenv("INGEST_TOKEN", "")
        upload_state(w_url, tok)
    else:
        pipeline_kwargs = dict(
            publish=args.publish,
            dry_run=args.dry_run,
            all_charts=args.all_charts,
            worker_url=args.worker_url,
            token=args.token,
            spbu_chart_limit=args.spbu_limit,
            force_markov_refit=args.force_markov,
        )

        if not args.loop:
            # Eksekusi sekali
            run_pipeline(**pipeline_kwargs)
        else:
            # Loop permanen: jalankan tiap --interval detik sampai --max-runtime tercapai
            loop_start = time.time()
            iteration = 0
            print(f"[LOOP] Memulai loop permanen: interval={args.interval}s, max_runtime={args.max_runtime}s")
            while True:
                elapsed_total = time.time() - loop_start
                if elapsed_total >= args.max_runtime:
                    print(f"[LOOP] Batas runtime {args.max_runtime}s tercapai setelah {iteration} iterasi. Keluar bersih.")
                    break

                iteration += 1
                iter_start = time.time()
                print(f"\n{'='*72}")
                print(f"[LOOP] ITERASI #{iteration} | Elapsed total: {int(elapsed_total)}s / {args.max_runtime}s")
                print(f"{'='*72}")

                try:
                    run_pipeline(**pipeline_kwargs)
                except Exception as exc:
                    print(f"[LOOP] PERINGATAN: Iterasi #{iteration} gagal dengan error: {exc}")
                    print("[LOOP] Melanjutkan ke iterasi berikutnya...")

                iter_elapsed = time.time() - iter_start
                sleep_sec = max(0, args.interval - iter_elapsed)
                remaining = args.max_runtime - (time.time() - loop_start)

                if remaining <= 0:
                    print(f"[LOOP] Batas runtime tercapai. Keluar bersih setelah {iteration} iterasi.")
                    break

                print(f"[LOOP] Iterasi #{iteration} selesai dalam {iter_elapsed:.1f}s. Jeda {sleep_sec:.0f}s sebelum iterasi #{iteration+1}...")
                time.sleep(min(sleep_sec, remaining))
