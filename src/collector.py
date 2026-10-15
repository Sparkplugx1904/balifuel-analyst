"""
Collector Module: Data Krisis BBM Bali
Mengumpulkan data secara berkala dari endpoint JSON dan HTML-embedded JSON,
menyimpan JSON mentah ke data/raw/, mengelola time series ke SQLite,
dan menghitung turunan laju per jam (rate derivatives).
"""

import os
import sys
import time
import json
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
import httpx
from bs4 import BeautifulSoup

WITA_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
DB_PATH = os.path.join(DATA_DIR, "balifuel.db")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36 BaliFuelCrisisResearch/1.0"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html, */*"
}

ENDPOINTS = {
    "stats": "https://balifuelwatch.vercel.app/api/stats",
    "metrics": "https://balifuelwatch.vercel.app/api/metrics",
    "reports_day": "https://balifuelwatch.vercel.app/api/reports?w=day&f=2",
    "reports_recent": "https://balifuelwatch.vercel.app/api/reports?w=recent&f=2",
    "places": "https://balifuelwatch.vercel.app/api/places",
    "odbl": "https://balifuelwatch.vercel.app/odbl-stations.json",
    "bensinbali": "https://bensinbali.com/",
    "marine_sanggaran": "https://marine-api.open-meteo.com/v1/marine?latitude=-8.86&longitude=115.30&hourly=wave_height,wave_period,wave_direction&timezone=Asia%2FMakassar",
    "marine_manggis": "https://marine-api.open-meteo.com/v1/marine?latitude=-8.62&longitude=115.70&hourly=wave_height,wave_period,wave_direction&timezone=Asia%2FMakassar",
    "weather_denpasar": "https://api.open-meteo.com/v1/forecast?latitude=-8.7262&longitude=115.2120&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m&hourly=precipitation_probability,wind_speed_10m&timezone=Asia%2FMakassar",
    "bmkg_weather": "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=51.71.01.1001"
}

FUELS = ["pertalite", "pertamax", "solar"]


def init_db(db_path: str = DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Table: raw snapshots metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snapshots_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_key TEXT NOT NULL,
                url TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                timestamp_wita TEXT NOT NULL,
                status_code INTEGER,
                etag TEXT,
                file_path TEXT,
                records_count INTEGER
            )
        """)
        
        # Table: stats time series (cumulative & online)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                timestamp_wita TEXT NOT NULL,
                online_users INTEGER,
                today_users INTEGER,
                total_users INTEGER,
                reports_total INTEGER,
                reports_today INTEGER,
                places_added INTEGER,
                reported_at_utc TEXT
            )
        """)

        # Table: hourly metrics history bootstrap
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_metrics (
                epoch_t INTEGER PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                timestamp_wita TEXT NOT NULL,
                reports INTEGER,
                has_fuel INTEGER,
                empty INTEGER,
                reporters INTEGER,
                new_users INTEGER,
                places INTEGER
            )
        """)

        # Table: driver reports (high-res events)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS driver_reports (
                report_id INTEGER PRIMARY KEY,
                station_id INTEGER,
                fuel TEXT,
                available INTEGER,
                queue_wait INTEGER,
                created_at_epoch INTEGER,
                created_at_utc TEXT,
                created_at_wita TEXT
            )
        """)

        # Table: master stations (Pertamina SPBU & Pertamini)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations_master (
                id INTEGER PRIMARY KEY,
                kind TEXT,
                brand TEXT,
                name TEXT,
                code TEXT,
                address TEXT,
                area TEXT,
                regency TEXT,
                lat REAL,
                lon REAL,
                diesel_available INTEGER,
                h24 INTEGER,
                lookers INTEGER,
                tracking INTEGER,
                queue_mins REAL,
                queue_json TEXT,
                busy_live INTEGER,
                busy_usual INTEGER,
                usual_today_json TEXT,
                prices_json TEXT,
                reports_summary_json TEXT,
                last_updated_utc TEXT,
                last_updated_wita TEXT
            )
        """)

        # Table: rate derivatives (deltas per hour, handling resets)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_derivatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                timestamp_wita TEXT NOT NULL,
                period_seconds REAL,
                delta_reports REAL,
                delta_users REAL,
                delta_places REAL,
                reports_per_hour REAL,
                users_per_hour REAL,
                is_counter_reset INTEGER DEFAULT 0
            )
        """)
        # Table: environmental & marine metrics (Open-Meteo & BMKG)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS environmental_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                timestamp_wita TEXT NOT NULL,
                source TEXT NOT NULL,
                location TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
        """)
        conn.commit()


def get_current_timestamps() -> Tuple[str, str, datetime]:
    now_utc = datetime.now(UTC_TZ)
    now_wita = now_utc.astimezone(WITA_TZ)
    return now_utc.isoformat(), now_wita.isoformat(), now_utc


def save_raw_json(endpoint_key: str, data: Any, timestamp_str: str) -> str:
    sanitized_ts = timestamp_str.replace(":", "-").replace("+", "_")
    filename = f"{sanitized_ts}_{endpoint_key}.json"
    full_path = os.path.join(RAW_DIR, filename)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return os.path.relpath(full_path, BASE_DIR)


def collect_snapshot(db_path: str = DB_PATH, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Mengambil satu putaran snapshot lengkap dari semua sumber."""
    init_db(db_path)
    close_client = False
    if client is None:
        client = httpx.Client(headers=HEADERS, timeout=20.0, follow_redirects=True)
        close_client = True

    ts_utc, ts_wita, now_dt = get_current_timestamps()
    ts_file = now_dt.strftime("%Y%m%d_%H%M%S")
    summary = {"timestamp_wita": ts_wita, "collected": {}}

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # 1. Fetch /api/stats
            try:
                r_stats = client.get(ENDPOINTS["stats"])
                if r_stats.status_code == 200:
                    j_stats = r_stats.json()
                    raw_file = save_raw_json("stats", j_stats, ts_file)
                    cursor.execute("""
                        INSERT INTO snapshots_meta 
                        (endpoint_key, url, timestamp_utc, timestamp_wita, status_code, etag, file_path, records_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, ("stats", ENDPOINTS["stats"], ts_utc, ts_wita, 200, r_stats.headers.get("etag"), raw_file, 1))

                    cursor.execute("""
                        INSERT INTO stats_snapshots
                        (timestamp_utc, timestamp_wita, online_users, today_users, total_users,
                         reports_total, reports_today, places_added, reported_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ts_utc, ts_wita,
                        j_stats.get("online", 0),
                        j_stats.get("today", 0),
                        j_stats.get("total", 0),
                        j_stats.get("reports_total", 0),
                        j_stats.get("reports_today", 0),
                        j_stats.get("places_added", 0),
                        j_stats.get("at", "")
                    ))
                    summary["collected"]["stats"] = j_stats
            except Exception as e:
                print(f"[Collector Warning] /api/stats failed: {e}")

            # 2. Fetch /api/metrics (hourly bootstrap & aggregates)
            try:
                r_metrics = client.get(ENDPOINTS["metrics"])
                if r_metrics.status_code == 200:
                    j_metrics = r_metrics.json()
                    raw_file = save_raw_json("metrics", j_metrics, ts_file)
                    hourly = j_metrics.get("hourly", [])
                    cursor.execute("""
                        INSERT INTO snapshots_meta 
                        (endpoint_key, url, timestamp_utc, timestamp_wita, status_code, etag, file_path, records_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, ("metrics", ENDPOINTS["metrics"], ts_utc, ts_wita, 200, r_metrics.headers.get("etag"), raw_file, len(hourly)))

                    # Insert hourly rows
                    for h in hourly:
                        t_epoch = h.get("t")
                        if not t_epoch:
                            continue
                        dt_h_utc = datetime.fromtimestamp(t_epoch, tz=timezone.utc)
                        dt_h_wita = dt_h_utc.astimezone(WITA_TZ)
                        cursor.execute("""
                            INSERT OR REPLACE INTO hourly_metrics
                            (epoch_t, timestamp_utc, timestamp_wita, reports, has_fuel, empty, reporters, new_users, places)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            t_epoch,
                            dt_h_utc.isoformat(),
                            dt_h_wita.isoformat(),
                            h.get("reports", 0),
                            h.get("has_fuel", 0),
                            h.get("empty", 0),
                            h.get("reporters", 0),
                            h.get("new_users", 0),
                            h.get("places", 0)
                        ))
                    summary["collected"]["metrics_hourly_count"] = len(hourly)
            except Exception as e:
                print(f"[Collector Warning] /api/metrics failed: {e}")

            # 3. Fetch /api/reports?w=day&f=2
            try:
                r_rep = client.get(ENDPOINTS["reports_day"])
                if r_rep.status_code == 200:
                    j_rep = r_rep.json()
                    raw_file = save_raw_json("reports_day", j_rep, ts_file)
                    rows = j_rep.get("rows", [])
                    cursor.execute("""
                        INSERT INTO snapshots_meta 
                        (endpoint_key, url, timestamp_utc, timestamp_wita, status_code, etag, file_path, records_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, ("reports_day", ENDPOINTS["reports_day"], ts_utc, ts_wita, 200, r_rep.headers.get("etag"), raw_file, len(rows)))

                    inserted_rep = 0
                    for row in rows:
                        # [id, station_id, fuel_idx, available, queue, created_at_epoch]
                        rep_id, st_id, f_idx, avail, q_val, epoch_s = row
                        fuel_name = FUELS[f_idx] if 0 <= f_idx < len(FUELS) else "pertalite"
                        dt_r_utc = datetime.fromtimestamp(epoch_s, tz=timezone.utc)
                        dt_r_wita = dt_r_utc.astimezone(WITA_TZ)
                        cursor.execute("""
                            INSERT OR REPLACE INTO driver_reports
                            (report_id, station_id, fuel, available, queue_wait, created_at_epoch, created_at_utc, created_at_wita)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rep_id, st_id, fuel_name, int(bool(avail)),
                            q_val, epoch_s, dt_r_utc.isoformat(), dt_r_wita.isoformat()
                        ))
                        inserted_rep += 1
                    summary["collected"]["reports_count"] = inserted_rep
            except Exception as e:
                print(f"[Collector Warning] /api/reports failed: {e}")

            # 4. Fetch bensinbali.com for 876 stations + Pertamini + retail prices
            try:
                r_bb = client.get(ENDPOINTS["bensinbali"])
                if r_bb.status_code == 200:
                    soup = BeautifulSoup(r_bb.text, "html.parser")
                    script_tag = soup.find("script", id="fuel-data")
                    if script_tag and script_tag.string:
                        bb_data = json.loads(script_tag.string)
                        raw_file = save_raw_json("bensinbali_fuel_data", bb_data, ts_file)
                        stations = bb_data.get("stations", [])
                        cursor.execute("""
                            INSERT INTO snapshots_meta 
                            (endpoint_key, url, timestamp_utc, timestamp_wita, status_code, etag, file_path, records_count)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, ("bensinbali", ENDPOINTS["bensinbali"], ts_utc, ts_wita, 200, r_bb.headers.get("etag"), raw_file, len(stations)))

                        for s in stations:
                            s_id = s.get("id")
                            if s_id is None:
                                continue
                            kind = s.get("kind", "spbu")
                            brand = s.get("brand", "")
                            name = s.get("name", "")
                            code = s.get("code") or ""
                            addr = s.get("address", "")
                            area = s.get("area", "")
                            lat = s.get("lat")
                            lon = s.get("lng")
                            lookers = int(s.get("lookers") or 0)
                            tracking = int(s.get("tracking") or 0)
                            queue = s.get("queue")
                            queue_mins = None
                            queue_json = None
                            if isinstance(queue, dict):
                                queue_mins = queue.get("mins")
                                queue_json = json.dumps(queue)
                            elif isinstance(queue, (int, float)):
                                queue_mins = float(queue)
                                queue_json = json.dumps({"mins": queue_mins})

                            busy = s.get("busy")
                            busy_live = busy.get("live") if isinstance(busy, dict) else None
                            busy_usual = busy.get("usual") if isinstance(busy, dict) else None
                            usual_today_json = json.dumps(s.get("usualToday")) if s.get("usualToday") else None

                            # extract prices
                            prices = {}
                            reports = s.get("reports", [])
                            for rep in reports:
                                if "prices" in rep and isinstance(rep["prices"], dict):
                                    prices.update(rep["prices"])

                            cursor.execute("""
                                INSERT OR REPLACE INTO stations_master
                                (id, kind, brand, name, code, address, area, regency, lat, lon,
                                 diesel_available, h24, lookers, tracking, queue_mins, queue_json,
                                 busy_live, busy_usual, usual_today_json, prices_json,
                                 reports_summary_json, last_updated_utc, last_updated_wita)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                s_id, kind, brand, name, code, addr, area, "",
                                lat, lon, 0, 0, lookers, tracking, queue_mins, queue_json,
                                busy_live, busy_usual, usual_today_json,
                                json.dumps(prices), json.dumps(reports),
                                ts_utc, ts_wita
                            ))
                        summary["collected"]["bensinbali_stations"] = len(stations)
            except Exception as e:
                print(f"[Collector Warning] bensinbali fetch failed: {e}")

            # 5. Fetch ODbL stations master (official Pertamina stations with regency & 24h flag)
            try:
                r_odbl = client.get(ENDPOINTS["odbl"])
                if r_odbl.status_code == 200:
                    j_odbl = r_odbl.json()
                    raw_file = save_raw_json("odbl_stations", j_odbl, ts_file)
                    st_list = j_odbl.get("stations", [])
                    for s in st_list:
                        s_id = s.get("id")
                        cursor.execute("""
                            UPDATE stations_master
                            SET regency = ?, diesel_available = ?, h24 = ?,
                                name = CASE WHEN name = '.' OR name = '' THEN ? ELSE name END
                            WHERE id = ?
                        """, (
                            s.get("reg", ""),
                            1 if s.get("diesel") else 0,
                            1 if s.get("h24") else 0,
                            s.get("name", ""),
                            s_id
                        ))
                    summary["collected"]["odbl_stations_enriched"] = len(st_list)
            except Exception as e:
                print(f"[Collector Warning] ODbL fetch failed: {e}")

            # 6. Optional Environmental & Marine Collectors
            env_status = collect_optional_environmental(conn, client, ts_utc, ts_wita)
            summary["environmental"] = env_status
            summary["sources_ok"] = env_status.get("sources_ok", [])
            summary["sources_failed"] = env_status.get("sources_failed", [])

            # 7. Compute rate derivatives
            compute_derivatives(conn, ts_utc, ts_wita)
            conn.commit()

    finally:
        if close_client:
            client.close()

    return summary


def compute_derivatives(conn: sqlite3.Connection, current_utc: str, current_wita: str):
    """Menghitung selisih laporan & user antar snapshot, menangani reset counter."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp_utc, online_users, today_users, total_users, reports_total, places_added
        FROM stats_snapshots
        ORDER BY id DESC LIMIT 2
    """)
    rows = cursor.fetchall()
    if len(rows) < 2:
        return

    curr, prev = rows[0], rows[1]
    curr_t = datetime.fromisoformat(curr[0])
    prev_t = datetime.fromisoformat(prev[0])
    period = max(1.0, (curr_t - prev_t).total_seconds())

    # Detect reset / decrease
    is_reset = 0
    delta_rep = curr[4] - prev[4]
    delta_usr = curr[3] - prev[3]
    delta_plc = curr[5] - prev[5]

    if delta_rep < 0 or delta_usr < 0:
        is_reset = 1
        delta_rep = max(0, curr[4])
        delta_usr = max(0, curr[3])

    hours = period / 3600.0
    rep_rate = delta_rep / hours if hours > 0 else 0.0
    usr_rate = delta_usr / hours if hours > 0 else 0.0

    cursor.execute("""
        INSERT INTO rate_derivatives
        (timestamp_utc, timestamp_wita, period_seconds, delta_reports, delta_users,
         delta_places, reports_per_hour, users_per_hour, is_counter_reset)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        current_utc, current_wita, period, delta_rep, delta_usr,
        delta_plc, rep_rate, usr_rate, is_reset
    ))


def run_daemon(interval_sec: int = 300, max_cycles: Optional[int] = None):
    """Menjalankan loop pengumpulan berkala."""
    print(f"[*] Starting Bali Fuel Crisis collector daemon (interval: {interval_sec}s)...")
    cycles = 0
    with httpx.Client(headers=HEADERS, timeout=25.0, follow_redirects=True) as client:
        while True:
            t0 = time.time()
            try:
                res = collect_snapshot(DB_PATH, client=client)
                print(f"[{res['timestamp_wita']}] Snapshot collected: {res['collected']}")
            except Exception as e:
                print(f"[Error in collector loop]: {e}")

            cycles += 1
            if max_cycles and cycles >= max_cycles:
                print(f"[*] Max cycles ({max_cycles}) reached. Exiting daemon.")
                break

            elapsed = time.time() - t0
            sleep_time = max(5.0, interval_sec - elapsed)
            time.sleep(sleep_time)

def collect_optional_environmental(conn: sqlite3.Connection, client: httpx.Client, ts_utc: str, ts_wita: str) -> Dict[str, Any]:
    """Mengumpulkan data cuaca & maritim opsional. Gagal = dilewati, status degraded, pipeline tetap berjalan."""
    cursor = conn.cursor()
    env_results = {}
    sources_ok = ["stats", "metrics", "reports", "stations"]
    sources_failed = []

    # 1. Marine Sanggaran
    try:
        r = client.get(ENDPOINTS["marine_sanggaran"], timeout=8.0)
        if r.status_code == 200:
            j = r.json()
            cursor.execute("INSERT INTO environmental_metrics (timestamp_utc, timestamp_wita, source, location, data_json) VALUES (?, ?, ?, ?, ?)",
                           (ts_utc, ts_wita, "open-meteo-marine", "sanggaran_sea", json.dumps(j.get("hourly", {}))))
            env_results["sanggaran_wave_m"] = j.get("hourly", {}).get("wave_height", [None])[0]
            sources_ok.append("marine_sanggaran")
        else:
            sources_failed.append("marine_sanggaran")
    except Exception as e:
        sources_failed.append("marine_sanggaran")

    # 2. Marine Manggis
    try:
        r = client.get(ENDPOINTS["marine_manggis"], timeout=8.0)
        if r.status_code == 200:
            j = r.json()
            cursor.execute("INSERT INTO environmental_metrics (timestamp_utc, timestamp_wita, source, location, data_json) VALUES (?, ?, ?, ?, ?)",
                           (ts_utc, ts_wita, "open-meteo-marine", "manggis_sea", json.dumps(j.get("hourly", {}))))
            env_results["manggis_wave_m"] = j.get("hourly", {}).get("wave_height", [None])[0]
            sources_ok.append("marine_manggis")
        else:
            sources_failed.append("marine_manggis")
    except Exception as e:
        sources_failed.append("marine_manggis")

    # 3. Weather Denpasar
    try:
        r = client.get(ENDPOINTS["weather_denpasar"], timeout=8.0)
        if r.status_code == 200:
            j = r.json()
            cursor.execute("INSERT INTO environmental_metrics (timestamp_utc, timestamp_wita, source, location, data_json) VALUES (?, ?, ?, ?, ?)",
                           (ts_utc, ts_wita, "open-meteo-forecast", "denpasar", json.dumps(j.get("current", {}))))
            env_results["denpasar_temp_c"] = j.get("current", {}).get("temperature_2m")
            sources_ok.append("weather_denpasar")
        else:
            sources_failed.append("weather_denpasar")
    except Exception as e:
        sources_failed.append("weather_denpasar")

    # 4. BMKG Weather
    try:
        r = client.get(ENDPOINTS["bmkg_weather"], timeout=8.0)
        if r.status_code == 200:
            j = r.json()
            cursor.execute("INSERT INTO environmental_metrics (timestamp_utc, timestamp_wita, source, location, data_json) VALUES (?, ?, ?, ?, ?)",
                           (ts_utc, ts_wita, "bmkg", "denpasar_adm4", json.dumps(j)))
            sources_ok.append("bmkg_weather")
        else:
            sources_failed.append("bmkg_weather")
    except Exception as e:
        sources_failed.append("bmkg_weather")

    # 5. AIS Stream
    ais_key = os.getenv("AISSTREAM_KEY")
    if ais_key:
        sources_ok.append("ais_stream")
    else:
        env_results["ais_status"] = "skipped_no_key"

    clean_env_path = os.path.join(CLEAN_DIR, "environmental_conditions.json")
    os.makedirs(CLEAN_DIR, exist_ok=True)
    with open(clean_env_path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at_wita": ts_wita,
            "metrics": env_results,
            "sources_ok": sources_ok,
            "sources_failed": sources_failed,
            "credits": {
                "bmkg": "Prakiraan cuaca resmi: Badan Meteorologi, Klimatologi, dan Geofisika (BMKG)",
                "open_meteo": "Data maritim dan cuaca berlisensi Open-Meteo bawah CC BY 4.0"
            }
        }, f, indent=2)

    return {"sources_ok": sources_ok, "sources_failed": sources_failed, "metrics": env_results}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collector for Bali Fuel Crisis Data")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous polling loop")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds (default: 300s)")
    parser.add_argument("--cycles", type=int, default=None, help="Max cycles for daemon mode")
    args = parser.parse_args()

    if args.daemon:
        run_daemon(interval_sec=args.interval, max_cycles=args.cycles)
    else:
        print("[*] Running one-shot collection and bootstrap...")
        res = collect_snapshot(DB_PATH)
        print(f"Done. Collected: {json.dumps(res, indent=2)}")
