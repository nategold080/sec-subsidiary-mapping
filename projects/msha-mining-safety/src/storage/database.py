"""SQLite database schema and operations for MSHA Mining Safety Tracker."""

import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
DB_PATH = os.path.join(DATA_DIR, "msha.db")


def get_connection(db_path: str | None = None, conn: sqlite3.Connection | None = None) -> tuple[sqlite3.Connection, bool]:
    """Get or create a database connection. Returns (conn, should_close)."""
    if conn is not None:
        return conn, False
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    return c, True


def init_db(db_path: str | None = None, conn: sqlite3.Connection | None = None) -> None:
    """Create all tables and indexes."""
    c, should_close = get_connection(db_path, conn)
    try:
        c.executescript(SCHEMA_SQL)
        c.commit()
    finally:
        if should_close:
            c.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mines (
    mine_id TEXT PRIMARY KEY,
    mine_name TEXT,
    coal_metal_ind TEXT,
    mine_type TEXT,
    mine_status TEXT,
    status_date TEXT,
    controller_id TEXT,
    controller_name TEXT,
    operator_id TEXT,
    operator_name TEXT,
    state TEXT,
    fips_cnty_cd TEXT,
    fips_cnty_nm TEXT,
    company_type TEXT,
    district TEXT,
    primary_sic TEXT,
    primary_sic_cd TEXT,
    secondary_sic TEXT,
    latitude TEXT,
    longitude TEXT,
    no_employees INTEGER,
    days_per_week INTEGER,
    hours_per_shift INTEGER,
    nearest_town TEXT,
    quality_score REAL
);

CREATE TABLE IF NOT EXISTS accidents (
    document_no TEXT PRIMARY KEY,
    mine_id TEXT,
    controller_id TEXT,
    controller_name TEXT,
    operator_id TEXT,
    operator_name TEXT,
    contractor_id TEXT,
    subunit TEXT,
    accident_dt TEXT,
    cal_yr INTEGER,
    degree_injury_cd TEXT,
    degree_injury TEXT,
    fips_state_cd TEXT,
    ug_location TEXT,
    mining_equip TEXT,
    equip_mfr_name TEXT,
    classification TEXT,
    accident_type TEXT,
    no_injuries INTEGER,
    tot_exper REAL,
    mine_exper REAL,
    job_exper REAL,
    occupation TEXT,
    activity TEXT,
    injury_source TEXT,
    nature_injury TEXT,
    inj_body_part TEXT,
    schedule_charge INTEGER,
    days_restrict INTEGER,
    days_lost INTEGER,
    immed_notify TEXT,
    narrative TEXT,
    coal_metal_ind TEXT,
    quality_score REAL
);

CREATE TABLE IF NOT EXISTS inspections (
    event_no TEXT PRIMARY KEY,
    mine_id TEXT,
    inspection_begin_dt TEXT,
    inspection_end_dt TEXT,
    controller_id TEXT,
    controller_name TEXT,
    operator_id TEXT,
    operator_name TEXT,
    cal_yr INTEGER,
    activity_code TEXT,
    activity TEXT,
    coal_metal_ind TEXT,
    quality_score REAL
);

CREATE TABLE IF NOT EXISTS violations (
    event_no TEXT,
    violation_no TEXT,
    mine_id TEXT,
    controller_id TEXT,
    controller_name TEXT,
    violator_id TEXT,
    violator_name TEXT,
    violator_type TEXT,
    mine_name TEXT,
    mine_type TEXT,
    coal_metal_ind TEXT,
    violation_issue_dt TEXT,
    cal_yr INTEGER,
    sig_sub TEXT,
    section_of_act TEXT,
    section_of_act_desc TEXT,
    part_section TEXT,
    part_section_desc TEXT,
    proposed_penalty REAL,
    amount_paid REAL,
    quality_score REAL,
    PRIMARY KEY (event_no, violation_no)
);

CREATE TABLE IF NOT EXISTS assessed_violations (
    violation_no TEXT PRIMARY KEY,
    assessed_id TEXT,
    mine_id TEXT,
    controller_id TEXT,
    controller_name TEXT,
    operator_id TEXT,
    operator_name TEXT,
    cal_yr INTEGER,
    violation_issue_dt TEXT,
    section_of_act TEXT,
    part_section TEXT,
    proposed_penalty_amt REAL,
    paid_proposed_penalty_amt REAL,
    penalty_points INTEGER,
    sig_sub TEXT,
    likely TEXT,
    injury_illness TEXT,
    negligence TEXT,
    gravity TEXT,
    quality_score REAL
);

CREATE TABLE IF NOT EXISTS penalties (
    docket_no TEXT PRIMARY KEY,
    mine_id TEXT,
    controller_id TEXT,
    controller_name TEXT,
    operator_id TEXT,
    operator_name TEXT,
    case_status TEXT,
    proposed_penalty REAL,
    amount_assessed REAL,
    amount_paid REAL,
    cal_yr INTEGER,
    quality_score REAL
);

CREATE TABLE IF NOT EXISTS operator_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id TEXT,
    operator_name TEXT,
    normalized_name TEXT,
    mine_count INTEGER DEFAULT 0,
    active_mine_count INTEGER DEFAULT 0,
    total_employees INTEGER DEFAULT 0,
    total_accidents INTEGER DEFAULT 0,
    total_fatalities INTEGER DEFAULT 0,
    total_injuries INTEGER DEFAULT 0,
    total_inspections INTEGER DEFAULT 0,
    total_violations INTEGER DEFAULT 0,
    total_proposed_penalties REAL DEFAULT 0,
    total_paid_penalties REAL DEFAULT 0,
    sig_sub_violations INTEGER DEFAULT 0,
    days_lost INTEGER DEFAULT 0,
    states TEXT,
    mine_types TEXT,
    commodities TEXT,
    safety_score REAL,
    risk_tier TEXT,
    UNIQUE(operator_id)
);

CREATE INDEX IF NOT EXISTS idx_accidents_mine ON accidents(mine_id);
CREATE INDEX IF NOT EXISTS idx_accidents_yr ON accidents(cal_yr);
CREATE INDEX IF NOT EXISTS idx_accidents_degree ON accidents(degree_injury_cd);
CREATE INDEX IF NOT EXISTS idx_inspections_mine ON inspections(mine_id);
CREATE INDEX IF NOT EXISTS idx_inspections_yr ON inspections(cal_yr);
CREATE INDEX IF NOT EXISTS idx_violations_mine ON violations(mine_id);
CREATE INDEX IF NOT EXISTS idx_violations_yr ON violations(cal_yr);
CREATE INDEX IF NOT EXISTS idx_violations_event ON violations(event_no);
CREATE INDEX IF NOT EXISTS idx_assessed_mine ON assessed_violations(mine_id);
CREATE INDEX IF NOT EXISTS idx_assessed_yr ON assessed_violations(cal_yr);
CREATE INDEX IF NOT EXISTS idx_penalties_mine ON penalties(mine_id);
CREATE INDEX IF NOT EXISTS idx_mines_state ON mines(state);
CREATE INDEX IF NOT EXISTS idx_mines_status ON mines(mine_status);
CREATE INDEX IF NOT EXISTS idx_mines_operator ON mines(operator_id);
CREATE INDEX IF NOT EXISTS idx_mines_controller ON mines(controller_id);
CREATE INDEX IF NOT EXISTS idx_profiles_name ON operator_profiles(normalized_name);
CREATE INDEX IF NOT EXISTS idx_profiles_score ON operator_profiles(safety_score);
"""


def upsert_mines_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert or replace mine records."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR REPLACE INTO mines (
                mine_id, mine_name, coal_metal_ind, mine_type, mine_status, status_date,
                controller_id, controller_name, operator_id, operator_name,
                state, fips_cnty_cd, fips_cnty_nm, company_type, district,
                primary_sic, primary_sic_cd, secondary_sic,
                latitude, longitude, no_employees, days_per_week, hours_per_shift,
                nearest_town, quality_score
            ) VALUES (
                :mine_id, :mine_name, :coal_metal_ind, :mine_type, :mine_status, :status_date,
                :controller_id, :controller_name, :operator_id, :operator_name,
                :state, :fips_cnty_cd, :fips_cnty_nm, :company_type, :district,
                :primary_sic, :primary_sic_cd, :secondary_sic,
                :latitude, :longitude, :no_employees, :days_per_week, :hours_per_shift,
                :nearest_town, :quality_score
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def insert_accidents_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert accident records (ignore duplicates)."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR IGNORE INTO accidents (
                document_no, mine_id, controller_id, controller_name,
                operator_id, operator_name, contractor_id, subunit,
                accident_dt, cal_yr, degree_injury_cd, degree_injury,
                fips_state_cd, ug_location, mining_equip, equip_mfr_name,
                classification, accident_type, no_injuries,
                tot_exper, mine_exper, job_exper,
                occupation, activity, injury_source, nature_injury,
                inj_body_part, schedule_charge, days_restrict, days_lost,
                immed_notify, narrative, coal_metal_ind, quality_score
            ) VALUES (
                :document_no, :mine_id, :controller_id, :controller_name,
                :operator_id, :operator_name, :contractor_id, :subunit,
                :accident_dt, :cal_yr, :degree_injury_cd, :degree_injury,
                :fips_state_cd, :ug_location, :mining_equip, :equip_mfr_name,
                :classification, :accident_type, :no_injuries,
                :tot_exper, :mine_exper, :job_exper,
                :occupation, :activity, :injury_source, :nature_injury,
                :inj_body_part, :schedule_charge, :days_restrict, :days_lost,
                :immed_notify, :narrative, :coal_metal_ind, :quality_score
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def insert_inspections_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert inspection records (ignore duplicates)."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR IGNORE INTO inspections (
                event_no, mine_id, inspection_begin_dt, inspection_end_dt,
                controller_id, controller_name, operator_id, operator_name,
                cal_yr, activity_code, activity, coal_metal_ind, quality_score
            ) VALUES (
                :event_no, :mine_id, :inspection_begin_dt, :inspection_end_dt,
                :controller_id, :controller_name, :operator_id, :operator_name,
                :cal_yr, :activity_code, :activity, :coal_metal_ind, :quality_score
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def insert_violations_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert violation records (ignore duplicates)."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR IGNORE INTO violations (
                event_no, violation_no, mine_id,
                controller_id, controller_name, violator_id, violator_name,
                violator_type, mine_name, mine_type, coal_metal_ind,
                violation_issue_dt, cal_yr, sig_sub,
                section_of_act, section_of_act_desc, part_section, part_section_desc,
                proposed_penalty, amount_paid, quality_score
            ) VALUES (
                :event_no, :violation_no, :mine_id,
                :controller_id, :controller_name, :violator_id, :violator_name,
                :violator_type, :mine_name, :mine_type, :coal_metal_ind,
                :violation_issue_dt, :cal_yr, :sig_sub,
                :section_of_act, :section_of_act_desc, :part_section, :part_section_desc,
                :proposed_penalty, :amount_paid, :quality_score
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def insert_assessed_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert assessed violation records (ignore duplicates)."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR IGNORE INTO assessed_violations (
                violation_no, assessed_id, mine_id,
                controller_id, controller_name, operator_id, operator_name,
                cal_yr, violation_issue_dt, section_of_act, part_section,
                proposed_penalty_amt, paid_proposed_penalty_amt, penalty_points,
                sig_sub, likely, injury_illness, negligence, gravity, quality_score
            ) VALUES (
                :violation_no, :assessed_id, :mine_id,
                :controller_id, :controller_name, :operator_id, :operator_name,
                :cal_yr, :violation_issue_dt, :section_of_act, :part_section,
                :proposed_penalty_amt, :paid_proposed_penalty_amt, :penalty_points,
                :sig_sub, :likely, :injury_illness, :negligence, :gravity, :quality_score
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def insert_penalties_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert civil penalty docket records (ignore duplicates)."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR IGNORE INTO penalties (
                docket_no, mine_id, controller_id, controller_name,
                operator_id, operator_name, case_status,
                proposed_penalty, amount_assessed, amount_paid,
                cal_yr, quality_score
            ) VALUES (
                :docket_no, :mine_id, :controller_id, :controller_name,
                :operator_id, :operator_name, :case_status,
                :proposed_penalty, :amount_assessed, :amount_paid,
                :cal_yr, :quality_score
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def upsert_profiles_batch(records: list[dict], conn: sqlite3.Connection | None = None) -> int:
    """Insert or replace operator profile records."""
    c, should_close = get_connection(conn=conn)
    try:
        c.executemany(
            """INSERT OR REPLACE INTO operator_profiles (
                operator_id, operator_name, normalized_name,
                mine_count, active_mine_count, total_employees,
                total_accidents, total_fatalities, total_injuries,
                total_inspections, total_violations,
                total_proposed_penalties, total_paid_penalties,
                sig_sub_violations, days_lost,
                states, mine_types, commodities,
                safety_score, risk_tier
            ) VALUES (
                :operator_id, :operator_name, :normalized_name,
                :mine_count, :active_mine_count, :total_employees,
                :total_accidents, :total_fatalities, :total_injuries,
                :total_inspections, :total_violations,
                :total_proposed_penalties, :total_paid_penalties,
                :sig_sub_violations, :days_lost,
                :states, :mine_types, :commodities,
                :safety_score, :risk_tier
            )""",
            records,
        )
        c.commit()
        return len(records)
    finally:
        if should_close:
            c.close()


def get_stats(conn: sqlite3.Connection | None = None) -> dict:
    """Get database statistics."""
    c, should_close = get_connection(conn=conn)
    try:
        stats = {}
        for table in ["mines", "accidents", "inspections", "violations", "assessed_violations", "penalties", "operator_profiles"]:
            row = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            stats[table] = row[0]

        row = c.execute("SELECT SUM(proposed_penalty_amt) FROM assessed_violations WHERE proposed_penalty_amt IS NOT NULL").fetchone()
        stats["total_proposed_penalties"] = row[0] or 0

        row = c.execute("SELECT SUM(paid_proposed_penalty_amt) FROM assessed_violations WHERE paid_proposed_penalty_amt IS NOT NULL").fetchone()
        stats["total_paid_penalties"] = row[0] or 0

        row = c.execute("SELECT COUNT(*) FROM accidents WHERE degree_injury_cd = '01'").fetchone()
        stats["total_fatalities"] = row[0]

        row = c.execute("SELECT COUNT(*) FROM accidents WHERE degree_injury_cd = '02'").fetchone()
        stats["total_permanent_disabilities"] = row[0]

        row = c.execute("SELECT COUNT(DISTINCT state) FROM mines WHERE state IS NOT NULL AND state != ''").fetchone()
        stats["states_covered"] = row[0]

        row = c.execute("SELECT MIN(cal_yr), MAX(cal_yr) FROM accidents WHERE cal_yr IS NOT NULL").fetchone()
        stats["accident_year_range"] = f"{row[0]}–{row[1]}" if row[0] else "N/A"

        row = c.execute("SELECT COUNT(*) FROM mines WHERE mine_status = 'Active'").fetchone()
        stats["active_mines"] = row[0]

        return stats
    finally:
        if should_close:
            c.close()
