"""Tests for database operations."""

import sqlite3
import pytest

from src.storage.database import (
    init_db, upsert_whd_case, upsert_osha_inspection, upsert_nlrb_case,
    upsert_employer, insert_cross_link, get_stats,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _whd_record(**kw):
    defaults = {
        "case_id": "1234567", "trade_name": "ACME CORP", "legal_name": "ACME CORPORATION",
        "street_address": "123 Main St", "city": "Springfield", "state": "IL",
        "zip_code": "62701", "naics_code": "722511", "naics_description": "Full-Service Restaurants",
        "findings_start_date": "2024-01-15", "findings_end_date": "2024-06-30",
        "back_wages_owed": 15000.0, "civil_penalties": 5000.0, "employees_affected": 12,
        "flsa_violated": 1, "mspa_violated": 0, "h1b_violated": 0,
        "fmla_violated": 0, "sca_violated": 0, "dba_violated": 0,
        "employer_normalized": "ACME", "quality_score": 0.85,
    }
    defaults.update(kw)
    return defaults


def _osha_record(**kw):
    defaults = {
        "activity_number": "A9876543", "reporting_id": "R123",
        "establishment_name": "ACME CORP", "site_address": "123 Main St",
        "site_city": "Springfield", "site_state": "IL", "site_zip": "62701",
        "naics_code": "722511", "sic_code": "5812",
        "inspection_type": "Complaint", "open_date": "2024-02-01", "close_date": "2024-04-15",
        "total_initial_penalty": 7500.0, "total_current_penalty": 5000.0,
        "num_violations": 3, "serious_violations": 2, "willful_violations": 0,
        "repeat_violations": 0, "fatalities": 0, "hospitalized": 0,
        "employer_normalized": "ACME", "quality_score": 0.80,
    }
    defaults.update(kw)
    return defaults


def _nlrb_record(**kw):
    defaults = {
        "case_number": "13-CA-321456", "case_name": "ACME CORP",
        "date_filed": "2024-03-10", "date_closed": "",
        "status": "Open", "case_type": "C",
        "allegation": "8(a)(1) Interference", "city": "Springfield", "state": "IL",
        "num_employees": 50, "unit_description": "All employees",
        "union_name": "SEIU Local 1", "employer_normalized": "ACME",
        "quality_score": 0.75,
    }
    defaults.update(kw)
    return defaults


class TestInitDB:
    def test_tables_created(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {t["name"] for t in tables}
        assert "whd_cases" in names
        assert "osha_inspections" in names
        assert "nlrb_cases" in names
        assert "employers" in names
        assert "cross_links" in names


class TestUpsertWHD:
    def test_insert(self, db):
        upsert_whd_case(db, _whd_record())
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM whd_cases").fetchone()[0]
        assert count == 1

    def test_upsert(self, db):
        upsert_whd_case(db, _whd_record(back_wages_owed=100))
        db.commit()
        upsert_whd_case(db, _whd_record(back_wages_owed=200))
        db.commit()
        row = db.execute("SELECT back_wages_owed FROM whd_cases").fetchone()
        assert row["back_wages_owed"] == 200


class TestUpsertOSHA:
    def test_insert(self, db):
        upsert_osha_inspection(db, _osha_record())
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM osha_inspections").fetchone()[0]
        assert count == 1


class TestUpsertNLRB:
    def test_insert(self, db):
        upsert_nlrb_case(db, _nlrb_record())
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM nlrb_cases").fetchone()[0]
        assert count == 1


class TestCrossLinks:
    def test_insert(self, db):
        link = {
            "source_type": "whd", "source_id": "1234567",
            "target_type": "osha", "target_id": "A9876543",
            "link_method": "exact_name", "confidence": 0.95,
        }
        result = insert_cross_link(db, link)
        assert result is not None

    def test_duplicate(self, db):
        link = {
            "source_type": "whd", "source_id": "1234567",
            "target_type": "osha", "target_id": "A9876543",
            "link_method": "exact_name", "confidence": 0.95,
        }
        insert_cross_link(db, link)
        db.commit()
        result = insert_cross_link(db, link)
        assert result is None


class TestEmployers:
    def test_upsert(self, db):
        rec = {
            "name_normalized": "ACME", "trade_names": "Acme Corp",
            "naics_code": "722511", "primary_state": "IL",
            "whd_case_count": 3, "osha_inspection_count": 2, "nlrb_case_count": 1,
            "total_back_wages": 50000, "total_penalties": 15000,
            "total_fatalities": 0, "compliance_score": 0.65,
        }
        result = upsert_employer(db, rec)
        assert result > 0
        count = db.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
        assert count == 1


class TestGetStats:
    def test_empty(self, db):
        stats = get_stats(db)
        assert stats["whd_count"] == 0
        assert stats["osha_count"] == 0
        assert stats["nlrb_count"] == 0

    def test_with_data(self, db):
        upsert_whd_case(db, _whd_record())
        upsert_osha_inspection(db, _osha_record())
        upsert_nlrb_case(db, _nlrb_record())
        db.commit()

        stats = get_stats(db)
        assert stats["whd_count"] == 1
        assert stats["osha_count"] == 1
        assert stats["nlrb_count"] == 1
        assert stats["total_back_wages"] == 15000.0
