"""
SQLite database layer for CFPB Consumer Complaint Cross-Linked Analysis.

Provides schema initialization, connection management, and CRUD operations
for all tables: complaints, institutions, CRA ratings, enforcement actions,
cross-links, and pipeline tracking.

All connections use WAL mode for concurrent read/write support.
"""

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "cfpb_tracker.db"

# ---------------------------------------------------------------------------
# Schema Definition
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- CFPB Consumer Complaints
CREATE TABLE IF NOT EXISTS cfpb_complaints (
    complaint_id INTEGER PRIMARY KEY,
    date_received TEXT,
    product TEXT,
    sub_product TEXT,
    issue TEXT,
    sub_issue TEXT,
    company TEXT NOT NULL,
    state TEXT,
    zip_code TEXT,
    consumer_narrative TEXT,
    company_public_response TEXT,
    company_response TEXT,
    timely_response TEXT,
    consumer_disputed TEXT,
    submitted_via TEXT,
    date_sent_to_company TEXT,
    tags TEXT,
    consumer_consent_provided TEXT,
    quality_score REAL DEFAULT 0.0
);

-- FDIC-insured Financial Institutions
CREATE TABLE IF NOT EXISTS financial_institutions (
    cert_number INTEGER PRIMARY KEY,
    rssd_id INTEGER,
    institution_name TEXT NOT NULL,
    canonical_name TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    total_assets REAL,
    institution_class TEXT,
    regulator TEXT,
    active INTEGER DEFAULT 1,
    established_date TEXT,
    fdic_url TEXT,
    quality_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- FFIEC CRA Ratings
CREATE TABLE IF NOT EXISTS cra_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cert_number INTEGER NOT NULL,
    institution_name TEXT,
    exam_date TEXT,
    cra_rating TEXT,
    assessment_area TEXT,
    regulator TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cert_number) REFERENCES financial_institutions(cert_number)
);

-- CFPB and Other Enforcement Actions
CREATE TABLE IF NOT EXISTS enforcement_actions (
    action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agency TEXT DEFAULT 'CFPB',
    respondent_name TEXT NOT NULL,
    action_date TEXT,
    action_type TEXT,
    penalty_amount REAL,
    description TEXT,
    url TEXT,
    institution_cert INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_cert) REFERENCES financial_institutions(cert_number)
);

-- Cross-link table: maps complaints to institutions via entity resolution
CREATE TABLE IF NOT EXISTS institution_complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    cert_number INTEGER NOT NULL,
    match_confidence REAL NOT NULL,
    match_method TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES cfpb_complaints(complaint_id),
    FOREIGN KEY (cert_number) REFERENCES financial_institutions(cert_number),
    UNIQUE(complaint_id, cert_number)
);

-- Pipeline run tracking
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    notes TEXT
);

-- Institution financial data from FDIC Call Reports (Enrichment 1)
CREATE TABLE IF NOT EXISTS institution_financials (
    cert_number INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    total_assets REAL,
    total_deposits REAL,
    total_loans REAL,
    net_income REAL,
    net_interest_income REAL,
    tier1_capital_ratio REAL,
    leverage_ratio REAL,
    roa REAL,
    roe REAL,
    noncurrent_loans_pct REAL,
    efficiency_ratio REAL,
    num_offices INTEGER,
    num_employees INTEGER,
    quality_score REAL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (cert_number, report_date)
);

-- Complaint-to-financial risk metrics (Enrichment 3)
CREATE TABLE IF NOT EXISTS institution_risk_profiles (
    cert_number INTEGER PRIMARY KEY,
    institution_name TEXT,
    total_assets REAL,
    asset_tier TEXT,
    complaint_count INTEGER,
    complaints_per_billion_assets REAL,
    enforcement_count INTEGER,
    total_penalties REAL,
    financial_health_score REAL,
    complaint_severity_score REAL,
    overall_risk_score REAL,
    risk_tier TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Unified multi-agency enforcement actions (Enrichment 2)
CREATE TABLE IF NOT EXISTS regulatory_enforcement (
    action_id TEXT PRIMARY KEY,
    agency TEXT NOT NULL,
    institution_name TEXT,
    cert_number INTEGER,
    action_type TEXT,
    action_date TEXT,
    penalty_amount REAL,
    description TEXT,
    docket_number TEXT,
    source_url TEXT,
    quality_score REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- HMDA institution-level mortgage lending summaries (Enrichment 4)
CREATE TABLE IF NOT EXISTS hmda_institution_summary (
    lei TEXT NOT NULL,
    cert_number INTEGER,
    institution_name TEXT,
    report_year INTEGER NOT NULL,
    total_applications INTEGER,
    total_originations INTEGER,
    total_denials INTEGER,
    denial_rate REAL,
    avg_loan_amount REAL,
    avg_interest_rate REAL,
    total_loan_volume REAL,
    lending_states TEXT,
    quality_score REAL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (lei, report_year)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_complaints_company ON cfpb_complaints(company);
CREATE INDEX IF NOT EXISTS idx_complaints_product ON cfpb_complaints(product);
CREATE INDEX IF NOT EXISTS idx_complaints_state ON cfpb_complaints(state);
CREATE INDEX IF NOT EXISTS idx_complaints_date ON cfpb_complaints(date_received);
CREATE INDEX IF NOT EXISTS idx_institutions_name ON financial_institutions(institution_name);
CREATE INDEX IF NOT EXISTS idx_institutions_canonical ON financial_institutions(canonical_name);
CREATE INDEX IF NOT EXISTS idx_institutions_state ON financial_institutions(state);
CREATE INDEX IF NOT EXISTS idx_cra_cert ON cra_ratings(cert_number);
CREATE INDEX IF NOT EXISTS idx_cra_rating ON cra_ratings(cra_rating);
CREATE INDEX IF NOT EXISTS idx_enforcement_respondent ON enforcement_actions(respondent_name);
CREATE INDEX IF NOT EXISTS idx_enforcement_cert ON enforcement_actions(institution_cert);
CREATE INDEX IF NOT EXISTS idx_enforcement_date ON enforcement_actions(action_date);
CREATE INDEX IF NOT EXISTS idx_ic_complaint ON institution_complaints(complaint_id);
CREATE INDEX IF NOT EXISTS idx_ic_cert ON institution_complaints(cert_number);
CREATE INDEX IF NOT EXISTS idx_ic_confidence ON institution_complaints(match_confidence);
CREATE INDEX IF NOT EXISTS idx_financials_cert ON institution_financials(cert_number);
CREATE INDEX IF NOT EXISTS idx_financials_date ON institution_financials(report_date);
CREATE INDEX IF NOT EXISTS idx_risk_tier ON institution_risk_profiles(risk_tier);
CREATE INDEX IF NOT EXISTS idx_risk_score ON institution_risk_profiles(overall_risk_score);
CREATE INDEX IF NOT EXISTS idx_risk_assets ON institution_risk_profiles(total_assets);
CREATE INDEX IF NOT EXISTS idx_regulatory_agency ON regulatory_enforcement(agency);
CREATE INDEX IF NOT EXISTS idx_regulatory_cert ON regulatory_enforcement(cert_number);
CREATE INDEX IF NOT EXISTS idx_regulatory_date ON regulatory_enforcement(action_date);
CREATE INDEX IF NOT EXISTS idx_regulatory_penalty ON regulatory_enforcement(penalty_amount);
CREATE INDEX IF NOT EXISTS idx_hmda_cert ON hmda_institution_summary(cert_number);
CREATE INDEX IF NOT EXISTS idx_hmda_year ON hmda_institution_summary(report_year);
CREATE INDEX IF NOT EXISTS idx_hmda_denial ON hmda_institution_summary(denial_rate);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Create a SQLite connection with WAL mode and row_factory enabled.

    Args:
        db_path: Path to the SQLite database file. Uses default if not provided.

    Returns:
        sqlite3.Connection configured with WAL mode and Row factory.
    """
    if db_path is None:
        db_path = str(DEFAULT_DB_PATH)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Initialize the database schema. Creates all tables and indexes if they
    do not already exist.

    Args:
        db_path: Path to the SQLite database file. Uses default if not provided.

    Returns:
        sqlite3.Connection to the initialized database.
    """
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Complaint Operations
# ---------------------------------------------------------------------------

def store_complaints_batch(
    conn: sqlite3.Connection,
    complaints: list[dict],
    batch_size: int = 1000,
) -> int:
    """
    Insert or replace a batch of CFPB complaints into the database.

    Args:
        conn: Active database connection.
        complaints: List of complaint dictionaries with keys matching table columns.
        batch_size: Number of records to insert per transaction. Default 1000.

    Returns:
        Total number of records inserted/updated.
    """
    total_stored = 0
    sql = """
        INSERT OR REPLACE INTO cfpb_complaints (
            complaint_id, date_received, product, sub_product,
            issue, sub_issue, company, state, zip_code,
            consumer_narrative, company_public_response, company_response,
            timely_response, consumer_disputed, submitted_via,
            date_sent_to_company, tags, consumer_consent_provided
        ) VALUES (
            :complaint_id, :date_received, :product, :sub_product,
            :issue, :sub_issue, :company, :state, :zip_code,
            :consumer_narrative, :company_public_response, :company_response,
            :timely_response, :consumer_disputed, :submitted_via,
            :date_sent_to_company, :tags, :consumer_consent_provided
        )
    """

    for i in range(0, len(complaints), batch_size):
        batch = complaints[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Failed to store complaint batch at offset {i}: {e}")

    return total_stored


def get_complaints_by_company(
    conn: sqlite3.Connection,
    company_name: str,
    limit: int = 100,
) -> list[sqlite3.Row]:
    """
    Retrieve complaints for a specific company name.

    Args:
        conn: Active database connection.
        company_name: Company name to search for (exact match).
        limit: Maximum number of records to return.

    Returns:
        List of complaint rows.
    """
    cursor = conn.execute(
        "SELECT * FROM cfpb_complaints WHERE company = ? ORDER BY date_received DESC LIMIT ?",
        (company_name, limit),
    )
    return cursor.fetchall()


def get_complaint_count(conn: sqlite3.Connection) -> int:
    """Return total number of complaints in the database."""
    cursor = conn.execute("SELECT COUNT(*) FROM cfpb_complaints")
    return cursor.fetchone()[0]


# ---------------------------------------------------------------------------
# Institution Operations
# ---------------------------------------------------------------------------

def store_institutions_batch(
    conn: sqlite3.Connection,
    institutions: list[dict],
    batch_size: int = 1000,
) -> int:
    """
    Insert or replace a batch of FDIC institution records.

    Args:
        conn: Active database connection.
        institutions: List of institution dictionaries.
        batch_size: Number of records per transaction.

    Returns:
        Total number of records inserted/updated.
    """
    total_stored = 0
    sql = """
        INSERT OR REPLACE INTO financial_institutions (
            cert_number, rssd_id, institution_name, canonical_name,
            city, state, zip_code, total_assets, institution_class,
            regulator, active, established_date, fdic_url, updated_at
        ) VALUES (
            :cert_number, :rssd_id, :institution_name, :canonical_name,
            :city, :state, :zip_code, :total_assets, :institution_class,
            :regulator, :active, :established_date, :fdic_url,
            :updated_at
        )
    """

    now = datetime.now(timezone.utc).isoformat()
    for i in range(0, len(institutions), batch_size):
        batch = institutions[i : i + batch_size]
        for inst in batch:
            inst.setdefault("updated_at", now)
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Failed to store institution batch at offset {i}: {e}")

    return total_stored


def get_all_institutions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """
    Retrieve all financial institutions from the database.

    Returns:
        List of all institution rows.
    """
    cursor = conn.execute(
        "SELECT * FROM financial_institutions ORDER BY institution_name"
    )
    return cursor.fetchall()


def get_institution_by_cert(
    conn: sqlite3.Connection,
    cert_number: int,
) -> Optional[sqlite3.Row]:
    """
    Retrieve a single institution by its FDIC CERT number.

    Args:
        conn: Active database connection.
        cert_number: FDIC certificate number.

    Returns:
        Institution row or None if not found.
    """
    cursor = conn.execute(
        "SELECT * FROM financial_institutions WHERE cert_number = ?",
        (cert_number,),
    )
    return cursor.fetchone()


def get_institution_count(conn: sqlite3.Connection) -> int:
    """Return total number of institutions in the database."""
    cursor = conn.execute("SELECT COUNT(*) FROM financial_institutions")
    return cursor.fetchone()[0]


# ---------------------------------------------------------------------------
# CRA Rating Operations
# ---------------------------------------------------------------------------

def store_cra_ratings_batch(
    conn: sqlite3.Connection,
    ratings: list[dict],
    batch_size: int = 1000,
) -> int:
    """
    Insert CRA rating records.

    Args:
        conn: Active database connection.
        ratings: List of CRA rating dictionaries.
        batch_size: Number of records per transaction.

    Returns:
        Total number of records inserted.
    """
    total_stored = 0
    sql = """
        INSERT INTO cra_ratings (
            cert_number, institution_name, exam_date,
            cra_rating, assessment_area, regulator
        ) VALUES (
            :cert_number, :institution_name, :exam_date,
            :cra_rating, :assessment_area, :regulator
        )
    """

    for i in range(0, len(ratings), batch_size):
        batch = ratings[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Failed to store CRA ratings batch at offset {i}: {e}")

    return total_stored


# ---------------------------------------------------------------------------
# Enforcement Action Operations
# ---------------------------------------------------------------------------

def store_enforcement_actions_batch(
    conn: sqlite3.Connection,
    actions: list[dict],
    batch_size: int = 500,
) -> int:
    """
    Insert enforcement action records.

    Args:
        conn: Active database connection.
        actions: List of enforcement action dictionaries.
        batch_size: Number of records per transaction.

    Returns:
        Total number of records inserted.
    """
    total_stored = 0
    sql = """
        INSERT INTO enforcement_actions (
            agency, respondent_name, action_date,
            action_type, penalty_amount, description, url, institution_cert
        ) VALUES (
            :agency, :respondent_name, :action_date,
            :action_type, :penalty_amount, :description, :url, :institution_cert
        )
    """

    for i in range(0, len(actions), batch_size):
        batch = actions[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(
                f"Failed to store enforcement actions batch at offset {i}: {e}"
            )

    return total_stored


# ---------------------------------------------------------------------------
# Cross-Link Operations
# ---------------------------------------------------------------------------

def store_institution_complaint_links(
    conn: sqlite3.Connection,
    links: list[dict],
    batch_size: int = 1000,
) -> int:
    """
    Insert institution-complaint cross-links from entity resolution.

    Args:
        conn: Active database connection.
        links: List of dicts with keys: complaint_id, cert_number,
               match_confidence, match_method.
        batch_size: Number of records per transaction.

    Returns:
        Total number of links inserted.
    """
    total_stored = 0
    sql = """
        INSERT OR IGNORE INTO institution_complaints (
            complaint_id, cert_number, match_confidence, match_method
        ) VALUES (
            :complaint_id, :cert_number, :match_confidence, :match_method
        )
    """

    for i in range(0, len(links), batch_size):
        batch = links[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(
                f"Failed to store cross-links batch at offset {i}: {e}"
            )

    return total_stored


def get_linked_complaints_for_institution(
    conn: sqlite3.Connection,
    cert_number: int,
    min_confidence: float = 0.0,
) -> list[sqlite3.Row]:
    """
    Get all complaints linked to a specific institution.

    Args:
        conn: Active database connection.
        cert_number: FDIC certificate number.
        min_confidence: Minimum match confidence threshold.

    Returns:
        List of complaint rows with match metadata.
    """
    cursor = conn.execute(
        """
        SELECT c.*, ic.match_confidence, ic.match_method
        FROM cfpb_complaints c
        JOIN institution_complaints ic ON c.complaint_id = ic.complaint_id
        WHERE ic.cert_number = ? AND ic.match_confidence >= ?
        ORDER BY c.date_received DESC
        """,
        (cert_number, min_confidence),
    )
    return cursor.fetchall()


# ---------------------------------------------------------------------------
# Pipeline Run Tracking
# ---------------------------------------------------------------------------

def start_pipeline_run(
    conn: sqlite3.Connection,
    pipeline_name: str,
    notes: Optional[str] = None,
) -> int:
    """
    Record the start of a pipeline run.

    Args:
        conn: Active database connection.
        pipeline_name: Name of the pipeline being run.
        notes: Optional notes about this run.

    Returns:
        The ID of the new pipeline run record.
    """
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO pipeline_runs (pipeline_name, started_at, status, notes)
        VALUES (?, ?, 'running', ?)
        """,
        (pipeline_name, now, notes),
    )
    conn.commit()
    return cursor.lastrowid


def complete_pipeline_run(
    conn: sqlite3.Connection,
    run_id: int,
    records_processed: int,
    records_failed: int = 0,
    status: str = "completed",
    notes: Optional[str] = None,
) -> None:
    """
    Record the completion of a pipeline run.

    Args:
        conn: Active database connection.
        run_id: ID of the pipeline run to complete.
        records_processed: Total records successfully processed.
        records_failed: Total records that failed processing.
        status: Final status (completed, failed, partial).
        notes: Optional completion notes.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        UPDATE pipeline_runs
        SET completed_at = ?, records_processed = ?, records_failed = ?,
            status = ?, notes = COALESCE(?, notes)
        WHERE id = ?
        """,
        (now, records_processed, records_failed, status, notes, run_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Institution Financials Operations (Enrichment 1)
# ---------------------------------------------------------------------------

def store_financials_batch(
    conn: sqlite3.Connection,
    records: list[dict],
    batch_size: int = 1000,
) -> int:
    """Insert or replace institution financial records."""
    total_stored = 0
    sql = """
        INSERT OR REPLACE INTO institution_financials (
            cert_number, report_date, total_assets, total_deposits,
            total_loans, net_income, net_interest_income,
            tier1_capital_ratio, leverage_ratio, roa, roe,
            noncurrent_loans_pct, efficiency_ratio,
            num_offices, num_employees, quality_score
        ) VALUES (
            :cert_number, :report_date, :total_assets, :total_deposits,
            :total_loans, :net_income, :net_interest_income,
            :tier1_capital_ratio, :leverage_ratio, :roa, :roe,
            :noncurrent_loans_pct, :efficiency_ratio,
            :num_offices, :num_employees, :quality_score
        )
    """
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Failed to store financials batch at offset {i}: {e}")
    return total_stored


def get_latest_financials(
    conn: sqlite3.Connection,
    cert_number: int,
) -> Optional[sqlite3.Row]:
    """Get the most recent financial record for an institution."""
    cursor = conn.execute(
        "SELECT * FROM institution_financials WHERE cert_number = ? "
        "ORDER BY report_date DESC LIMIT 1",
        (cert_number,),
    )
    return cursor.fetchone()


def get_financials_history(
    conn: sqlite3.Connection,
    cert_number: int,
    limit: int = 8,
) -> list[sqlite3.Row]:
    """Get quarterly financial history for an institution."""
    cursor = conn.execute(
        "SELECT * FROM institution_financials WHERE cert_number = ? "
        "ORDER BY report_date DESC LIMIT ?",
        (cert_number, limit),
    )
    return cursor.fetchall()


# ---------------------------------------------------------------------------
# Regulatory Enforcement Operations (Enrichment 2)
# ---------------------------------------------------------------------------

def store_regulatory_enforcement_batch(
    conn: sqlite3.Connection,
    actions: list[dict],
    batch_size: int = 500,
) -> int:
    """Insert or replace unified enforcement action records."""
    total_stored = 0
    sql = """
        INSERT OR REPLACE INTO regulatory_enforcement (
            action_id, agency, institution_name, cert_number,
            action_type, action_date, penalty_amount,
            description, docket_number, source_url, quality_score
        ) VALUES (
            :action_id, :agency, :institution_name, :cert_number,
            :action_type, :action_date, :penalty_amount,
            :description, :docket_number, :source_url, :quality_score
        )
    """
    for i in range(0, len(actions), batch_size):
        batch = actions[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(
                f"Failed to store regulatory enforcement batch at offset {i}: {e}"
            )
    return total_stored


def migrate_cfpb_enforcement_to_regulatory(conn: sqlite3.Connection) -> int:
    """
    Migrate existing enforcement_actions rows into the unified
    regulatory_enforcement table.
    """
    sql = """
        INSERT OR IGNORE INTO regulatory_enforcement (
            action_id, agency, institution_name, cert_number,
            action_type, action_date, penalty_amount,
            description, docket_number, source_url, quality_score
        )
        SELECT
            'CFPB-' || CAST(action_id AS TEXT),
            COALESCE(agency, 'CFPB'),
            respondent_name,
            institution_cert,
            action_type,
            action_date,
            penalty_amount,
            description,
            NULL,
            url,
            CASE WHEN penalty_amount IS NOT NULL AND penalty_amount > 0 THEN 0.8 ELSE 0.5 END
        FROM enforcement_actions
    """
    cursor = conn.execute(sql)
    conn.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Institution Risk Profile Operations (Enrichment 3)
# ---------------------------------------------------------------------------

def store_risk_profiles_batch(
    conn: sqlite3.Connection,
    profiles: list[dict],
    batch_size: int = 1000,
) -> int:
    """Insert or replace institution risk profile records."""
    total_stored = 0
    sql = """
        INSERT OR REPLACE INTO institution_risk_profiles (
            cert_number, institution_name, total_assets, asset_tier,
            complaint_count, complaints_per_billion_assets,
            enforcement_count, total_penalties,
            financial_health_score, complaint_severity_score,
            overall_risk_score, risk_tier
        ) VALUES (
            :cert_number, :institution_name, :total_assets, :asset_tier,
            :complaint_count, :complaints_per_billion_assets,
            :enforcement_count, :total_penalties,
            :financial_health_score, :complaint_severity_score,
            :overall_risk_score, :risk_tier
        )
    """
    for i in range(0, len(profiles), batch_size):
        batch = profiles[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Failed to store risk profiles batch at offset {i}: {e}")
    return total_stored


# ---------------------------------------------------------------------------
# HMDA Summary Operations (Enrichment 4)
# ---------------------------------------------------------------------------

def store_hmda_summaries_batch(
    conn: sqlite3.Connection,
    summaries: list[dict],
    batch_size: int = 1000,
) -> int:
    """Insert or replace HMDA institution summary records."""
    total_stored = 0
    sql = """
        INSERT OR REPLACE INTO hmda_institution_summary (
            lei, cert_number, institution_name, report_year,
            total_applications, total_originations, total_denials,
            denial_rate, avg_loan_amount, avg_interest_rate,
            total_loan_volume, lending_states, quality_score
        ) VALUES (
            :lei, :cert_number, :institution_name, :report_year,
            :total_applications, :total_originations, :total_denials,
            :denial_rate, :avg_loan_amount, :avg_interest_rate,
            :total_loan_volume, :lending_states, :quality_score
        )
    """
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i : i + batch_size]
        try:
            conn.executemany(sql, batch)
            conn.commit()
            total_stored += len(batch)
        except sqlite3.Error as e:
            conn.rollback()
            raise RuntimeError(f"Failed to store HMDA summaries batch at offset {i}: {e}")
    return total_stored


# ---------------------------------------------------------------------------
# Quality Score Operations
# ---------------------------------------------------------------------------

def update_quality_scores(conn: sqlite3.Connection) -> int:
    """
    Recompute quality scores for all financial institutions based on
    data completeness across all linked tables.

    Quality scoring formula (weights sum to 1.0):
        - has_institution_name: 0.10
        - has_location: 0.10
        - has_financial_data: 0.10
        - has_complaints_linked: 0.20
        - has_cra_rating: 0.15
        - has_enforcement_history: 0.15
        - has_regulator_info: 0.10
        - has_cert_number: 0.10

    Returns:
        Number of institutions updated.
    """
    # Updated quality scoring: enforcement check now includes unified
    # regulatory_enforcement table as well as legacy enforcement_actions
    sql = """
        UPDATE financial_institutions
        SET quality_score = (
            (CASE WHEN institution_name IS NOT NULL AND institution_name != '' THEN 0.10 ELSE 0.0 END) +
            (CASE WHEN city IS NOT NULL AND state IS NOT NULL THEN 0.10 ELSE 0.0 END) +
            (CASE WHEN cert_number IN (SELECT DISTINCT cert_number FROM institution_financials) THEN 0.10 ELSE 0.0 END) +
            (CASE WHEN cert_number IN (SELECT DISTINCT cert_number FROM institution_complaints) THEN 0.20 ELSE 0.0 END) +
            (CASE WHEN cert_number IN (SELECT DISTINCT cert_number FROM cra_ratings) THEN 0.15 ELSE 0.0 END) +
            (CASE WHEN (
                cert_number IN (SELECT DISTINCT institution_cert FROM enforcement_actions WHERE institution_cert IS NOT NULL)
                OR cert_number IN (SELECT DISTINCT cert_number FROM regulatory_enforcement WHERE cert_number IS NOT NULL)
            ) THEN 0.15 ELSE 0.0 END) +
            (CASE WHEN regulator IS NOT NULL AND regulator != '' THEN 0.10 ELSE 0.0 END) +
            (CASE WHEN cert_number IS NOT NULL THEN 0.10 ELSE 0.0 END)
        ),
        updated_at = CURRENT_TIMESTAMP
    """
    cursor = conn.execute(sql)
    conn.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Statistics / Aggregation Queries
# ---------------------------------------------------------------------------

def get_stats(conn: sqlite3.Connection) -> dict:
    """
    Compute summary statistics across all tables.

    Returns:
        Dictionary with keys:
            - total_complaints: int
            - total_institutions: int
            - total_cra_ratings: int
            - total_enforcement_actions: int
            - total_cross_links: int
            - avg_match_confidence: float
            - complaints_by_product: list[dict]
            - complaints_by_state: list[dict]
            - top_companies: list[dict]
            - institutions_with_enforcement: int
            - avg_quality_score: float
            - pipeline_runs: list[dict]
    """
    stats = {}

    # Total counts
    stats["total_complaints"] = conn.execute(
        "SELECT COUNT(*) FROM cfpb_complaints"
    ).fetchone()[0]

    stats["total_institutions"] = conn.execute(
        "SELECT COUNT(*) FROM financial_institutions"
    ).fetchone()[0]

    stats["total_cra_ratings"] = conn.execute(
        "SELECT COUNT(*) FROM cra_ratings"
    ).fetchone()[0]

    stats["total_enforcement_actions"] = conn.execute(
        "SELECT COUNT(*) FROM enforcement_actions"
    ).fetchone()[0]

    stats["total_cross_links"] = conn.execute(
        "SELECT COUNT(*) FROM institution_complaints"
    ).fetchone()[0]

    # Average match confidence
    row = conn.execute(
        "SELECT AVG(match_confidence) FROM institution_complaints"
    ).fetchone()
    stats["avg_match_confidence"] = round(row[0], 4) if row[0] else 0.0

    # Complaints by product (top 10)
    rows = conn.execute(
        """
        SELECT product, COUNT(*) as cnt
        FROM cfpb_complaints
        GROUP BY product
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()
    stats["complaints_by_product"] = [
        {"product": r["product"], "count": r["cnt"]} for r in rows
    ]

    # Complaints by state (top 10)
    rows = conn.execute(
        """
        SELECT state, COUNT(*) as cnt
        FROM cfpb_complaints
        WHERE state IS NOT NULL AND state != ''
        GROUP BY state
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()
    stats["complaints_by_state"] = [
        {"state": r["state"], "count": r["cnt"]} for r in rows
    ]

    # Top 10 companies by complaint volume
    rows = conn.execute(
        """
        SELECT company, COUNT(*) as cnt
        FROM cfpb_complaints
        GROUP BY company
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()
    stats["top_companies"] = [
        {"company": r["company"], "count": r["cnt"]} for r in rows
    ]

    # Institutions with at least one enforcement action
    stats["institutions_with_enforcement"] = conn.execute(
        """
        SELECT COUNT(DISTINCT institution_cert)
        FROM enforcement_actions
        WHERE institution_cert IS NOT NULL
        """
    ).fetchone()[0]

    # Average quality score
    row = conn.execute(
        "SELECT AVG(quality_score) FROM financial_institutions"
    ).fetchone()
    stats["avg_quality_score"] = round(row[0], 4) if row[0] else 0.0

    # Enrichment table counts
    stats["total_financials"] = conn.execute(
        "SELECT COUNT(*) FROM institution_financials"
    ).fetchone()[0]

    stats["institutions_with_financials"] = conn.execute(
        "SELECT COUNT(DISTINCT cert_number) FROM institution_financials"
    ).fetchone()[0]

    stats["total_regulatory_enforcement"] = conn.execute(
        "SELECT COUNT(*) FROM regulatory_enforcement"
    ).fetchone()[0]

    stats["total_risk_profiles"] = conn.execute(
        "SELECT COUNT(*) FROM institution_risk_profiles"
    ).fetchone()[0]

    stats["total_hmda_summaries"] = conn.execute(
        "SELECT COUNT(*) FROM hmda_institution_summary"
    ).fetchone()[0]

    # Regulatory enforcement by agency
    rows = conn.execute(
        "SELECT agency, COUNT(*) as cnt FROM regulatory_enforcement GROUP BY agency ORDER BY cnt DESC"
    ).fetchall()
    stats["enforcement_by_agency"] = [
        {"agency": r["agency"], "count": r["cnt"]} for r in rows
    ]

    # Risk tier distribution
    rows = conn.execute(
        "SELECT risk_tier, COUNT(*) as cnt FROM institution_risk_profiles "
        "WHERE risk_tier IS NOT NULL GROUP BY risk_tier ORDER BY cnt DESC"
    ).fetchall()
    stats["risk_tier_distribution"] = [
        {"risk_tier": r["risk_tier"], "count": r["cnt"]} for r in rows
    ]

    # Recent pipeline runs
    rows = conn.execute(
        """
        SELECT pipeline_name, started_at, completed_at,
               records_processed, records_failed, status
        FROM pipeline_runs
        ORDER BY started_at DESC
        LIMIT 10
        """
    ).fetchall()
    stats["pipeline_runs"] = [
        {
            "pipeline_name": r["pipeline_name"],
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "records_processed": r["records_processed"],
            "records_failed": r["records_failed"],
            "status": r["status"],
        }
        for r in rows
    ]

    return stats
