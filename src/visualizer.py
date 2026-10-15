"""
Visualizer Module: Generator Grafik per SPBU (SVG/PNG)
Menghasilkan grafik visual mandiri untuk SPBU di Bali:
- Peluang ada BBM 72 jam ke depan
- Pita ketidakpastian (P10 - P90)
- Proyeksi antrean (menit)
- Indikator status terkini & estimasi waktu pemulihan
"""

import os
import sys
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
CLEAN_DIR = os.path.join(DATA_DIR, "clean")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SPBU_DIR = os.path.join(OUTPUT_DIR, "spbu")


def generate_spbu_charts(limit: int = None, format_ext: str = "svg"):
    os.makedirs(SPBU_DIR, exist_ok=True)
    
    with open(os.path.join(CLEAN_DIR, "station_forecasts.json"), "r", encoding="utf-8") as f:
        forecast_data = json.load(f)
    with open(os.path.join(CLEAN_DIR, "cleaned_stations.json"), "r", encoding="utf-8") as f:
        stations = json.load(f)

    st_map = {s["id"]: s for s in stations}
    st_forecasts = forecast_data["stations_forecast"]
    hours_label = forecast_data["hours_label"]

    # Filter: prioritas SPBU resmi Pertamina (212) + hotspot
    target_ids = []
    for s_id_str, fc in st_forecasts.items():
        s_id = int(s_id_str)
        st = st_map.get(s_id, {})
        if st.get("kind") == "spbu" or fc.get("vulnerability_score", 0) >= 75.0:
            target_ids.append(s_id)

    if limit:
        target_ids = target_ids[:limit]

    print(f"[*] Generating {len(target_ids)} visual charts in output/spbu/ (Format: {format_ext})...")

    # Matplotlib styling for dark/clean aesthetic
    plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Helvetica", "Arial"]
    plt.rcParams["axes.edgecolor"] = "#334155"
    plt.rcParams["axes.linewidth"] = 0.8

    generated_count = 0
    for s_id in target_ids:
        fc = st_forecasts.get(str(s_id))
        st = st_map.get(s_id, {})
        if not fc:
            continue

        name = st.get("name") or f"SPBU {s_id}"
        area = st.get("area") or "Bali"
        code = st.get("code") or "-"
        p0 = fc["current_p_pertalite"]
        recov_date = fc["estimated_recovery_datetime_wita"]
        vuln = fc["vulnerability_score"]
        dist = fc["distance_to_terminal_km"]

        p50 = np.array(fc["p50_traj"]) * 100.0
        p10 = np.array(fc["p10_traj"]) * 100.0
        p90 = np.array(fc["p90_traj"]) * 100.0
        queue_traj = np.array(fc["queue_traj_mins"])

        x = np.arange(len(p50))

        # Create dual-panel figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.0]})
        fig.patch.set_facecolor("#0f172a")
        ax1.set_facecolor("#1e293b")
        ax2.set_facecolor("#1e293b")

        # Color based on current probability
        if p0 >= 0.70:
            status_color = "#22c55e"  # Green
            status_text = "Kemungkinan Stok Tersedia"
        elif p0 >= 0.40:
            status_color = "#f59e0b"  # Amber
            status_text = "Pasokan Kritis / Menipis"
        else:
            status_color = "#ef4444"  # Red
            status_text = "Stok Kosong / Antrean Bubar"

        # Panel 1: Probability trajectory & Uncertainty band
        ax1.fill_between(x, p10, p90, color="#38bdf8", alpha=0.22, label="Pita Ketidakpastian 80% (P10 - P90)")
        ax1.plot(x, p50, color="#38bdf8", linewidth=2.5, label="Median Peluang Stok Ada (P50)")
        ax1.axhline(90.0, color="#22c55e", linestyle="--", linewidth=1.2, alpha=0.7, label="Ambang Pulih Normal (90%)")
        ax1.axhline(50.0, color="#64748b", linestyle=":", linewidth=0.8, alpha=0.5)

        ax1.set_ylabel("Peluang Ada Stok (%)", color="#f8fafc", fontsize=11, fontweight="bold")
        ax1.set_ylim(0, 105)
        ax1.tick_params(colors="#94a3b8", labelsize=9)
        ax1.grid(True, linestyle="--", alpha=0.15, color="#94a3b8")
        ax1.legend(loc="lower right", facecolor="#0f172a", edgecolor="#334155", labelcolor="#f8fafc", fontsize=8.5)

        # Title and metadata header
        title_str = f"SPBU {s_id}: {name} ({area})"
        fig.suptitle(title_str, color="#f8fafc", fontsize=14, fontweight="bold", y=0.98)
        subtitle = (
            f"Kode: {code} | Status Awal: {p0*100:.0f}% ({status_text}) | "
            f"Jarak TBBM: {dist:.1f} km | Estimasi Pulih: {recov_date}"
        )
        ax1.set_title(subtitle, color="#94a3b8", fontsize=9.5, pad=8)

        # Panel 2: Queue time forecast
        ax2.plot(x, queue_traj, color="#f59e0b", linewidth=2.0, label="Estimasi Waktu Tunggu Antrean")
        ax2.fill_between(x, 0, queue_traj, color="#f59e0b", alpha=0.15)
        ax2.axhline(20.0, color="#ef4444", linestyle=":", linewidth=1.0, alpha=0.6, label="Batas Antrean Panjang (20 mnt)")
        ax2.set_ylabel("Antrean (Menit)", color="#f8fafc", fontsize=10, fontweight="bold")
        ax2.set_xlabel("Waktu (WITA)", color="#f8fafc", fontsize=10, fontweight="bold")
        ax2.set_ylim(0, max(45.0, np.max(queue_traj) * 1.25))
        ax2.tick_params(colors="#94a3b8", labelsize=9)
        ax2.grid(True, linestyle="--", alpha=0.15, color="#94a3b8")
        ax2.legend(loc="upper right", facecolor="#0f172a", edgecolor="#334155", labelcolor="#f8fafc", fontsize=8.5)

        # X-axis ticks every 12 hours
        tick_indices = np.arange(0, len(x), 12)
        ax2.set_xticks(tick_indices)
        ax2.set_xticklabels([hours_label[i] for i in tick_indices], rotation=0, color="#94a3b8")

        # Footnote
        fig.text(0.5, 0.01, "Model Markov & Logistik BBM Bali · BaliFuel Crisis Analytics 2026",
                 ha="center", color="#64748b", fontsize=8)

        plt.tight_layout(rect=[0, 0.02, 1, 0.95])

        out_name = f"spbu_{s_id}.{format_ext}"
        out_file = os.path.join(SPBU_DIR, out_name)
        plt.savefig(out_file, dpi=130, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)
        generated_count += 1

    print(f"[+] Successfully generated {generated_count} charts in {SPBU_DIR}.")
    return generated_count


if __name__ == "__main__":
    generate_spbu_charts(limit=None, format_ext="svg")
