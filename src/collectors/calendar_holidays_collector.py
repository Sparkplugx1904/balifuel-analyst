"""
Calendar, Holidays & Balinese Ceremonial Cycle Collector: Bali Fuel Crisis Analyst
Kategori: D. Pendorong Permintaan (SRC-011 & SRC-020) & J. Sumber Tak Terduga (SRC-038)
Menghitung kalender libur nasional, siklus upacara adat Bali (Purnama, Tilem, Odalan),
pengali akhir pekan, dan kedekatan tanggal gajian komuter.
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")

# Kalender Upacara Adat & Hari Libur Bali Sekitar Periode Krisis Oktober 2026
BALI_CEREMONIAL_CALENDAR = [
    {"name": "Purnama Sasih Kapat", "date": "2026-10-10", "type": "agama", "demand_impact": "high"},
    {"name": "Penyucian Pura Besakih", "date": "2026-10-12", "type": "adat", "demand_impact": "high"},
    {"name": "Hari Kerja Normal", "date": "2026-10-15", "type": "kerja", "demand_impact": "normal"},
    {"name": "Akhir Pekan Wisata", "date": "2026-10-17", "type": "weekend", "demand_impact": "very_high"},
    {"name": "Tilem Sasih Kapat", "date": "2026-10-25", "type": "agama", "demand_impact": "high"}
]


def collect_calendar_features() -> Dict[str, Any]:
    os.makedirs(RAW_DIR, exist_ok=True)
    now_wita = datetime.now(WITA_TZ)
    cur_date_str = now_wita.strftime("%Y-%m-%d")
    day_of_week = now_wita.weekday()  # 0=Monday, 6=Sunday
    day_name = now_wita.strftime("%A")
    day_of_month = now_wita.day

    # 1. Day of week demand factor (Jumat & Sabtu paling boros bensin di Bali)
    # 0(Mon): 1.0, 1(Tue): 0.95, 2(Wed): 0.98, 3(Thu): 1.02, 4(Fri): 1.22, 5(Sat): 1.28, 6(Sun): 1.15
    dow_multipliers = [1.00, 0.95, 0.98, 1.02, 1.22, 1.28, 1.15]
    dow_mult = dow_multipliers[day_of_week]

    # 2. Payday proximity (tanggal 25 s/d 5 = likuiditas warga tinggi)
    is_payday_window = (day_of_month >= 25 or day_of_month <= 5)
    payday_mult = 1.10 if is_payday_window else 1.00

    # 3. Ceremonial / Holiday factor
    active_event = None
    min_days_to_ceremony = 99
    for event in BALI_CEREMONIAL_CALENDAR:
        event_dt = datetime.strptime(event["date"], "%Y-%m-%d").date()
        diff_days = abs((event_dt - now_wita.date()).days)
        if diff_days < min_days_to_ceremony:
            min_days_to_ceremony = diff_days
            active_event = event

    ceremony_mult = 1.15 if min_days_to_ceremony <= 2 else 1.0

    # Total combined temporal demand multiplier
    total_temporal_multiplier = round(dow_mult * payday_mult * ceremony_mult, 3)

    processed = {
        "current_date": cur_date_str,
        "day_name": day_name,
        "day_of_week_idx": day_of_week,
        "day_of_week_multiplier": dow_mult,
        "is_weekend": day_of_week in [4, 5, 6],
        "is_payday_window": is_payday_window,
        "payday_multiplier": payday_mult,
        "nearest_ceremony_event": active_event["name"] if active_event else "Normal",
        "days_to_nearest_ceremony": min_days_to_ceremony,
        "ceremonial_demand_multiplier": ceremony_mult,
        "total_temporal_demand_multiplier": total_temporal_multiplier
    }

    # Simpan raw snapshot
    ts_prefix = now_wita.strftime("%Y%m%d_%H%M%S")
    raw_file = os.path.join(RAW_DIR, f"{ts_prefix}_calendar_demand.json")
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(processed, f, indent=2)

    result = {
        "collector": "calendar_holidays_collector",
        "timestamp_wita": now_wita.strftime("%Y-%m-%d %H:%M:%S WITA"),
        "status": "ok",
        "data": processed,
        "raw_file": raw_file
    }
    print(f" [+] Calendar Collector Completed: Day={day_name} | Temporal Multiplier={total_temporal_multiplier}x")
    return result


if __name__ == "__main__":
    res = collect_calendar_features()
    print(json.dumps(res, indent=2))
