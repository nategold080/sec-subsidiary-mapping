"""Tests for cross-linking engine."""

import sqlite3
import pytest

from src.storage.database import (
    init_db, upsert_whd_case, upsert_osha_inspection, upsert_nlrb_case,
)
from src.normalization.cross_linker import cross_link_all, _link_exact, _link_fuzzy


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _whd(conn, case_id="123", trade_name="ACME CORP", state="IL", **kw):
    rec = {
        "case_id": case_id, "trade_name": trade_name, "legal_name": "",
        "street_address": "", "city": "Chicago", "state": state,
        "zip_code": "", "naics_code": "722511", "naics_description": "Restaurants",
        "findings_start_date": "2024-01-01", "findings_end_date": "",
        "back_wages_owed": 5000, "civil_penalties": 1000, "employees_affected": 5,
        "flsa_violated": 1, "mspa_violated": 0, "h1b_violated": 0,
        "fmla_violated": 0, "sca_violated": 0, "dba_violated": 0,
        "employer_normalized": "ACME", "quality_score": 0.8,
    }
    rec.update(kw)
    upsert_whd_case(conn, rec)


def _osha(conn, activity_number="A456", name="ACME CORP", state="IL", **kw):
    rec = {
        "activity_number": activity_number, "reporting_id": "",
        "establishment_name": name, "site_address": "",
        "site_city": "Chicago", "site_state": state, "site_zip": "",
        "naics_code": "722511", "sic_code": "",
        "inspection_type": "Complaint", "open_date": "2024-02-01", "close_date": "",
        "total_initial_penalty": 0, "total_current_penalty": 5000,
        "num_violations": 2, "serious_violations": 1, "willful_violations": 0,
        "repeat_violations": 0, "fatalities": 0, "hospitalized": 0,
        "employer_normalized": "ACME", "quality_score": 0.8,
    }
    rec.update(kw)
    upsert_osha_inspection(conn, rec)


def _nlrb(conn, case_number="13-CA-100", case_name="ACME CORP", state="IL", **kw):
    rec = {
        "case_number": case_number, "case_name": case_name,
        "date_filed": "2024-03-01", "date_closed": "",
        "status": "Open", "case_type": "CA",
        "allegation": "8(a)(1)", "city": "Chicago", "state": state,
        "num_employees": 50, "unit_description": "", "union_name": "",
        "employer_normalized": "ACME", "quality_score": 0.75,
    }
    rec.update(kw)
    upsert_nlrb_case(conn, rec)


class TestLinkExact:
    def test_whd_osha_match(self, db):
        _whd(db)
        _osha(db)
        db.commit()
        matches = _link_exact(db)
        assert matches >= 1

    def test_all_three_sources(self, db):
        _whd(db)
        _osha(db)
        _nlrb(db)
        db.commit()
        matches = _link_exact(db)
        assert matches >= 3  # WHD-OSHA, WHD-NLRB, OSHA-NLRB

    def test_no_match_different_names(self, db):
        _whd(db, employer_normalized="ACME")
        _osha(db, employer_normalized="BETA")
        db.commit()
        matches = _link_exact(db)
        assert matches == 0

    def test_empty_db(self, db):
        matches = _link_exact(db)
        assert matches == 0


class TestLinkFuzzy:
    def test_similar_names(self, db):
        _whd(db, employer_normalized="ACME SERVICES")
        _osha(db, employer_normalized="ACME SERVICE")
        db.commit()
        matches = _link_fuzzy(db)
        assert matches >= 1

    def test_different_states_no_match(self, db):
        _whd(db, state="IL", employer_normalized="ACME SERVICES")
        _osha(db, state="CA", employer_normalized="ACME SERVICE")
        db.commit()
        matches = _link_fuzzy(db)
        assert matches == 0


class TestCrossLinkAll:
    def test_full_pipeline(self, db):
        _whd(db)
        _osha(db)
        _nlrb(db)
        db.commit()
        results = cross_link_all(db)
        assert results["exact_matches"] >= 1
        assert results["employers_created"] >= 1

    def test_creates_employer_profile(self, db):
        _whd(db)
        _osha(db)
        db.commit()
        cross_link_all(db)

        emp = db.execute("SELECT * FROM employers WHERE name_normalized = 'ACME'").fetchone()
        assert emp is not None
        assert emp["whd_case_count"] >= 1
        assert emp["osha_inspection_count"] >= 1
        assert emp["compliance_score"] < 1.0  # Should have some penalty

    def test_compliance_score_assigned(self, db):
        _whd(db, back_wages_owed=100000, civil_penalties=50000)
        _osha(db, total_current_penalty=50000, fatalities=1, willful_violations=2)
        _nlrb(db)
        db.commit()
        cross_link_all(db)

        emp = db.execute("SELECT * FROM employers WHERE name_normalized = 'ACME'").fetchone()
        assert emp["compliance_score"] < 0.7  # Significant violations
