"""SQLite database for SEC subsidiary mapping.

Uses WAL mode for concurrent reads. All functions accept optional conn
parameter for testing.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "sec_subsidiaries.db"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Get a database connection with WAL mode."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None):
    """Create all tables if they don't exist."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS parents (
            cik TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            ticker TEXT,
            sic_code TEXT,
            sic_description TEXT,
            state_of_incorporation TEXT,
            exchange TEXT,
            fiscal_year_end TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS filings (
            accession TEXT PRIMARY KEY,
            cik TEXT NOT NULL,
            form_type TEXT DEFAULT '10-K',
            filing_date TEXT,
            exhibit_filename TEXT,
            exhibit_url TEXT,
            parse_method TEXT,
            subsidiary_count INTEGER DEFAULT 0,
            raw_text_length INTEGER DEFAULT 0,
            parse_error TEXT,
            quality_score REAL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cik) REFERENCES parents(cik)
        );

        CREATE TABLE IF NOT EXISTS subsidiaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_normalized TEXT,
            jurisdiction_raw TEXT,
            jurisdiction_code TEXT,
            jurisdiction_name TEXT,
            jurisdiction_country TEXT,
            is_tax_haven INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ownership_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_cik TEXT NOT NULL,
            subsidiary_id INTEGER NOT NULL,
            filing_accession TEXT NOT NULL,
            filing_date TEXT,
            ownership_pct REAL,
            source_url TEXT,
            quality_score REAL,
            quality_components TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (parent_cik) REFERENCES parents(cik),
            FOREIGN KEY (subsidiary_id) REFERENCES subsidiaries(id),
            FOREIGN KEY (filing_accession) REFERENCES filings(accession)
        );

        CREATE TABLE IF NOT EXISTS financials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cik TEXT NOT NULL,
            fiscal_year INTEGER,
            revenue REAL,
            total_assets REAL,
            net_income REAL,
            employees INTEGER,
            source TEXT DEFAULT 'xbrl',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (cik) REFERENCES parents(cik)
        );

        CREATE INDEX IF NOT EXISTS idx_filings_cik ON filings(cik);
        CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date);
        CREATE INDEX IF NOT EXISTS idx_subs_name ON subsidiaries(name_normalized);
        CREATE INDEX IF NOT EXISTS idx_subs_jurisdiction ON subsidiaries(jurisdiction_code);
        CREATE INDEX IF NOT EXISTS idx_subs_tax_haven ON subsidiaries(is_tax_haven);
        CREATE INDEX IF NOT EXISTS idx_links_parent ON ownership_links(parent_cik);
        CREATE INDEX IF NOT EXISTS idx_links_sub ON ownership_links(subsidiary_id);
        CREATE INDEX IF NOT EXISTS idx_links_filing ON ownership_links(filing_accession);
        CREATE INDEX IF NOT EXISTS idx_financials_cik ON financials(cik);
    """)

    conn.commit()
    if close:
        conn.close()


def upsert_parent(conn: sqlite3.Connection, parent: dict):
    """Insert or update a parent company."""
    conn.execute("""
        INSERT INTO parents (cik, company_name, ticker, sic_code, sic_description,
                            state_of_incorporation, exchange, fiscal_year_end, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(cik) DO UPDATE SET
            company_name = excluded.company_name,
            ticker = CASE WHEN excluded.ticker != '' AND excluded.ticker IS NOT NULL THEN excluded.ticker ELSE parents.ticker END,
            sic_code = CASE WHEN excluded.sic_code != '' AND excluded.sic_code IS NOT NULL THEN excluded.sic_code ELSE parents.sic_code END,
            sic_description = CASE WHEN excluded.sic_description != '' AND excluded.sic_description IS NOT NULL THEN excluded.sic_description ELSE parents.sic_description END,
            state_of_incorporation = CASE WHEN excluded.state_of_incorporation != '' AND excluded.state_of_incorporation IS NOT NULL THEN excluded.state_of_incorporation ELSE parents.state_of_incorporation END,
            exchange = CASE WHEN excluded.exchange != '' AND excluded.exchange IS NOT NULL THEN excluded.exchange ELSE parents.exchange END,
            fiscal_year_end = CASE WHEN excluded.fiscal_year_end != '' AND excluded.fiscal_year_end IS NOT NULL THEN excluded.fiscal_year_end ELSE parents.fiscal_year_end END,
            updated_at = datetime('now')
    """, (
        parent.get("cik", ""),
        parent.get("company_name", "") or parent.get("name", ""),
        parent.get("ticker", ""),
        parent.get("sic_code", "") or parent.get("sic", ""),
        parent.get("sic_description", ""),
        parent.get("state_of_incorporation", ""),
        parent.get("exchange", ""),
        parent.get("fiscal_year_end", ""),
    ))


def upsert_filing(conn: sqlite3.Connection, filing: dict):
    """Insert or update a filing record."""
    conn.execute("""
        INSERT INTO filings (accession, cik, form_type, filing_date, exhibit_filename,
                            exhibit_url, parse_method, subsidiary_count, raw_text_length,
                            parse_error, quality_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(accession) DO UPDATE SET
            parse_method = excluded.parse_method,
            subsidiary_count = excluded.subsidiary_count,
            raw_text_length = excluded.raw_text_length,
            parse_error = excluded.parse_error,
            quality_score = excluded.quality_score
    """, (
        filing.get("accession", ""),
        filing.get("cik", ""),
        filing.get("form_type", "10-K"),
        filing.get("filing_date", "") or filing.get("file_date", ""),
        filing.get("exhibit_filename", "") or filing.get("filename", ""),
        filing.get("exhibit_url", ""),
        filing.get("parse_method", ""),
        filing.get("subsidiary_count", 0),
        filing.get("raw_text_length", 0),
        filing.get("parse_error"),
        filing.get("quality_score"),
    ))


def insert_subsidiary(conn: sqlite3.Connection, sub: dict) -> int:
    """Insert a subsidiary and return its ID. Deduplicates by name+jurisdiction."""
    # Check for existing
    row = conn.execute("""
        SELECT id FROM subsidiaries
        WHERE name_normalized = ? AND jurisdiction_code = ?
    """, (
        sub.get("name_normalized", ""),
        sub.get("jurisdiction_code", ""),
    )).fetchone()

    if row:
        return row["id"]

    cursor = conn.execute("""
        INSERT INTO subsidiaries (name, name_normalized, jurisdiction_raw,
                                 jurisdiction_code, jurisdiction_name,
                                 jurisdiction_country, is_tax_haven)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        sub.get("name", ""),
        sub.get("name_normalized", ""),
        sub.get("jurisdiction_raw", ""),
        sub.get("jurisdiction_code", ""),
        sub.get("jurisdiction_name", ""),
        sub.get("jurisdiction_country", ""),
        1 if sub.get("is_tax_haven") else 0,
    ))
    return cursor.lastrowid


def insert_ownership_link(conn: sqlite3.Connection, link: dict):
    """Insert an ownership link between parent and subsidiary."""
    conn.execute("""
        INSERT INTO ownership_links (parent_cik, subsidiary_id, filing_accession,
                                    filing_date, ownership_pct, source_url,
                                    quality_score, quality_components)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        link.get("parent_cik", ""),
        link.get("subsidiary_id", 0),
        link.get("filing_accession", ""),
        link.get("filing_date", ""),
        link.get("ownership_pct"),
        link.get("source_url", ""),
        link.get("quality_score"),
        json.dumps(link.get("quality_components", {})),
    ))


def get_stats(conn: Optional[sqlite3.Connection] = None) -> dict:
    """Get summary statistics from the database."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        stats = {}
        stats["parent_count"] = conn.execute("SELECT COUNT(*) FROM parents").fetchone()[0]
        stats["filing_count"] = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
        stats["subsidiary_count"] = conn.execute("SELECT COUNT(*) FROM subsidiaries").fetchone()[0]
        stats["link_count"] = conn.execute("SELECT COUNT(*) FROM ownership_links").fetchone()[0]

        stats["tax_haven_count"] = conn.execute(
            "SELECT COUNT(*) FROM subsidiaries WHERE is_tax_haven = 1"
        ).fetchone()[0]

        row = conn.execute(
            "SELECT COUNT(DISTINCT jurisdiction_code) FROM subsidiaries WHERE jurisdiction_code != ''"
        ).fetchone()
        stats["jurisdiction_count"] = row[0] if row else 0

        row = conn.execute(
            "SELECT AVG(quality_score) FROM ownership_links WHERE quality_score IS NOT NULL"
        ).fetchone()
        stats["avg_quality"] = round(row[0], 4) if row and row[0] else 0.0

        row = conn.execute(
            "SELECT MIN(filing_date), MAX(filing_date) FROM filings WHERE filing_date != ''"
        ).fetchone()
        stats["date_range"] = (row[0], row[1]) if row else (None, None)

        return stats
    finally:
        if close:
            conn.close()
