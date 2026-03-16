"""Load OSHA inspection data from raw JSON API pages into main DB."""

import json
import glob
import re
import sqlite3
import sys
from pathlib import Path

PROJECT = Path(__file__).parent.parent
MAIN_DB = PROJECT / "data" / "labor_compliance.db"
OSHA_DIR = PROJECT / "data" / "raw" / "osha"

_SUFFIXES = re.compile(
    r'\b(LLC|INC|CORP|CO|LTD|LP|LLP|PC|PA|PLLC|NA|DBA|GROUP|COMPANY|CORPORATION|INCORPORATED|LIMITED|ENTERPRISES|HOLDINGS)\b\.?',
    re.IGNORECASE,
)
_MULTI_SPACE = re.compile(r'\s+')


def normalize_name(name):
    if not name:
        return ""
    n = name.upper().strip()
    for sep in [" D/B/A ", " DBA ", " D.B.A. ", " T/A ", " AKA "]:
        if sep in n:
            n = n.split(sep)[0]
    n = _SUFFIXES.sub("", n)
    n = re.sub(r'[^\w\s]', ' ', n)
    n = _MULTI_SPACE.sub(' ', n).strip()
    return n


def normalize_date(val):
    if not val:
        return ""
    val = str(val).strip()
    if "T" in val:
        return val.split("T")[0]
    return val[:10] if len(val) >= 10 else val


def load_osha(main_conn, min_year=2005):
    """Load OSHA inspections from raw JSON API pages."""
    files = sorted(glob.glob(str(OSHA_DIR / "insp_*.json")))
    if not files:
        print("No OSHA JSON files found.")
        return 0

    print(f"Loading OSHA from {len(files)} JSON files...")

    main_conn.execute("DELETE FROM osha_inspections")
    batch = []

    for i, f in enumerate(files):
        data = json.load(open(f))
        for r in data:
            open_date = normalize_date(r.get("open_date"))
            if open_date:
                try:
                    year = int(open_date[:4])
                    if year < min_year:
                        continue
                except (ValueError, IndexError):
                    pass

            activity = r.get("activity_nr")
            if activity is None:
                continue

            estab = (r.get("estab_name") or "").strip()
            emp_norm = normalize_name(estab)

            batch.append((
                str(activity),
                (r.get("reporting_id") or "").strip(),
                estab,
                (r.get("site_address") or "").strip(),
                (r.get("site_city") or "").strip(),
                (r.get("site_state") or "").strip(),
                (r.get("site_zip") or "").strip(),
                (r.get("naics_code") or "").strip(),
                (r.get("sic_code") or "").strip(),
                (r.get("insp_type") or "").strip(),
                open_date,
                normalize_date(r.get("close_case_date")),
                0.0,  # total_initial_penalty (no violation data)
                0.0,  # total_current_penalty
                0,    # num_violations
                0,    # serious_violations
                0,    # willful_violations
                0,    # repeat_violations
                0,    # fatalities
                0,    # hospitalized
                emp_norm,
                0.80,
            ))

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(files)} files ({len(batch):,} records so far)")

    print(f"  Inserting {len(batch):,} OSHA inspections...")
    main_conn.executemany("""
        INSERT OR REPLACE INTO osha_inspections
        (activity_number, reporting_id, establishment_name, site_address, site_city,
         site_state, site_zip, naics_code, sic_code, inspection_type,
         open_date, close_date, total_initial_penalty, total_current_penalty,
         num_violations, serious_violations, willful_violations, repeat_violations,
         fatalities, hospitalized, employer_normalized, quality_score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, batch)
    main_conn.commit()
    print(f"  Loaded {len(batch):,} OSHA inspections.")
    return len(batch)


def rebuild_employers(main_conn):
    """Rebuild employer profiles with all three sources."""
    print("Rebuilding employer profiles...")
    main_conn.execute("DELETE FROM employers")
    main_conn.execute("""
        INSERT INTO employers (name_normalized, primary_state, whd_case_count, osha_inspection_count,
                              nlrb_case_count, total_back_wages, total_penalties, total_fatalities, compliance_score)
        SELECT
            emp_name,
            MAX(state) as primary_state,
            SUM(whd_count) as whd_cases,
            SUM(osha_count) as osha_inspections,
            SUM(nlrb_count) as nlrb_cases,
            SUM(back_wages) as total_bw,
            SUM(penalties) as total_pen,
            SUM(fatalities) as total_fat,
            0.5 as compliance_score
        FROM (
            SELECT employer_normalized as emp_name, state, COUNT(*) as whd_count, 0 as osha_count, 0 as nlrb_count,
                   SUM(back_wages_owed) as back_wages, SUM(civil_penalties) as penalties, 0 as fatalities
            FROM whd_cases WHERE employer_normalized != ''
            GROUP BY employer_normalized, state
            UNION ALL
            SELECT employer_normalized as emp_name, site_state as state, 0 as whd_count, COUNT(*) as osha_count, 0 as nlrb_count,
                   0 as back_wages, SUM(total_current_penalty) as penalties, SUM(fatalities) as fatalities
            FROM osha_inspections WHERE employer_normalized != ''
            GROUP BY employer_normalized, site_state
            UNION ALL
            SELECT employer_normalized as emp_name, state, 0 as whd_count, 0 as osha_count, COUNT(*) as nlrb_count,
                   0 as back_wages, 0 as penalties, 0 as fatalities
            FROM nlrb_cases WHERE employer_normalized != ''
            GROUP BY employer_normalized, state
        )
        GROUP BY emp_name
    """)
    main_conn.commit()

    emp_count = main_conn.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
    multi = main_conn.execute("""
        SELECT COUNT(*) FROM employers
        WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
    """).fetchone()[0]
    three = main_conn.execute("""
        SELECT COUNT(*) FROM employers
        WHERE whd_case_count > 0 AND osha_inspection_count > 0 AND nlrb_case_count > 0
    """).fetchone()[0]
    print(f"  {emp_count:,} employer profiles, {multi:,} multi-agency, {three:,} all-3-agency")
    return emp_count


def main():
    print(f"Main DB: {MAIN_DB}")
    main_conn = sqlite3.connect(str(MAIN_DB))
    main_conn.execute("PRAGMA journal_mode=WAL")

    osha_count = load_osha(main_conn)
    rebuild_employers(main_conn)

    print("\n=== FINAL STATS ===")
    for table in ['whd_cases', 'osha_inspections', 'nlrb_cases', 'employers', 'cross_links']:
        c = main_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {c:,}")

    main_conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
