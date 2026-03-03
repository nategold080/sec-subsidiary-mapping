"""Tests for investigation parsing."""

import pytest
from src.scrapers.investigations import _safe_int, _normalize_date, _parse_api_investigation


class TestSafeInt:
    def test_normal(self):
        assert _safe_int("2023") == 2023

    def test_float_string(self):
        assert _safe_int("2023.0") == 2023

    def test_empty(self):
        assert _safe_int("") == 0

    def test_none(self):
        assert _safe_int(None) == 0

    def test_garbage(self):
        assert _safe_int("N/A") == 0


class TestNormalizeDate:
    def test_yyyymmdd(self):
        assert _normalize_date("20230615") == "2023-06-15"

    def test_empty(self):
        assert _normalize_date("") == ""

    def test_already_formatted(self):
        assert _normalize_date("2023-06-15") == "2023-06-15"


class TestParseApiInvestigation:
    def test_standard(self):
        item = {
            "investigationNumber": "PE25001",
            "nhtsaId": "102000",
            "investigationType": "PE",
            "status": "Open",
            "openDate": "2025-01-15",
            "subject": "Air bag failure",
            "description": "Multiple <b>reports</b> of air bag non-deployment.",
            "issueYear": 2024,
        }
        rec = _parse_api_investigation(item)
        assert rec["investigation_number"] == "PE25001"
        assert rec["investigation_type"] == "PE"
        assert rec["status"] == "Open"
        assert rec["model_year_start"] == 2024
        # HTML should be stripped
        assert "<b>" not in rec["description"]
        assert "reports" in rec["description"]

    def test_no_inv_number(self):
        assert _parse_api_investigation({}) is None

    def test_missing_fields(self):
        item = {"investigationNumber": "EA25010"}
        rec = _parse_api_investigation(item)
        assert rec["investigation_type"] == ""
        assert rec["model_year_start"] == 0
