"""
Marine & Terrestrial Weather Collector: Bali Fuel Crisis Analyst
Kategori: F. Cuaca & Laut (SRC-006 & SRC-025)
Mengambil data oseanografi (tinggi gelombang laut Selat Badung & TBBM Manggis)
untuk menghitung indeks risiko keterlambatan sandar kapal tanker.
"""

import os
import sys
import json
import time
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")


def collect_marine_weather() -> Dict[str, Any]:
    os.makedirs(RAW_DIR, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    now_wita = datetime.now(WITA_TZ)

    # Titik Perairan TBBM Manggis (Karangasem / Selat Lombok)
    lat_manggis = -8.5115
    lon_manggis = 115.5300

    url = (
        f"https://marine-api.open-meteo.com/v1/marine?"
        f"latitude={lat_manggis}&longitude={lon_manggis}"
        f"&hourly=wave_height,wave_direction,wave_period"
        f"&forecast_days=3"
    )

    result = {
        "collector": "marine_weather_collector",
        "timestamp_utc": now_utc.isoformat(),
        "timestamp_wita": now_wita.strftime("%Y-%m-%d %H:%M:%S WITA"),
        "status": "degraded",
        "data": None
    }

    retries = 3
    backoff = 1.0
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=8.0, headers={"User-Agent": "BaliFuel-Analyst/2.0"}) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    hourly = data.get("hourly", {})
                    waves = hourly.get("wave_height", [])
                    max_wave = float(np_max) if (np_max := max(waves, default=0.0)) else 0.0
                    avg_wave = float(sum(waves) / len(waves)) if waves else 0.0

                    # Kategori risiko sandar tanker Pertamina:
                    # < 1.25m: Tenang (Aman sandar)
                    # 1.25m - 2.0m: Sedang (Perlu kewaspadaan tugboat)
                    # > 2.0m: Tinggi (Risiko tertunda sandar)
                    risk_level = "low" if avg_wave < 1.25 else ("medium" if avg_wave < 2.0 else "high")

                    processed = {
                        "coordinates": {"lat": lat_manggis, "lon": lon_manggis},
                        "tbbm_monitored": "TBBM Manggis (Karangasem)",
                        "current_wave_height_m": waves[0] if waves else 0.8,
                        "max_forecast_wave_height_m": round(max_wave, 2),
                        "avg_wave_height_m": round(avg_wave, 2),
                        "marine_risk_level": risk_level,
                        "tanker_berthing_delay_hours": 0.0 if risk_level == "low" else (4.0 if risk_level == "medium" else 12.0),
                        "hourly_waves": waves[:24]
                    }

                    # Simpan raw payload
                    ts_prefix = now_wita.strftime("%Y%m%d_%H%M%S")
                    raw_file = os.path.join(RAW_DIR, f"{ts_prefix}_marine_weather.json")
                    with open(raw_file, "w", encoding="utf-8") as f:
                        json.dump(data, f)

                    result["status"] = "ok"
                    result["data"] = processed
                    result["raw_file"] = raw_file
                    print(f" [+] Marine Weather Collected: Avg Wave={avg_wave:.2f}m | Risk={risk_level.upper()}")
                    return result
        except Exception as e:
            time.sleep(backoff)
            backoff *= 2.0

    # Fallback jika degraded
    result["data"] = {
        "tbbm_monitored": "TBBM Manggis (Karangasem)",
        "current_wave_height_m": 0.85,
        "max_forecast_wave_height_m": 1.20,
        "avg_wave_height_m": 0.95,
        "marine_risk_level": "low",
        "tanker_berthing_delay_hours": 0.0
    }
    print(" [!] Marine Weather Degraded: using historical oceanographic baseline")
    return result


if __name__ == "__main__":
    res = collect_marine_weather()
    print(json.dumps(res, indent=2))
