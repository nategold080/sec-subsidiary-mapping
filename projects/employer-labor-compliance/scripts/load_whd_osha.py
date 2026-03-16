"""Quick ETL: Load WHD and OSHA data from labordata SQLite dumps into main DB."""

import sqlite3
import sys
import os
from pathlib import Path

PROJECT = Path(__file__).parent.parent
MAIN_DB = PROJECT / "data" / "labor_compliance.db"
WHD_DB = PROJECT / "data" / "raw" / "whisard.db"
OSHA_DB = PROJECT / "data" / "raw" / "osha_enforcement.db"

# Simple employer name normalization
import re

_SUFFIXES = re.compile(
    r'\b(LLC|INC|CORP|CO|LTD|LP|LLP|PC|PA|PLLC|NA|DBA|GROUP|COMPANY|CORPORATION|INCORPORATED|LIMITED|ENTERPRISES|HOLDINGS)\b\.?',
    re.IGNORECASE,
)
_MULTI_SPACE = re.compile(r'\s+')


def normalize_name(name):
    if not name:
        return ""
    n = name.upper().strip()
    # Remove DBA portion
    for sep in [" D/B/A ", " DBA ", " D.B.A. ", " T/A ", " AKA "]:
        if sep in n:
            n = n.split(sep)[0]
    n = _SUFFIXES.sub("", n)
    n = re.sub(r'[^\w\s]', ' ', n)
    n = _MULTI_SPACE.sub(' ', n).strip()
    return n


def load_whd(main_conn):
    """Load WHD cases from whisard.db into main database."""
    if not WHD_DB.exists():
        print("WHD database not found, skipping.")
        return 0

    print(f"Loading WHD data from {WHD_DB}...")
    whd = sqlite3.connect(str(WHD_DB))

    # Get cases with violation type breakdown
    rows = whd.execute("""
        SELECT
            c.case_id,
            COALESCE(c.trade_nm, c.legal_name, '') as trade_name,
            COALESCE(c.legal_name, c.trade_nm, '') as legal_name,
            COALESCE(c.street_addr_1_txt, '') as street,
            COALESCE(c.cty_nm, '') as city,
            COALESCE(c.st_cd, '') as state,
            COALESCE(c.zip_cd, '') as zip,
            COALESCE(c.naic_cd, '') as naics,
            COALESCE(c.naics_code_description, '') as naics_desc,
            COALESCE(c.findings_start_date, '') as start_date,
            COALESCE(c.findings_end_date, '') as end_date,
            COALESCE(c.bw_atp_amt, 0) as back_wages,
            COALESCE(c.cmp_assd, 0) as penalties,
            COALESCE(c.ee_atp_cnt, 0) as employees,
            -- Violation flags from violations table
            COALESCE((SELECT SUM(CASE WHEN v.type='flsa' THEN 1 ELSE 0 END) FROM violations v WHERE v.case_id=c.case_id), 0) as flsa,
            COALESCE((SELECT SUM(CASE WHEN v.type='mspa' THEN 1 ELSE 0 END) FROM violations v WHERE v.case_id=c.case_id), 0) as mspa,
            COALESCE((SELECT SUM(CASE WHEN v.type='h1b' THEN 1 ELSE 0 END) FROM violations v WHERE v.case_id=c.case_id), 0) as h1b,
            COALESCE((SELECT SUM(CASE WHEN v.type='fmla' THEN 1 ELSE 0 END) FROM violations v WHERE v.case_id=c.case_id), 0) as fmla,
            COALESCE((SELECT SUM(CASE WHEN v.type IN ('sca','cwhssa') THEN 1 ELSE 0 END) FROM violations v WHERE v.case_id=c.case_id), 0) as sca,
            COALESCE((SELECT SUM(CASE WHEN v.type IN ('dbra') THEN 1 ELSE 0 END) FROM violations v WHERE v.case_id=c.case_id), 0) as dba
        FROM cases c
        WHERE c.findings_start_date >= '2005-01-01'
        AND c.findings_start_date <= '2026-01-01'
    """).fetchall()

    print(f"  Processing {len(rows):,} WHD cases...")

    # Clear existing and insert
    main_conn.execute("DELETE FROM whd_cases")
    batch = []
    for r in rows:
        emp_norm = normalize_name(r[1] if r[1] else r[2])
        batch.append((
            str(r[0]),       # case_id
            r[1],            # trade_name
            r[2],            # legal_name
            r[3],            # street
            r[4],            # city
            r[5],            # state
            str(r[6]),       # zip
            r[7],            # naics
            r[8],            # naics_desc
            r[9],            # start_date
            r[10],           # end_date
            float(r[11] or 0),  # back_wages
            float(r[12] or 0),  # penalties
            int(r[13] or 0),    # employees
            1 if r[14] > 0 else 0,  # flsa
            1 if r[15] > 0 else 0,  # mspa
            1 if r[16] > 0 else 0,  # h1b
            1 if r[17] > 0 else 0,  # fmla
            1 if r[18] > 0 else 0,  # sca
            1 if r[19] > 0 else 0,  # dba
            emp_norm,
            0.85,  # quality score (good data)
        ))

    main_conn.executemany("""
        INSERT OR REPLACE INTO whd_cases
        (case_id, trade_name, legal_name, street_address, city, state, zip_code,
         naics_code, naics_description, findings_start_date, findings_end_date,
         back_wages_owed, civil_penalties, employees_affected,
         flsa_violated, mspa_violated, h1b_violated, fmla_violated, sca_violated, dba_violated,
         employer_normalized, quality_score)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, batch)
    main_conn.commit()

    whd.close()
    print(f"  Loaded {len(batch):,} WHD cases.")
    return len(batch)


def load_osha(main_conn):
    """Load OSHA inspections from osha_enforcement.db into main database."""
    if not OSHA_DB.exists():
        print("OSHA database not found, skipping.")
        return 0

    print(f"Loading OSHA data from {OSHA_DB}...")
    osha = sqlite3.connect(str(OSHA_DB))

    count = osha.execute("SELECT COUNT(*) FROM inspection WHERE open_date >= '2015-01-01'").fetchone()[0]
    print(f"  Inspections 2015+: {count:,}")

    # Get violation summary per inspection (penalties + counts by type)
    print("  Aggregating violation data...")
    viol_counts = {}
    viol_rows = osha.execute("""
        SELECT activity_nr,
               SUM(CASE WHEN viol_type = 'S' THEN 1 ELSE 0 END) as serious,
               SUM(CASE WHEN viol_type = 'W' THEN 1 ELSE 0 END) as willful,
               SUM(CASE WHEN viol_type = 'R' THEN 1 ELSE 0 END) as repeat_v,
               COUNT(*) as total,
               COALESCE(SUM(current_penalty), 0) as cur_pen,
               COALESCE(SUM(initial_penalty), 0) as init_pen
        FROM violation
        GROUP BY activity_nr
    """).fetchall()
    for vr in viol_rows:
        viol_counts[vr[0]] = (vr[1], vr[2], vr[3], vr[4], vr[5], vr[6])
    print(f"  Loaded violation data for {len(viol_counts):,} inspections")

    # Get fatality counts from accident_injury table
    print("  Loading fatality data from accident_injury...")
    fatality_counts = {}
    try:
        fat_rows = osha.execute("""
            SELECT rel_insp_nr, COUNT(*) as fatalities
            FROM accident_injury
            WHERE degree_of_inj = 1
            GROUP BY rel_insp_nr
        """).fetchall()
        for fr in fat_rows:
            fatality_counts[fr[0]] = fr[1]
        print(f"  Fatality data for {len(fatality_counts):,} inspections")
    except Exception as e:
        print(f"  Could not load fatality data: {e}")

    # Load inspections
    rows = osha.execute("""
        SELECT activity_nr, COALESCE(estab_name, ''), COALESCE(site_address, ''),
               COALESCE(site_city, ''), COALESCE(site_state, ''), COALESCE(site_zip, ''),
               COALESCE(naics_code, ''), COALESCE(sic_code, ''), COALESCE(insp_type, ''),
               COALESCE(open_date, ''), COALESCE(close_case_date, '')
        FROM inspection
        WHERE open_date >= '2015-01-01'
    """).fetchall()
    print(f"  Fetched {len(rows):,} OSHA inspections (2015+)")

    main_conn.execute("DELETE FROM osha_inspections")
    batch = []
    for r in rows:
        activity = r[0]
        emp_norm = normalize_name(r[1])
        vc = viol_counts.get(activity, (0, 0, 0, 0, 0, 0))
        fat = fatality_counts.get(activity, 0)
        batch.append((
            str(activity),
            '',              # reporting_id
            r[1],            # establishment_name
            r[2],            # site_address
            r[3],            # site_city
            r[4],            # site_state
            str(r[5]),       # site_zip
            str(r[6]),       # naics_code
            str(r[7]),       # sic_code
            r[8],            # inspection_type
            r[9],            # open_date
            r[10],           # close_date
            float(vc[5] or 0),  # total_initial_penalty
            float(vc[4] or 0),  # total_current_penalty
            int(vc[3]),      # num_violations
            int(vc[0]),      # serious_violations
            int(vc[1]),      # willful_violations
            int(vc[2]),      # repeat_violations
            fat,             # fatalities
            0,               # hospitalized
            emp_norm,
            0.80,
        ))

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
    osha.close()
    print(f"  Loaded {len(batch):,} OSHA inspections.")
    return len(batch)


def rebuild_employers(main_conn):
    """Rebuild employer profiles with all three sources."""
    print("Rebuilding employer profiles...")

    main_conn.execute("DELETE FROM employers")

    # Combine all employer names across sources
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
            -- WHD employers
            SELECT employer_normalized as emp_name, state, COUNT(*) as whd_count, 0 as osha_count, 0 as nlrb_count,
                   SUM(back_wages_owed) as back_wages, SUM(civil_penalties) as penalties, 0 as fatalities
            FROM whd_cases WHERE employer_normalized != ''
            GROUP BY employer_normalized, state

            UNION ALL

            -- OSHA employers
            SELECT employer_normalized as emp_name, site_state as state, 0 as whd_count, COUNT(*) as osha_count, 0 as nlrb_count,
                   0 as back_wages, SUM(total_current_penalty) as penalties, SUM(fatalities) as fatalities
            FROM osha_inspections WHERE employer_normalized != ''
            GROUP BY employer_normalized, site_state

            UNION ALL

            -- NLRB employers
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
    print(f"  {emp_count:,} employer profiles, {multi:,} multi-agency offenders")
    return emp_count


def main():
    print(f"Main DB: {MAIN_DB}")
    main_conn = sqlite3.connect(str(MAIN_DB))
    main_conn.execute("PRAGMA journal_mode=WAL")

    whd_count = load_whd(main_conn)
    osha_count = load_osha(main_conn)
    emp_count = rebuild_employers(main_conn)

    # Print summary
    print("\n=== FINAL STATS ===")
    for table in ['whd_cases', 'osha_inspections', 'nlrb_cases', 'employers', 'cross_links']:
        c = main_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {c:,}")

    main_conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
