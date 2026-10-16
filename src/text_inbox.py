"""
Manual Social Inbox Ingestion Module: BaliFuel Analyst
Membaca file CSV komentar publik dari data/inbox/sosial/*.csv:
- Sanitasi PII (Zero-PII: menghapus @username, nomor telepon, plat kendaraan)
- Deduplikasi pesan berulang dengan hash SHA-256 satu arah
- Menghasilkan koleksi komentar bersih terstandardisasi
"""

import os
import sys
import glob
import re
import hashlib
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

WITA_TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX_DIR = os.path.join(BASE_DIR, "data", "inbox", "sosial")


def sanitize_pii(text: str) -> str:
    """Menghapus PII: username, no telp, plat nomor, email."""
    if not isinstance(text, str):
        return ""
    # Hapus @mentions
    s = re.sub(r"@[\w\d_.]+", "[USER]", text)
    # Hapus nomor telepon / nomor panjang
    s = re.sub(r"\b(\+62|62|08)[\d\s-]{8,13}\b", "[TELP]", s)
    # Hapus plat nomor kendaraan (misal DK 1234 AB)
    s = re.sub(r"\b[A-Z]{1,2}\s*\d{1,4}\s*[A-Z]{1,3}\b", "[PLAT]", s)
    # Hapus email
    s = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", "[EMAIL]", s)
    # Hapus URL panjang
    s = re.sub(r"https?://\S+", "", s)
    return s.strip()


def compute_content_hash(text: str) -> str:
    """Menghasilkan hash 16-hex untuk deduplikasi tanpa menyimpan identitas."""
    cleaned = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


def load_manual_inbox() -> List[Dict[str, Any]]:
    """Membaca semua CSV di data/inbox/sosial/*.csv (kecuali TEMPLATE.csv)."""
    if not os.path.exists(INBOX_DIR):
        return []

    csv_files = glob.glob(os.path.join(INBOX_DIR, "*.csv"))
    valid_records = []
    seen_hashes = set()

    for fp in sorted(csv_files):
        # Lewati template murni bila tidak diisi laporan baru
        try:
            df = pd.read_csv(fp)
            req_cols = {"platform", "url_postingan", "tanggal", "teks_komentar", "suka"}
            if not req_cols.issubset(set(df.columns)):
                continue

            for _, row in df.iterrows():
                raw_text = str(row.get("teks_komentar", ""))
                clean_text = sanitize_pii(raw_text)
                if len(clean_text) < 5:
                    continue

                c_hash = compute_content_hash(clean_text)
                if c_hash in seen_hashes:
                    continue  # Deduplikasi
                seen_hashes.add(c_hash)

                likes = int(row.get("suka", 0)) if pd.notnull(row.get("suka")) else 0
                platform = str(row.get("platform", "Sosial")).strip()
                date_str = str(row.get("tanggal", "")).strip()

                valid_records.append({
                    "hash_id": c_hash,
                    "platform": platform,
                    "date_str": date_str,
                    "clean_text": clean_text,
                    "likes": likes
                })
        except Exception as e:
            print(f" [!] Inbox warning reading {os.path.basename(fp)}: {e}")

    return valid_records


if __name__ == "__main__":
    records = load_manual_inbox()
    print(f"Loaded {len(records)} verified comments from manual inbox.")
