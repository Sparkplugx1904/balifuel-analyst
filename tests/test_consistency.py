"""
Automated Consistency & Verification Test Suite: BaliFuel Analyst
Wajib dijalankan sebelum setiap publish; publish DIBATALKAN bila ada tes gagal.
"""

import os
import sys
import json
import pytest
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.consistency import check_data_consistency, generate_prediction_scorecard
from src.accuracy_gates import evaluate_accuracy_gates
from src.text_inbox import sanitize_pii


def test_data_consistency_axioms():
    res = check_data_consistency()
    assert res["status"] == "PASSED", f"Consistency check failed: {res['issues_found']}"
    assert res["total_checks"] >= 5


def test_single_source_of_truth_mc():
    mc_path = os.path.join(BASE_DIR, "data", "clean", "monte_carlo_results.json")
    assert os.path.exists(mc_path)
    with open(mc_path, "r", encoding="utf-8") as f:
        mc = json.load(f)

    # Pastikan kuantil berurutan
    p10 = mc["credible_intervals"]["ci_80"]["hours_range"][0]
    p50 = mc["median_recovery_hours"]
    p90 = mc["credible_intervals"]["ci_80"]["hours_range"][1]
    assert p10 <= p50 <= p90, f"Quantiles out of order: {p10} <= {p50} <= {p90}"


def test_accuracy_gates_evaluation():
    gates_res = evaluate_accuracy_gates()
    assert gates_res["status_keyakinan"] in ["TINGGI", "SEDANG"]
    assert "gates" in gates_res
    # G3 coverage harus dalam 70-90%
    assert 70.0 <= gates_res["gates"]["G3_interval_80_coverage"]["coverage_pct"] <= 90.0


def test_queue_scale_allows_extreme_wait():
    st_fc_path = os.path.join(BASE_DIR, "data", "clean", "station_forecasts.json")
    assert os.path.exists(st_fc_path)
    with open(st_fc_path, "r", encoding="utf-8") as f:
        st_fc = json.load(f)

    # Harus ada SPBU yang mencatat antrean jam sibuk >= 240 menit (4 jam)
    all_q = []
    for s_id, s in st_fc["stations_forecast"].items():
        all_q.extend(s.get("queue_traj_mins", []))
    max_q = max(all_q)
    assert max_q >= 240.0, f"Max projected queue ({max_q} mins) is unrealistically low during crisis"


def test_recovery_date_logic():
    mc_path = os.path.join(BASE_DIR, "data", "clean", "monte_carlo_results.json")
    with open(mc_path, "r", encoding="utf-8") as f:
        mc = json.load(f)
    med_h = mc.get("median_recovery_hours", 0.0)
    # Di tengah krisis pulau, waktu pemulihan tidak mungkin < 72 jam
    assert med_h >= 72.0, f"Median recovery hours ({med_h}h) is unrealistically fast"


def test_zero_pii_sanitization():
    raw_text = "Hubungi saya di 081234567890 atau @wayan_bali plat DK 4321 XY bensin habis di SPBU"
    cleaned = sanitize_pii(raw_text)
    assert "081234567890" not in cleaned
    assert "@wayan_bali" not in cleaned
    assert "DK 4321 XY" not in cleaned
    assert "[TELP]" in cleaned
    assert "[USER]" in cleaned
    assert "[PLAT]" in cleaned


def test_prediction_scorecard_validity():
    scorecard = generate_prediction_scorecard()
    assert scorecard["akurasi_keseluruhan_pct"] > 50.0
    assert len(scorecard["evaluasi_terakhir"]) >= 3
    assert os.path.exists(os.path.join(BASE_DIR, "data", "clean", "rapor_prediksi.json"))
