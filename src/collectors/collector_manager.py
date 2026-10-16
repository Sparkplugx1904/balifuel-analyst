"""
Collector Manager & Orchestrator: BaliFuel Analyst System
Menjalankan 6 modul collector secara paralel/sekuensial dengan prinsip degradasi mulus:
1. marine_weather_collector (SRC-006 & SRC-025)
2. routing_distance_collector (SRC-008 & SRC-021)
3. behavioral_news_collector (SRC-030)
4. calendar_holidays_collector (SRC-011 & SRC-020 & SRC-038)
5. macro_demand_collector (SRC-018 & SRC-019)
6. osm_infrastructure_collector (SRC-006 & SRC-024)
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.collectors.marine_weather_collector import collect_marine_weather
from src.collectors.routing_distance_collector import collect_routing_distances
from src.collectors.behavioral_news_collector import collect_behavioral_news
from src.collectors.calendar_holidays_collector import collect_calendar_features
from src.collectors.macro_demand_collector import collect_macro_demand
from src.collectors.osm_infrastructure_collector import collect_osm_infrastructure

CLEAN_DIR = os.path.join(BASE_DIR, "data", "clean")
DB_PATH = os.path.join(BASE_DIR, "data", "balifuel.db")


def run_all_collectors() -> Dict[str, Any]:
    os.makedirs(CLEAN_DIR, exist_ok=True)
    t0 = time.time()
    now_wita = datetime.now(WITA_TZ).strftime("%Y-%m-%d %H:%M:%S WITA")
    print(f"\n{'='*64}")
    print(f"[*] RUNNING ALL 6 GRACEFUL COLLECTORS [{now_wita}]")
    print(f"{'='*64}")

    collectors_results = {}
    statuses = {}

    # 1. Marine Weather
    try:
        res = collect_marine_weather()
        collectors_results["marine_weather"] = res.get("data")
        statuses["marine_weather"] = res.get("status")
    except Exception as e:
        print(f" [!] Error in marine_weather: {e}")
        statuses["marine_weather"] = "failed_degraded"
        collectors_results["marine_weather"] = {"marine_risk_level": "low", "tanker_berthing_delay_hours": 0.0}

    # 2. Routing Distance Matrix
    try:
        res = collect_routing_distances()
        collectors_results["routing_matrix"] = res.get("data")
        statuses["routing_matrix"] = res.get("status")
    except Exception as e:
        print(f" [!] Error in routing_distance: {e}")
        statuses["routing_matrix"] = "failed_degraded"
        collectors_results["routing_matrix"] = {"critical_bottleneck_areas": []}

    # 3. Behavioral News RSS
    try:
        res = collect_behavioral_news()
        collectors_results["news_signals"] = res.get("data")
        statuses["news_signals"] = res.get("status")
    except Exception as e:
        print(f" [!] Error in behavioral_news: {e}")
        statuses["news_signals"] = "failed_degraded"
        collectors_results["news_signals"] = {"panic_news_ratio": 0.5, "media_narrative_phase": "neutral"}

    # 4. Calendar & Ceremonial Cycles
    try:
        res = collect_calendar_features()
        collectors_results["calendar_signals"] = res.get("data")
        statuses["calendar_signals"] = res.get("status")
    except Exception as e:
        print(f" [!] Error in calendar_holidays: {e}")
        statuses["calendar_signals"] = "failed_degraded"
        collectors_results["calendar_signals"] = {"total_temporal_demand_multiplier": 1.0}

    # 5. Macroeconomic & Tourism Demand
    try:
        res = collect_macro_demand()
        collectors_results["macro_demand"] = res.get("data")
        statuses["macro_demand"] = res.get("status")
    except Exception as e:
        print(f" [!] Error in macro_demand: {e}")
        statuses["macro_demand"] = "failed_degraded"
        collectors_results["macro_demand"] = {"brent_crude_usd_per_barrel": 76.5, "usd_idr_exchange_rate": 15700.0}

    # 6. OSM Highway Infrastructure
    try:
        res = collect_osm_infrastructure()
        collectors_results["osm_infrastructure"] = res.get("data")
        statuses["osm_infrastructure"] = res.get("status")
    except Exception as e:
        print(f" [!] Error in osm_infrastructure: {e}")
        statuses["osm_infrastructure"] = "failed_degraded"
        collectors_results["osm_infrastructure"] = {"corridor_priority_boost": {}}

    total_time = round(time.time() - t0, 2)
    consolidated = {
        "collected_at_wita": now_wita,
        "elapsed_seconds": total_time,
        "collector_statuses": statuses,
        "payload": collectors_results
    }

    # Save to data/clean/environmental_conditions.json
    clean_file = os.path.join(CLEAN_DIR, "environmental_conditions.json")
    with open(clean_file, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2)

    print(f"\n[+] All 6 Collectors Finished in {total_time}s. Saved -> {clean_file}")
    print(f" Statuses: {statuses}")
    print(f"{'='*64}\n")

    return consolidated


if __name__ == "__main__":
    run_all_collectors()
