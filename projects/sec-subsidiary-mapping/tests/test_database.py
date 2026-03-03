"""Tests for database operations."""

import sqlite3
import pytest

from src.storage.database import (
    init_db,
    upsert_parent,
    upsert_filing,
    insert_subsidiary,
    insert_ownership_link,
    get_stats,
)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestInitDB:
    def test_creates_tables(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "parents" in names
        assert "filings" in names
        assert "subsidiaries" in names
        assert "ownership_links" in names
        assert "financials" in names


class TestUpsertParent:
    def test_insert(self, db):
        upsert_parent(db, {
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "ticker": "AAPL",
            "sic_code": "3571",
        })
        db.commit()
        row = db.execute("SELECT * FROM parents WHERE cik = ?", ("0000320193",)).fetchone()
        assert row["company_name"] == "Apple Inc."
        assert row["ticker"] == "AAPL"
        assert row["sic_code"] == "3571"

    def test_upsert_preserves_existing(self, db):
        upsert_parent(db, {
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "ticker": "AAPL",
            "sic_code": "3571",
        })
        # Update with partial data - should preserve existing
        upsert_parent(db, {
            "cik": "0000320193",
            "company_name": "APPLE INC",
            "ticker": "",
            "sic_code": "",
        })
        db.commit()
        row = db.execute("SELECT * FROM parents WHERE cik = ?", ("0000320193",)).fetchone()
        assert row["company_name"] == "APPLE INC"  # Updated
        assert row["ticker"] == "AAPL"  # Preserved
        assert row["sic_code"] == "3571"  # Preserved


class TestUpsertFiling:
    def test_insert(self, db):
        upsert_parent(db, {"cik": "0000320193", "company_name": "Apple"})
        upsert_filing(db, {
            "accession": "0000320193-24-000123",
            "cik": "0000320193",
            "filing_date": "2024-11-01",
            "filename": "exhibit21.htm",
            "exhibit_url": "https://sec.gov/...",
            "parse_method": "table",
            "subsidiary_count": 25,
        })
        db.commit()
        row = db.execute("SELECT * FROM filings WHERE accession = ?",
                        ("0000320193-24-000123",)).fetchone()
        assert row["subsidiary_count"] == 25
        assert row["parse_method"] == "table"


class TestInsertSubsidiary:
    def test_insert_new(self, db):
        sub_id = insert_subsidiary(db, {
            "name": "Apple Asia Limited",
            "name_normalized": "APPLE ASIA",
            "jurisdiction_raw": "Hong Kong",
            "jurisdiction_code": "HK",
            "jurisdiction_name": "Hong Kong",
            "jurisdiction_country": "HK",
            "is_tax_haven": True,
        })
        db.commit()
        assert sub_id > 0
        row = db.execute("SELECT * FROM subsidiaries WHERE id = ?", (sub_id,)).fetchone()
        assert row["name"] == "Apple Asia Limited"

    def test_deduplication(self, db):
        sub_id1 = insert_subsidiary(db, {
            "name": "Apple Asia Limited",
            "name_normalized": "APPLE ASIA",
            "jurisdiction_code": "HK",
        })
        sub_id2 = insert_subsidiary(db, {
            "name": "Apple Asia Limited",
            "name_normalized": "APPLE ASIA",
            "jurisdiction_code": "HK",
        })
        assert sub_id1 == sub_id2


class TestOwnershipLink:
    def test_insert(self, db):
        upsert_parent(db, {"cik": "0000320193", "company_name": "Apple"})
        sub_id = insert_subsidiary(db, {
            "name": "Apple Asia",
            "name_normalized": "APPLE ASIA",
            "jurisdiction_code": "HK",
        })
        upsert_filing(db, {
            "accession": "0000320193-24-000123",
            "cik": "0000320193",
            "filing_date": "2024-11-01",
        })
        insert_ownership_link(db, {
            "parent_cik": "0000320193",
            "subsidiary_id": sub_id,
            "filing_accession": "0000320193-24-000123",
            "filing_date": "2024-11-01",
            "ownership_pct": 100.0,
            "quality_score": 0.85,
        })
        db.commit()

        row = db.execute("SELECT * FROM ownership_links LIMIT 1").fetchone()
        assert row["parent_cik"] == "0000320193"
        assert row["ownership_pct"] == 100.0


class TestGetStats:
    def test_empty_db(self, db):
        stats = get_stats(db)
        assert stats["parent_count"] == 0
        assert stats["subsidiary_count"] == 0

    def test_with_data(self, db):
        upsert_parent(db, {"cik": "123", "company_name": "Test"})
        insert_subsidiary(db, {
            "name": "Sub1", "name_normalized": "SUB1",
            "jurisdiction_code": "DE",
        })
        db.commit()
        stats = get_stats(db)
        assert stats["parent_count"] == 1
        assert stats["subsidiary_count"] == 1
