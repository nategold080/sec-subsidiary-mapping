"""Tests for WHD scraper and parser."""

import json
import pytest
from pathlib import Path

from src.scrapers.whd import parse_whd_data, _normalize_api_date, _safe_float, _safe_int


class TestNormalizeDateWHD:
    def test_iso_datetime(self):
        assert _normalize_api_date("2024-01-15T00:00:00") == "2024-01-15"

    def test_iso_date(self):
        assert _normalize_api_date("2024-01-15") == "2024-01-15"

    def test_empty(self):
        assert _normalize_api_date("") == ""

    def test_none(self):
        assert _normalize_api_date(None) == ""


class TestSafeFloat:
    def test_normal(self):
        assert _safe_float(123.45) == 123.45

    def test_int(self):
        assert _safe_float(1234) == 1234.0

    def test_zero(self):
        assert _safe_float(0) == 0.0

    def test_none(self):
        assert _safe_float(None) == 0.0

    def test_string(self):
        assert _safe_float("123.45") == 123.45

    def test_invalid(self):
        assert _safe_float("abc") == 0.0


class TestSafeIntWHD:
    def test_normal(self):
        assert _safe_int(42) == 42

    def test_float(self):
        assert _safe_int(42.7) == 42

    def test_none(self):
        assert _safe_int(None) == 0

    def test_string(self):
        assert _safe_int("42") == 42


class TestParseWhdData:
    def test_basic(self, tmp_path):
        data = [
            {
                "case_id": 100,
                "trade_nm": "ACME",
                "legal_name": "ACME INC",
                "cty_nm": "Chicago",
                "st_cd": "IL",
                "naic_cd": "722511",
                "naics_code_description": "Full-Service Restaurants",
                "findings_start_date": "2024-01-01T00:00:00",
                "findings_end_date": "2024-06-01T00:00:00",
                "bw_atp_amt": 5000.0,
                "cmp_assd": 1000.0,
                "ee_atp_cnt": 10,
                "flsa_violtn_cnt": 1,
                "mspa_violtn_cnt": 0,
                "h1b_violtn_cnt": 0,
                "fmla_violtn_cnt": 0,
                "sca_violtn_cnt": 0,
                "dbra_violtn_cnt": 0,
            },
            {
                "case_id": 101,
                "trade_nm": "BETA",
                "legal_name": "BETA LLC",
                "cty_nm": "Springfield",
                "st_cd": "IL",
                "naic_cd": "722511",
                "findings_start_date": "2024-02-01T00:00:00",
                "bw_atp_amt": 3000.0,
                "cmp_assd": 500.0,
                "ee_atp_cnt": 5,
                "flsa_violtn_cnt": 0,
            },
        ]
        json_file = tmp_path / "whd.json"
        json_file.write_text(json.dumps(data))

        records = parse_whd_data(json_file, min_year=2020)
        assert len(records) == 2
        assert records[0]["case_id"] == "100"
        assert records[0]["trade_name"] == "ACME"
        assert records[0]["back_wages_owed"] == 5000.0
        assert records[0]["civil_penalties"] == 1000.0
        assert records[0]["flsa_violated"] == 1
        assert records[0]["findings_start_date"] == "2024-01-01"

    def test_year_filter(self, tmp_path):
        data = [
            {"case_id": 100, "trade_nm": "OLD", "findings_start_date": "2010-01-01T00:00:00"},
            {"case_id": 101, "trade_nm": "NEW", "findings_start_date": "2024-01-01T00:00:00"},
        ]
        json_file = tmp_path / "whd.json"
        json_file.write_text(json.dumps(data))

        records = parse_whd_data(json_file, min_year=2015)
        assert len(records) == 1
        assert records[0]["trade_name"] == "NEW"

    def test_null_case_id_skipped(self, tmp_path):
        data = [
            {"case_id": None, "trade_nm": "NOCASE", "findings_start_date": "2024-01-01T00:00:00"},
            {"case_id": 101, "trade_nm": "HASCASE", "findings_start_date": "2024-01-01T00:00:00"},
        ]
        json_file = tmp_path / "whd.json"
        json_file.write_text(json.dumps(data))

        records = parse_whd_data(json_file, min_year=2020)
        assert len(records) == 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_whd_data(Path("/nonexistent/whd.json"))

    def test_violation_flags(self, tmp_path):
        data = [
            {
                "case_id": 200,
                "trade_nm": "TEST",
                "findings_start_date": "2024-01-01T00:00:00",
                "flsa_violtn_cnt": 3,
                "h1b_violtn_cnt": 1,
                "fmla_violtn_cnt": 0,
                "mspa_violtn_cnt": 0,
                "sca_violtn_cnt": 0,
                "dbra_violtn_cnt": 2,
            }
        ]
        json_file = tmp_path / "whd.json"
        json_file.write_text(json.dumps(data))

        records = parse_whd_data(json_file, min_year=2020)
        assert records[0]["flsa_violated"] == 1
        assert records[0]["h1b_violated"] == 1
        assert records[0]["fmla_violated"] == 0
        assert records[0]["dba_violated"] == 1

    def test_null_fields_default(self, tmp_path):
        data = [{"case_id": 300, "findings_start_date": "2024-01-01T00:00:00"}]
        json_file = tmp_path / "whd.json"
        json_file.write_text(json.dumps(data))

        records = parse_whd_data(json_file, min_year=2020)
        assert records[0]["trade_name"] == ""
        assert records[0]["back_wages_owed"] == 0.0
        assert records[0]["employees_affected"] == 0
