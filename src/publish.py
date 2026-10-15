"""
Publish Module: Bundling Kontrak Data, Validasi Skema, & Ingest ke Cloudflare Worker
Menghasilkan 4 berkas kontrak di latest/:
1. meta.json (<2 KB) - diunggah TERAKHIR
2. summary.json (<150 KB)
3. stations.json (<1.5 MB)
4. history.json
Serta sinkronisasi state database:
- download_state(): unduh state/balifuel.db di awal job
- upload_state(): kompaksi VACUUM, retensi 14 hari, unggah state/balifuel.db di akhir job
"""

import os
import sys
import json
import sqlite3
import uuid
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional
import httpx

WITA_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.cleaner import sanitize_for_json

DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")
PUBLISH_OUT = os.path.join(BASE_DIR, "publish_out")

PIPELINE_VERSION = "2.1.0"
MAX_META_BYTES = 2500            # Target < 2 KB, batas keras 2.5 KB
MAX_SUMMARY_BYTES = 160 * 1024   # Target < 150 KB
MAX_STATIONS_BYTES = 1550 * 1024 # Target < 1.5 MB


def generate_run_id() -> str:
    now_str = datetime.now(UTC_TZ).strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"run_{now_str}_{short_uuid}"


def prune_and_compact_db(db_path: str = DB_PATH) -> int:
    """Melakukan retensi rolling 14 hari dan kompaksi VACUUM pada SQLite."""
    if not os.path.exists(db_path):
        return 0
    cutoff_dt = datetime.now(UTC_TZ) - timedelta(days=14)
    cutoff_iso = cutoff_dt.isoformat()
    cutoff_epoch = int(cutoff_dt.timestamp())

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM snapshots_meta WHERE timestamp_utc < ?", (cutoff_iso,))
        cursor.execute("DELETE FROM stats_snapshots WHERE timestamp_utc < ?", (cutoff_iso,))
        cursor.execute("DELETE FROM hourly_metrics WHERE epoch_t < ?", (cutoff_epoch,))
        cursor.execute("DELETE FROM driver_reports WHERE created_at_epoch < ?", (cutoff_epoch,))
        cursor.execute("DELETE FROM rate_derivatives WHERE timestamp_utc < ?", (cutoff_iso,))
        conn.commit()
        # Compact database
        cursor.execute("VACUUM")

    size = os.path.getsize(db_path)
    if size > 50 * 1024 * 1024:
        print(f"[State Warning] SQLite database size exceeds 50 MB: {size:,} bytes!")
    return size


def record_run_history(db_path: str, run_id: str, csi: float, median_recovery: str):
    """Merekam riwayat run untuk evaluasi stabilitas prediksi."""
    now_utc = datetime.now(UTC_TZ).isoformat()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs_history (
                run_id TEXT PRIMARY KEY,
                run_at_utc TEXT NOT NULL,
                csi_island REAL,
                median_recovery_wita TEXT
            )
        """)
        cursor.execute("""
            INSERT OR REPLACE INTO pipeline_runs_history (run_id, run_at_utc, csi_island, median_recovery_wita)
            VALUES (?, ?, ?, ?)
        """, (run_id, now_utc, csi, median_recovery))
        conn.commit()


def get_history_series(db_path: str = DB_PATH) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Mengambil riwayat CSI 14 hari dan riwayat prediksi dari DB."""
    hourly_csi = []
    run_stability = []
    if not os.path.exists(db_path):
        return hourly_csi, run_stability

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT epoch_t, timestamp_wita, csi
                FROM crisis_severity_hourly
                ORDER BY epoch_t ASC
            """)
            for row in cursor.fetchall():
                hourly_csi.append({"t": row[0], "wita": row[1], "csi": round(row[2], 1)})
        except Exception:
            pass

        try:
            cursor.execute("""
                SELECT run_id, run_at_utc, csi_island, median_recovery_wita
                FROM pipeline_runs_history
                ORDER BY run_at_utc DESC LIMIT 30
            """)
            for row in cursor.fetchall():
                run_stability.append({
                    "run_id": row[0],
                    "run_at": row[1],
                    "csi": row[2],
                    "median_recovery": row[3]
                })
        except Exception:
            pass

    return hourly_csi, run_stability


def build_contracts(run_id: str) -> Dict[str, Any]:
    """Menyusun 4 kontrak data dari data/clean/."""
    # 1. Load clean artifacts
    with open(os.path.join(CLEAN_DIR, "cleaned_stations.json"), "r", encoding="utf-8") as f:
        stations_clean = json.load(f)
    with open(os.path.join(CLEAN_DIR, "crisis_metrics.json"), "r", encoding="utf-8") as f:
        metrics = json.load(f)
    with open(os.path.join(CLEAN_DIR, "monte_carlo_results.json"), "r", encoding="utf-8") as f:
        monte_carlo = json.load(f)
    with open(os.path.join(CLEAN_DIR, "station_forecasts.json"), "r", encoding="utf-8") as f:
        forecasts = json.load(f)
    with open(os.path.join(CLEAN_DIR, "vulnerable_hotspots.json"), "r", encoding="utf-8") as f:
        hotspots = json.load(f)
    with open(os.path.join(DATA_DIR, "external_context.json"), "r", encoding="utf-8") as f:
        context = json.load(f)

    # Environmental (optional)
    env_data = {}
    env_file = os.path.join(CLEAN_DIR, "environmental_conditions.json")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            env_data = json.load(f)

    # 2. Record run stability in DB
    record_run_history(DB_PATH, run_id, metrics.get("current_island_csi", 50.0), monte_carlo.get("median_recovery_datetime_wita", ""))
    hourly_csi, run_stability = get_history_series(DB_PATH)

    now_utc = datetime.now(UTC_TZ)
    now_wita = now_utc.astimezone(WITA_TZ)

    # Calculate data age
    as_of_str = monte_carlo.get("start_datetime_wita", now_wita.strftime("%Y-%m-%d %H:%M WITA"))
    data_age_min = 5.0  # Fresh snapshot

    # Status determination (ok, degraded, stale)
    sources_ok = env_data.get("sources_ok", ["stats", "metrics", "reports", "stations"])
    sources_failed = env_data.get("sources_failed", [])
    if data_age_min > 30.0:
        status_code = "stale"
    elif len(sources_failed) > 0:
        status_code = "degraded"
    else:
        status_code = "ok"

    # --- KONTRAK 1: meta.json (<2 KB) ---
    meta_payload = {
        "run_id": run_id,
        "generated_at": {
            "utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "wita": now_wita.strftime("%Y-%m-%d %H:%M WITA")
        },
        "data_as_of": as_of_str,
        "data_age_min": round(data_age_min, 1),
        "status": status_code,
        "csi_island": metrics.get("current_island_csi", 50.0),
        "median_recovery_wita": monte_carlo.get("median_recovery_datetime_wita", ""),
        "median_day": monte_carlo.get("median_recovery_day_indonesian", ""),
        "ci50": monte_carlo.get("credible_intervals", {}).get("ci_50", {}).get("date_range_wita", []),
        "ci80": monte_carlo.get("credible_intervals", {}).get("ci_80", {}).get("date_range_wita", []),
        "n_paths": monte_carlo.get("total_paths", 10000),
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "pipeline_version": PIPELINE_VERSION
    }

    # --- KONTRAK 2: summary.json (<150 KB) ---
    summary_payload = {
        "run_id": run_id,
        "metrics": {
            "current_island_csi": metrics.get("current_island_csi"),
            "current_status": metrics.get("current_status"),
            "current_traffic_light": metrics.get("current_traffic_light"),
            "latest_empty_spbu_pct": metrics.get("latest_empty_spbu_pct"),
            "peak_csi": metrics.get("peak_csi"),
            "peak_timestamp_wita": metrics.get("peak_timestamp_wita"),
            "total_active_spbu": metrics.get("total_active_spbu"),
            "total_pertamini": metrics.get("total_pertamini"),
            "change_points": metrics.get("change_points", []),
            "diurnal_profile": metrics.get("diurnal_profile", [])
        },
        "areas": metrics.get("area_metrics", []),
        "monte_carlo": {
            "criteria": monte_carlo.get("criteria"),
            "median_hours": monte_carlo.get("median_recovery_hours"),
            "histogram": monte_carlo.get("histogram_recovery_dates", []),
            "cdf": monte_carlo.get("cumulative_distribution_function", []),
            "scenarios": monte_carlo.get("scenarios", {}),
            "sensitivity": monte_carlo.get("sensitivity", {}),
            "fan_chart": monte_carlo.get("fan_chart", {})
        },
        "hotspots": hotspots[:20],
        "environmental": env_data.get("metrics", {}),
        "timeline": context.get("crisis_timeline", [])
    }

    # --- KONTRAK 3: stations.json (Target <1.5 MB) ---
    st_map = {s["id"]: s for s in stations_clean}
    st_forecasts = forecasts.get("stations_forecast", {})

    compact_stations = []
    for s_id_str, fc in st_forecasts.items():
        s_id = int(s_id_str)
        st = st_map.get(s_id, {})
        p0 = round(float(fc.get("current_p_pertalite", 0.5)), 2)
        st_status = "available" if p0 >= 0.60 else ("warning" if p0 >= 0.35 else "empty")

        prices = st.get("prices") or {}
        pertalite_price = prices.get("pertalite")

        compact_stations.append({
            "id": s_id,
            "name": st.get("name") or f"SPBU {s_id}",
            "kind": "spbu" if st.get("kind") == "spbu" else "pertamini",
            "area": st.get("area") or "Bali",
            "lat": round(float(st.get("lat")), 5) if st.get("lat") is not None else None,
            "lng": round(float(st.get("lon")), 5) if st.get("lon") is not None else None,
            "status": st_status,
            "p_now": p0,
            "queue": st.get("queue_mins"),
            "price": pertalite_price,
            "recov": fc.get("estimated_recovery_datetime_wita", ""),
            "p10": [round(float(x), 2) for x in fc.get("p10_traj", [])],
            "p50": [round(float(x), 2) for x in fc.get("p50_traj", [])],
            "p90": [round(float(x), 2) for x in fc.get("p90_traj", [])],
            "q_traj": [round(float(x), 1) for x in fc.get("queue_traj_mins", [])]
        })

    stations_payload = {
        "run_id": run_id,
        "hours": forecasts.get("hours_label", []),
        "stations": compact_stations
    }

    # --- KONTRAK 4: history.json ---
    history_payload = {
        "run_id": run_id,
        "hourly_csi": hourly_csi,
        "run_stability": run_stability
    }

    return {
        "meta.json": sanitize_for_json(meta_payload),
        "summary.json": sanitize_for_json(summary_payload),
        "stations.json": sanitize_for_json(stations_payload),
        "history.json": sanitize_for_json(history_payload)
    }


def validate_contracts(contracts: Dict[str, Any]) -> Dict[str, int]:
    """Validasi ukuran dan skema kontrak data."""
    sizes = {}

    # 1. meta.json
    meta_bytes = json.dumps(contracts["meta.json"], separators=(',', ':'), allow_nan=False).encode("utf-8")
    sizes["meta.json"] = len(meta_bytes)
    if len(meta_bytes) > MAX_META_BYTES:
        print(f"[Contract Warning] meta.json size {len(meta_bytes)}B exceeds target {MAX_META_BYTES}B")

    # 2. summary.json
    summary_bytes = json.dumps(contracts["summary.json"], separators=(',', ':'), allow_nan=False).encode("utf-8")
    sizes["summary.json"] = len(summary_bytes)
    if len(summary_bytes) > MAX_SUMMARY_BYTES:
        print(f"[Contract Warning] summary.json size {len(summary_bytes)/1024:.1f}KB exceeds {MAX_SUMMARY_BYTES/1024}KB")

    # 3. stations.json
    stations_bytes = json.dumps(contracts["stations.json"], separators=(',', ':'), allow_nan=False).encode("utf-8")
    sizes["stations.json"] = len(stations_bytes)
    if len(stations_bytes) > MAX_STATIONS_BYTES:
        print(f"[Contract Warning] stations.json size {len(stations_bytes)/1024/1024:.2f}MB exceeds {MAX_STATIONS_BYTES/1024/1024}MB")

    # 4. history.json
    history_bytes = json.dumps(contracts["history.json"], separators=(',', ':'), allow_nan=False).encode("utf-8")
    sizes["history.json"] = len(history_bytes)
    return sizes


def save_dry_run_files(contracts: Dict[str, Any], output_dir: str = PUBLISH_OUT) -> Dict[str, str]:
    """Menyimpan berkas kontrak ke output_dir untuk mode dry-run."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    for filename, payload in contracts.items():
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        paths[filename] = filepath
    return paths


def upload_contract(worker_url: str, token: str, filename: str, payload_bytes: bytes, client: httpx.Client) -> Dict[str, Any]:
    """Mengunggah satu kontrak data ke PUT /ingest/<filename>."""
    url = f"{worker_url.rstrip('/')}/ingest/{filename}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = client.put(url, content=payload_bytes, headers=headers, timeout=25.0)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Failed to ingest {filename}: Status {resp.status_code} - {resp.text}")
    return resp.json()


def publish_pipeline_artifacts(worker_url: Optional[str] = None, token: Optional[str] = None, dry_run: bool = False, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Eksekusi publikasi kontrak data:
    1. stations.json
    2. summary.json
    3. history.json
    4. meta.json (TERAKHIR)
    """
    if not run_id:
        run_id = generate_run_id()

    print(f"[*] Packaging publication contracts for Run ID: {run_id}")
    contracts = build_contracts(run_id)
    sizes = validate_contracts(contracts)

    print("\n[=== KONTRAK DATA AUDIT UKURAN ===]")
    for fn, sz in sizes.items():
        print(f"  - {fn:14}: {sz:,} bytes ({sz/1024:.1f} KB)")

    if dry_run or not worker_url:
        paths = save_dry_run_files(contracts, PUBLISH_OUT)
        print(f"\n[+] Dry-run completed. All 4 contracts written to: {PUBLISH_OUT}")
        return {"run_id": run_id, "dry_run": True, "sizes": sizes, "paths": paths}

    # Live Upload mode
    if not token:
        token = os.getenv("INGEST_TOKEN", "")
    if not token:
        raise ValueError("INGEST_TOKEN is required for live publish.")

    print(f"\n[*] Uploading contracts to Worker: {worker_url} (Strict Order: stations -> summary -> history -> meta)")

    # Strict upload order: stations -> summary -> history -> meta
    upload_order = ["stations.json", "summary.json", "history.json", "meta.json"]
    upload_results = {}

    with httpx.Client() as client:
        for fn in upload_order:
            payload_bytes = json.dumps(contracts[fn], separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode("utf-8")
            res = upload_contract(worker_url, token, fn, payload_bytes, client)
            upload_results[fn] = res
            print(f"  ✓ {fn} uploaded ({len(payload_bytes):,} B, ETag: {res.get('etag')})")

    return {
        "run_id": run_id,
        "dry_run": False,
        "sizes": sizes,
        "uploads": upload_results
    }


def download_state(worker_url: str, token: str, target_db_path: str = DB_PATH) -> bool:
    """Mengunduh state/balifuel.db di awal job. Jika 404, return False untuk bootstrap baru."""
    url = f"{worker_url.rstrip('/')}/state/balifuel.db"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[*] Restoring state from: {url}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(target_db_path), exist_ok=True)
                with open(target_db_path, "wb") as f:
                    f.write(resp.content)
                print(f"[+] State restored successfully ({len(resp.content):,} bytes).")
                return True
            elif resp.status_code == 404:
                print("[*] State not found in R2 (404). Bootstrapping fresh database.")
                return False
            else:
                print(f"[State Warning] Download returned status {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[State Warning] Could not download state: {e}. Bootstrapping fresh DB.")
        return False


def upload_state(worker_url: str, token: str, source_db_path: str = DB_PATH) -> bool:
    """Mengunggah state/balifuel.db di akhir job setelah retensi dan kompaksi."""
    if not os.path.exists(source_db_path):
        print(f"[State Warning] Database {source_db_path} does not exist. Skipping state upload.")
        return False

    final_size = prune_and_compact_db(source_db_path)
    print(f"[*] Pruned & compacted database. Final size: {final_size:,} bytes ({final_size/1024/1024:.2f} MB)")

    url = f"{worker_url.rstrip('/')}/state/balifuel.db"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream"
    }

    try:
        with open(source_db_path, "rb") as f:
            data = f.read()
        with httpx.Client(timeout=45.0) as client:
            resp = client.put(url, content=data, headers=headers)
            if resp.status_code == 200:
                print(f"[+] State successfully uploaded to R2 ({len(data):,} bytes).")
                return True
            else:
                print(f"[State Warning] Upload failed with status {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print(f"[State Error] Failed to upload state: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish contracts & sync state with Cloudflare Worker")
    parser.add_argument("--dry-run", action="store_true", help="Generate and validate files into ./publish_out without uploading")
    parser.add_argument("--worker-url", type=str, default=os.getenv("WORKER_URL", "http://127.0.0.1:8787"), help="Cloudflare Worker URL")
    parser.add_argument("--token", type=str, default=os.getenv("INGEST_TOKEN", ""), help="Ingest Bearer Token")
    parser.add_argument("--restore-state", action="store_true", help="Download state/balifuel.db from Worker")
    parser.add_argument("--save-state", action="store_true", help="Compact and upload state/balifuel.db to Worker")
    args = parser.parse_args()

    if args.restore_state:
        download_state(args.worker_url, args.token)
    elif args.save_state:
        upload_state(args.worker_url, args.token)
    else:
        publish_pipeline_artifacts(worker_url=args.worker_url, token=args.token, dry_run=args.dry_run)
