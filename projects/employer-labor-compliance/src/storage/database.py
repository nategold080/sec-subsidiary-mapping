"""SQLite database for Employer Labor Compliance data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "labor_compliance.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables."""
    _conn = conn or get_connection()
    _conn.executescript("""
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

        CREATE INDEX IF NOT EXISTS idx_whd_employer ON whd_cases(employer_normalized);
        CREATE INDEX IF NOT EXISTS idx_whd_state ON whd_cases(state);
        CREATE INDEX IF NOT EXISTS idx_whd_naics ON whd_cases(naics_code);
        CREATE INDEX IF NOT EXISTS idx_osha_employer ON osha_inspections(employer_normalized);
        CREATE INDEX IF NOT EXISTS idx_osha_state ON osha_inspections(site_state);
        CREATE INDEX IF NOT EXISTS idx_nlrb_employer ON nlrb_cases(employer_normalized);
        CREATE INDEX IF NOT EXISTS idx_nlrb_state ON nlrb_cases(state);
        CREATE INDEX IF NOT EXISTS idx_employers_name ON employers(name_normalized);
        CREATE INDEX IF NOT EXISTS idx_cross_links_source ON cross_links(source_type, source_id);
        CREATE INDEX IF NOT EXISTS idx_cross_links_target ON cross_links(target_type, target_id);
    """)
    _conn.commit()
    if conn is None:
        _conn.close()


def upsert_whd_case(conn: sqlite3.Connection, rec: dict) -> str:
    """Insert or update a WHD case."""
    conn.execute("""
        INSERT INTO whd_cases (
            case_id, trade_name, legal_name, street_address, city, state, zip_code,
            naics_code, naics_description, findings_start_date, findings_end_date,
            back_wages_owed, civil_penalties, employees_affected,
            flsa_violated, mspa_violated, h1b_violated, fmla_violated,
            sca_violated, dba_violated, employer_normalized, quality_score
        ) VALUES (
            :case_id, :trade_name, :legal_name, :street_address, :city, :state, :zip_code,
            :naics_code, :naics_description, :findings_start_date, :findings_end_date,
            :back_wages_owed, :civil_penalties, :employees_affected,
            :flsa_violated, :mspa_violated, :h1b_violated, :fmla_violated,
            :sca_violated, :dba_violated, :employer_normalized, :quality_score
        ) ON CONFLICT(case_id) DO UPDATE SET
            back_wages_owed = CASE WHEN excluded.back_wages_owed > 0 THEN excluded.back_wages_owed ELSE whd_cases.back_wages_owed END,
            civil_penalties = CASE WHEN excluded.civil_penalties > 0 THEN excluded.civil_penalties ELSE whd_cases.civil_penalties END,
            quality_score = excluded.quality_score
    """, rec)
    return rec["case_id"]


def upsert_osha_inspection(conn: sqlite3.Connection, rec: dict) -> str:
    """Insert or update an OSHA inspection."""
    conn.execute("""
        INSERT INTO osha_inspections (
            activity_number, reporting_id, establishment_name, site_address,
            site_city, site_state, site_zip, naics_code, sic_code,
            inspection_type, open_date, close_date,
            total_initial_penalty, total_current_penalty,
            num_violations, serious_violations, willful_violations, repeat_violations,
            fatalities, hospitalized, employer_normalized, quality_score
        ) VALUES (
            :activity_number, :reporting_id, :establishment_name, :site_address,
            :site_city, :site_state, :site_zip, :naics_code, :sic_code,
            :inspection_type, :open_date, :close_date,
            :total_initial_penalty, :total_current_penalty,
            :num_violations, :serious_violations, :willful_violations, :repeat_violations,
            :fatalities, :hospitalized, :employer_normalized, :quality_score
        ) ON CONFLICT(activity_number) DO UPDATE SET
            total_current_penalty = CASE WHEN excluded.total_current_penalty > 0 THEN excluded.total_current_penalty ELSE osha_inspections.total_current_penalty END,
            close_date = CASE WHEN excluded.close_date != '' THEN excluded.close_date ELSE osha_inspections.close_date END,
            quality_score = excluded.quality_score
    """, rec)
    return rec["activity_number"]


def upsert_nlrb_case(conn: sqlite3.Connection, rec: dict) -> str:
    """Insert or update an NLRB case."""
    conn.execute("""
        INSERT INTO nlrb_cases (
            case_number, case_name, date_filed, date_closed, status, case_type,
            allegation, city, state, num_employees, unit_description, union_name,
            employer_normalized, quality_score
        ) VALUES (
            :case_number, :case_name, :date_filed, :date_closed, :status, :case_type,
            :allegation, :city, :state, :num_employees, :unit_description, :union_name,
            :employer_normalized, :quality_score
        ) ON CONFLICT(case_number) DO UPDATE SET
            status = CASE WHEN excluded.status != '' THEN excluded.status ELSE nlrb_cases.status END,
            date_closed = CASE WHEN excluded.date_closed != '' THEN excluded.date_closed ELSE nlrb_cases.date_closed END,
            quality_score = excluded.quality_score
    """, rec)
    return rec["case_number"]


def upsert_employer(conn: sqlite3.Connection, rec: dict) -> int:
    """Insert or update an employer record."""
    conn.execute("""
        INSERT INTO employers (
            name_normalized, trade_names, naics_code, primary_state,
            whd_case_count, osha_inspection_count, nlrb_case_count,
            total_back_wages, total_penalties, total_fatalities, compliance_score
        ) VALUES (
            :name_normalized, :trade_names, :naics_code, :primary_state,
            :whd_case_count, :osha_inspection_count, :nlrb_case_count,
            :total_back_wages, :total_penalties, :total_fatalities, :compliance_score
        ) ON CONFLICT(name_normalized) DO UPDATE SET
            whd_case_count = excluded.whd_case_count,
            osha_inspection_count = excluded.osha_inspection_count,
            nlrb_case_count = excluded.nlrb_case_count,
            total_back_wages = excluded.total_back_wages,
            total_penalties = excluded.total_penalties,
            total_fatalities = excluded.total_fatalities,
            compliance_score = excluded.compliance_score
    """, rec)
    row = conn.execute(
        "SELECT id FROM employers WHERE name_normalized = ?",
        (rec["name_normalized"],),
    ).fetchone()
    return row["id"]


def insert_cross_link(conn: sqlite3.Connection, rec: dict) -> int | None:
    """Insert a cross-link between records."""
    try:
        cur = conn.execute("""
            INSERT INTO cross_links (source_type, source_id, target_type, target_id, link_method, confidence)
            VALUES (:source_type, :source_id, :target_type, :target_id, :link_method, :confidence)
        """, rec)
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_stats(conn: sqlite3.Connection | None = None) -> dict:
    """Get database summary statistics."""
    _conn = conn or get_connection()

    whd_count = _conn.execute("SELECT COUNT(*) FROM whd_cases").fetchone()[0]
    osha_count = _conn.execute("SELECT COUNT(*) FROM osha_inspections").fetchone()[0]
    nlrb_count = _conn.execute("SELECT COUNT(*) FROM nlrb_cases").fetchone()[0]
    employer_count = _conn.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
    cross_link_count = _conn.execute("SELECT COUNT(*) FROM cross_links").fetchone()[0]

    total_back_wages = _conn.execute(
        "SELECT COALESCE(SUM(back_wages_owed), 0) FROM whd_cases"
    ).fetchone()[0]
    total_whd_penalties = _conn.execute(
        "SELECT COALESCE(SUM(civil_penalties), 0) FROM whd_cases"
    ).fetchone()[0]
    total_osha_penalties = _conn.execute(
        "SELECT COALESCE(SUM(total_current_penalty), 0) FROM osha_inspections"
    ).fetchone()[0]
    total_fatalities = _conn.execute(
        "SELECT COALESCE(SUM(fatalities), 0) FROM osha_inspections"
    ).fetchone()[0]
    employees_affected = _conn.execute(
        "SELECT COALESCE(SUM(employees_affected), 0) FROM whd_cases"
    ).fetchone()[0]

    avg_quality_whd = _conn.execute(
        "SELECT AVG(quality_score) FROM whd_cases WHERE quality_score > 0"
    ).fetchone()[0] or 0
    avg_quality_osha = _conn.execute(
        "SELECT AVG(quality_score) FROM osha_inspections WHERE quality_score > 0"
    ).fetchone()[0] or 0
    avg_quality_nlrb = _conn.execute(
        "SELECT AVG(quality_score) FROM nlrb_cases WHERE quality_score > 0"
    ).fetchone()[0] or 0

    # Top states by WHD cases
    top_states = _conn.execute("""
        SELECT state, COUNT(*) as cnt FROM whd_cases
        WHERE state != '' GROUP BY state ORDER BY cnt DESC LIMIT 10
    """).fetchall()

    # Top industries
    top_industries = _conn.execute("""
        SELECT naics_description, COUNT(*) as cnt FROM whd_cases
        WHERE naics_description != '' GROUP BY naics_description ORDER BY cnt DESC LIMIT 10
    """).fetchall()

    # Multi-agency offenders
    multi_agency = _conn.execute("""
        SELECT name_normalized, whd_case_count, osha_inspection_count, nlrb_case_count,
               (whd_case_count + osha_inspection_count + nlrb_case_count) as total
        FROM employers
        WHERE (CASE WHEN whd_case_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN osha_inspection_count > 0 THEN 1 ELSE 0 END +
               CASE WHEN nlrb_case_count > 0 THEN 1 ELSE 0 END) >= 2
        ORDER BY total DESC LIMIT 10
    """).fetchall()

    result = {
        "whd_count": whd_count,
        "osha_count": osha_count,
        "nlrb_count": nlrb_count,
        "employer_count": employer_count,
        "cross_link_count": cross_link_count,
        "total_back_wages": total_back_wages,
        "total_whd_penalties": total_whd_penalties,
        "total_osha_penalties": total_osha_penalties,
        "total_fatalities": total_fatalities,
        "employees_affected": employees_affected,
        "avg_quality": {
            "whd": round(avg_quality_whd, 3),
            "osha": round(avg_quality_osha, 3),
            "nlrb": round(avg_quality_nlrb, 3),
        },
        "top_states": [(r["state"], r["cnt"]) for r in top_states],
        "top_industries": [(r["naics_description"], r["cnt"]) for r in top_industries],
        "multi_agency_offenders": [dict(r) for r in multi_agency],
    }

    if conn is None:
        _conn.close()
    return result
