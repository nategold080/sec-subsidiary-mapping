"""Build a compact deploy database for Railway deployment.

Creates data/labor_compliance_deploy.db from the full database,
trimming to fit under 100MB for git while keeping all 3 data sources.
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FULL_DB = PROJECT_ROOT / "data" / "labor_compliance.db"
DEPLOY_DB = PROJECT_ROOT / "data" / "labor_compliance_deploy.db"

# Target max size in MB
MAX_SIZE_MB = 95


def build_deploy_db():
    if not FULL_DB.exists():
        print(f"ERROR: Full database not found at {FULL_DB}")
        return

    for f in [DEPLOY_DB, Path(str(DEPLOY_DB) + "-wal"), Path(str(DEPLOY_DB) + "-shm")]:
        if f.exists():
            f.unlink()

    print(f"Building deploy DB from {FULL_DB} ...")

    conn = sqlite3.connect(str(DEPLOY_DB))
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"ATTACH DATABASE '{FULL_DB}' AS full_db")

    # Create schema (no cross_links — dashboard doesn't query it)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS whd_cases (
            case_id TEXT PRIMARY KEY,
            trade_name TEXT NOT NULL,
            legal_name TEXT,
            street_address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            naics_code TEXT,
            naics_description TEXT,
            findings_start_date TEXT,
            findings_end_date TEXT,
            back_wages_owed REAL DEFAULT 0,
            civil_penalties REAL DEFAULT 0,
            employees_affected INTEGER DEFAULT 0,
            flsa_violated INTEGER DEFAULT 0,
            mspa_violated INTEGER DEFAULT 0,
            h1b_violated INTEGER DEFAULT 0,
            fmla_violated INTEGER DEFAULT 0,
            sca_violated INTEGER DEFAULT 0,
            dba_violated INTEGER DEFAULT 0,
            employer_normalized TEXT,
            quality_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS osha_inspections (
            activity_number TEXT PRIMARY KEY,
            reporting_id TEXT,
            establishment_name TEXT NOT NULL,
            site_address TEXT,
            site_city TEXT,
            site_state TEXT,
            site_zip TEXT,
            naics_code TEXT,
            sic_code TEXT,
            inspection_type TEXT,
            open_date TEXT,
            close_date TEXT,
            total_initial_penalty REAL DEFAULT 0,
            total_current_penalty REAL DEFAULT 0,
            num_violations INTEGER DEFAULT 0,
            serious_violations INTEGER DEFAULT 0,
            willful_violations INTEGER DEFAULT 0,
            repeat_violations INTEGER DEFAULT 0,
            fatalities INTEGER DEFAULT 0,
            hospitalized INTEGER DEFAULT 0,
            employer_normalized TEXT,
            quality_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS nlrb_cases (
            case_number TEXT PRIMARY KEY,
            case_name TEXT NOT NULL,
            date_filed TEXT,
            date_closed TEXT,
            status TEXT,
            case_type TEXT,
            allegation TEXT,
            city TEXT,
            state TEXT,
            num_employees INTEGER DEFAULT 0,
            unit_description TEXT,
            union_name TEXT,
            employer_normalized TEXT,
            quality_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS employers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_normalized TEXT NOT NULL UNIQUE,
            trade_names TEXT,
            naics_code TEXT,
            primary_state TEXT,
            whd_case_count INTEGER DEFAULT 0,
            osha_inspection_count INTEGER DEFAULT 0,
            nlrb_case_count INTEGER DEFAULT 0,
            total_back_wages REAL DEFAULT 0,
            total_penalties REAL DEFAULT 0,
            total_fatalities INTEGER DEFAULT 0,
            compliance_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cross_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            link_method TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source_type, source_id, target_type, target_id)
        );
    """)

    # Copy ALL WHD cases (~7K, tiny)
    conn.execute("INSERT INTO whd_cases SELECT * FROM full_db.whd_cases")
    whd = conn.execute("SELECT COUNT(*) FROM whd_cases").fetchone()[0]
    print(f"  WHD cases: {whd:,}")

    # Copy OSHA inspections 2009+ (overlap with WHD and NLRB eras)
    conn.execute("""
        INSERT INTO osha_inspections
        SELECT * FROM full_db.osha_inspections
        WHERE open_date >= '2009-01-01' OR open_date = '' OR open_date IS NULL
    """)
    osha = conn.execute("SELECT COUNT(*) FROM osha_inspections").fetchone()[0]
    print(f"  OSHA inspections (2009+): {osha:,}")

    # Copy NLRB — last 5 years to save space
    conn.execute("""
        INSERT INTO nlrb_cases
        SELECT * FROM full_db.nlrb_cases
        WHERE date_filed >= '2020-01-01'
    """)
    nlrb = conn.execute("SELECT COUNT(*) FROM nlrb_cases").fetchone()[0]
    print(f"  NLRB cases (2020+): {nlrb:,}")

    # Skip cross_links — not queried by dashboard, saves ~30MB

    # Build employers from the deploy data
    print("  Building employer profiles from deploy data...")
    conn.execute("""
        INSERT INTO employers (name_normalized, primary_state, whd_case_count, osha_inspection_count,
                              nlrb_case_count, total_back_wages, total_penalties, total_fatalities, compliance_score)
        SELECT
            emp_name,
            MAX(state) as primary_state,
            SUM(whd_count), SUM(osha_count), SUM(nlrb_count),
            SUM(back_wages), SUM(penalties), SUM(fatalities), 0.5
        FROM (
            SELECT employer_normalized as emp_name, state, COUNT(*) as whd_count, 0 as osha_count, 0 as nlrb_count,
                   SUM(back_wages_owed) as back_wages, SUM(civil_penalties) as penalties, 0 as fatalities
            FROM whd_cases WHERE employer_normalized != '' GROUP BY employer_normalized, state
            UNION ALL
            SELECT employer_normalized, site_state, 0, COUNT(*), 0, 0, SUM(total_current_penalty), SUM(fatalities)
            FROM osha_inspections WHERE employer_normalized != '' GROUP BY employer_normalized, site_state
            UNION ALL
            SELECT employer_normalized, state, 0, 0, COUNT(*), 0, 0, 0
            FROM nlrb_cases WHERE employer_normalized != '' GROUP BY employer_normalized, state
        ) GROUP BY emp_name
    """)
    emp = conn.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
    print(f"  Employers: {emp:,}")

    # Create indexes
    print("  Creating indexes...")
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_whd_employer ON whd_cases(employer_normalized);
        CREATE INDEX IF NOT EXISTS idx_whd_state ON whd_cases(state);
        CREATE INDEX IF NOT EXISTS idx_whd_naics ON whd_cases(naics_code);
        CREATE INDEX IF NOT EXISTS idx_osha_employer ON osha_inspections(employer_normalized);
        CREATE INDEX IF NOT EXISTS idx_osha_state ON osha_inspections(site_state);
        CREATE INDEX IF NOT EXISTS idx_nlrb_employer ON nlrb_cases(employer_normalized);
        CREATE INDEX IF NOT EXISTS idx_nlrb_state ON nlrb_cases(state);
        CREATE INDEX IF NOT EXISTS idx_employers_name ON employers(name_normalized);
    """)

    conn.execute("DETACH DATABASE full_db")
    conn.commit()

    # VACUUM
    print("  Running VACUUM...")
    conn.execute("VACUUM")
    conn.close()

    size_mb = DEPLOY_DB.stat().st_size / (1024 * 1024)
    print(f"\nDeploy DB: {DEPLOY_DB}")
    print(f"Size: {size_mb:.1f} MB")

    if size_mb > MAX_SIZE_MB:
        print(f"\nWARNING: Deploy DB is {size_mb:.1f} MB (target: <{MAX_SIZE_MB} MB)")
        print("Consider trimming OSHA or NLRB further.")

    # Summary
    conn = sqlite3.connect(str(DEPLOY_DB))
    print("\nTable row counts:")
    for table in ['whd_cases', 'osha_inspections', 'nlrb_cases', 'employers', 'cross_links']:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,}")

    multi = conn.execute("""
        SELECT COUNT(*) FROM employers
        WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
    """).fetchone()[0]
    three = conn.execute("""
        SELECT COUNT(*) FROM employers
        WHERE whd_case_count > 0 AND osha_inspection_count > 0 AND nlrb_case_count > 0
    """).fetchone()[0]
    bw = conn.execute("SELECT COALESCE(SUM(back_wages_owed),0) FROM whd_cases").fetchone()[0]
    print(f"\n  Multi-agency offenders: {multi:,}")
    print(f"  All 3 agencies: {three:,}")
    print(f"  Total back wages: ${bw:,.0f}")
    conn.close()


if __name__ == "__main__":
    build_deploy_db()
