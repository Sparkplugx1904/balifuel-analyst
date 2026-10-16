"""
Unit Tests for Plain Language Checker: BaliFuel Analyst
"""

import pytest
from src.plain_language import periksa, bersihkan_teks


def test_deteksi_kata_sulit():
    teks_sulit = "Pasokan bensin dari tanker ke terminal sedang terkendala."
    masalah = periksa(teks_sulit)
    jenis_list = [m["jenis"] for m in masalah]
    assert "kata_sulit" in jenis_list
    assert any(m.get("kata") in ["pasokan", "tanker", "terminal"] for m in masalah)


def test_deteksi_kalimat_terlalu_panjang():
    kalimat_panjang = "Ini adalah kalimat yang sangat panjang sekali karena sengaja ditulis dengan lebih dari delapan belas kata untuk menguji apakah fungsi pemeriksa bahasa awam kami bekerja dengan baik."
    masalah = periksa(kalimat_panjang)
    assert any(m["jenis"] == "kalimat_terlalu_panjang" for m in masalah)


def test_deteksi_satuan_kl():
    teks_kl = "Kapal membawa muatan sebanyak 26.200 KL bensin."
    masalah = periksa(teks_kl)
    assert any(m["jenis"] == "satuan_sulit_kl" for m in masalah)


def test_kalimat_bersih_lolos():
    teks_bersih = "Bensin diperkirakan normal kembali pada Minggu pagi. Truk sudah mulai mengantar bensin ke SPBU."
    masalah = periksa(teks_bersih)
    assert len(masalah) == 0


def test_bersihkan_teks():
    teks_kotor = "Pasokan dari tanker menuju terminal."
    teks_bersih = bersihkan_teks(teks_kotor)
    assert "kiriman" in teks_bersih
    assert "kapal pengangkut bensin" in teks_bersih
    assert "gudang besar bensin" in teks_bersih
