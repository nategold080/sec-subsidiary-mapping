"""Load cached recall data and fetch remaining makes.

Usage: python -m scripts.load_recalls [--fetch-remaining]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.scrapers.recalls import fetch_recalls_bulk, CACHE_DIR
from src.normalization.vehicles import normalize_make, normalize_model, MAJOR_MAKES
from src.normalization.cross_linker import cross_link_all
from src.validation.quality import score_recall
from src.storage.database import get_connection, init_db, upsert_recall, upsert_vehicle


def load_cached_recalls(conn):
    """Load all cached recall JSON files into the database."""
    cache_dir = CACHE_DIR
    if not cache_dir.exists():
        print("No cache directory found")
        return 0

    total = 0
    seen = set()
    for f in sorted(cache_dir.glob("recalls_*.json")):
        with open(f) as fh:
            data = json.load(fh)
        for rec in data:
            if rec["campaign_number"] in seen:
                continue
            seen.add(rec["campaign_number"])
            qs = score_recall(rec)
            rec["quality_score"] = qs.score
            upsert_recall(conn, rec)
            upsert_vehicle(conn, rec["make"], rec["model"],
                           normalize_make(rec["make"]), normalize_model(rec["model"]))
            total += 1
        print(f"  Loaded {f.name}: {len(data)} recalls")

    conn.commit()
    return total


def fetch_remaining(conn):
    """Fetch recalls for makes not yet cached."""
    years = list(range(2015, 2027))

    # Find which makes are already fully cached
    cached_makes = set()
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("recalls_*.json"):
            parts = f.stem.split("_")
            if len(parts) >= 3:
                make = "_".join(parts[1:-1])  # Handle makes with underscores
                cached_makes.add(make)

    # Check which makes have all years cached
    fully_cached = set()
    for make in MAJOR_MAKES:
        all_years = all(
            (CACHE_DIR / f"recalls_{make}_{y}.json").exists()
            for y in years
        )
        if all_years:
            fully_cached.add(make)

    remaining = [m for m in MAJOR_MAKES if m not in fully_cached]
    if not remaining:
        print("All makes fully cached!")
        return 0

    print(f"Fetching {len(remaining)} remaining makes: {', '.join(remaining[:10])}...")

    def progress(done, total, msg):
        if done % 5 == 0 or done == total:
            print(f"  {done}/{total}: {msg}")

    results = fetch_recalls_bulk(remaining, years, progress_callback=progress)
    print(f"Fetched {len(results)} unique recall campaigns")

    # Load into database
    total = 0
    for rec in results:
        qs = score_recall(rec)
        rec["quality_score"] = qs.score
        upsert_recall(conn, rec)
        upsert_vehicle(conn, rec["make"], rec["model"],
                       normalize_make(rec["make"]), normalize_model(rec["model"]))
        total += 1
    conn.commit()
    return total


def main():
    conn = get_connection()
    init_db(conn)

    # Step 1: Load whatever is cached
    print("=== Loading cached recalls ===")
    cached_count = load_cached_recalls(conn)
    print(f"Loaded {cached_count} cached recalls into database\n")

    # Step 2: Fetch remaining makes
    if "--fetch-remaining" in sys.argv or "--fetch" in sys.argv:
        print("=== Fetching remaining recalls from API ===")
        new_count = fetch_remaining(conn)
        print(f"Loaded {new_count} new recalls\n")

    # Step 3: Re-run cross-linking
    print("=== Re-running cross-linking ===")
    # Clear old recall-related cross-links first
    conn.execute("DELETE FROM cross_links WHERE target_type = 'recall' OR source_type = 'recall'")
    conn.commit()

    results = cross_link_all(conn)
    for link_type, count in results.items():
        print(f"  {link_type}: {count:,} links")

    # Print final stats
    complaint_count = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    recall_count = conn.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
    inv_count = conn.execute("SELECT COUNT(*) FROM investigations").fetchone()[0]
    cross_count = conn.execute("SELECT COUNT(*) FROM cross_links").fetchone()[0]
    vehicle_count = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]

    print(f"\n=== Final Stats ===")
    print(f"  Complaints:    {complaint_count:,}")
    print(f"  Recalls:       {recall_count:,}")
    print(f"  Investigations: {inv_count:,}")
    print(f"  Cross-links:   {cross_count:,}")
    print(f"  Vehicles:      {vehicle_count:,}")

    conn.close()


if __name__ == "__main__":
    main()
