"""Tests for quality scoring."""

import pytest
from src.validation.quality import (
    score_whd_case, score_osha_inspection, score_nlrb_case,
    compute_compliance_score,
)


class TestScoreWHD:
    def test_full_record(self):
        rec = {
            "case_id": "123", "trade_name": "ACME",
            "state": "IL", "city": "Chicago",
            "naics_code": "722511",
            "findings_start_date": "2024-01-01",
            "back_wages_owed": 5000, "civil_penalties": 1000,
            "employees_affected": 10,
            "flsa_violated": 1,
        }
        qs = score_whd_case(rec)
        assert qs.score > 0.8

    def test_minimal_record(self):
        rec = {"case_id": "123", "trade_name": "ACME"}
        qs = score_whd_case(rec)
        assert 0.2 < qs.score < 0.5

    def test_empty_record(self):
        qs = score_whd_case({})
        assert qs.score == 0.0


class TestScoreOSHA:
    def test_full_record(self):
        rec = {
            "activity_number": "A123", "establishment_name": "ACME",
            "site_state": "IL", "site_city": "Chicago",
            "naics_code": "722511", "open_date": "2024-01-01",
            "total_current_penalty": 5000, "num_violations": 3,
            "inspection_type": "Complaint",
        }
        qs = score_osha_inspection(rec)
        assert qs.score > 0.8

    def test_empty(self):
        qs = score_osha_inspection({})
        assert qs.score == 0.0


class TestScoreNLRB:
    def test_full_record(self):
        rec = {
            "case_number": "13-CA-123", "case_name": "ACME",
            "date_filed": "2024-01-01", "status": "Open",
            "case_type": "C", "state": "IL", "city": "Chicago",
            "allegation": "8(a)(1)",
        }
        qs = score_nlrb_case(rec)
        assert qs.score > 0.8

    def test_empty(self):
        qs = score_nlrb_case({})
        assert qs.score == 0.0


class TestComplianceScore:
    def test_clean_employer(self):
        score = compute_compliance_score()
        assert score == 1.0

    def test_minor_violation(self):
        score = compute_compliance_score(whd_cases=1, total_back_wages=5000)
        assert 0.6 < score < 0.95

    def test_multi_agency(self):
        score = compute_compliance_score(
            whd_cases=5, osha_inspections=3, nlrb_cases=2,
            total_back_wages=100000, total_penalties=50000,
        )
        assert score < 0.5

    def test_fatality(self):
        score = compute_compliance_score(
            osha_inspections=1, total_fatalities=1,
        )
        assert score < 0.9  # Fatality should reduce score noticeably

    def test_worst_case(self):
        score = compute_compliance_score(
            whd_cases=50, osha_inspections=30, nlrb_cases=20,
            total_back_wages=5000000, total_penalties=2000000,
            total_fatalities=5, willful_violations=10,
        )
        assert score < 0.2
