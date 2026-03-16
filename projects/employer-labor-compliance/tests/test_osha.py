"""Tests for OSHA scraper and parser."""

import json
import pytest
from pathlib import Path

from src.scrapers.osha import parse_osha_data, _normalize_api_date, _safe_float, _safe_int


class TestNormalizeDateOSHA:
    def test_iso_datetime(self):
        assert _normalize_api_date("2024-01-15T00:00:00") == "2024-01-15"

    def test_iso_date(self):
        assert _normalize_api_date("2024-01-15") == "2024-01-15"

    def test_empty(self):
        assert _normalize_api_date("") == ""

    def test_none(self):
        assert _normalize_api_date(None) == ""


class TestParseOshaData:
    def test_basic(self, tmp_path):
        data = [
            {
                "activity_nr": 317722197,
                "reporting_id": "0453720",
                "estab_name": "ACME FACTORY",
                "site_address": "123 Main St",
                "site_city": "Chicago",
                "site_state": "IL",
                "site_zip": "60601",
                "naics_code": "722511",
                "sic_code": "5812",
                "insp_type": "G",
                "open_date": "2024-01-01T00:00:00",
                "close_case_date": "2024-03-01T00:00:00",
            }
        ]
        json_file = tmp_path / "osha.json"
        json_file.write_text(json.dumps(data))

        records = parse_osha_data(json_file, min_year=2020)
        assert len(records) == 1
        assert records[0]["activity_number"] == "317722197"
        assert records[0]["establishment_name"] == "ACME FACTORY"
        assert records[0]["site_state"] == "IL"
        assert records[0]["open_date"] == "2024-01-01"
        assert records[0]["close_date"] == "2024-03-01"

    def test_year_filter(self, tmp_path):
        data = [
            {"activity_nr": 100, "estab_name": "OLD", "open_date": "2010-01-01T00:00:00"},
            {"activity_nr": 101, "estab_name": "NEW", "open_date": "2024-01-01T00:00:00"},
        ]
        json_file = tmp_path / "osha.json"
        json_file.write_text(json.dumps(data))

        records = parse_osha_data(json_file, min_year=2015)
        assert len(records) == 1
        assert records[0]["establishment_name"] == "NEW"

    def test_null_activity_skipped(self, tmp_path):
        data = [
            {"activity_nr": None, "estab_name": "NOID", "open_date": "2024-01-01T00:00:00"},
            {"activity_nr": 101, "estab_name": "HASID", "open_date": "2024-01-01T00:00:00"},
        ]
        json_file = tmp_path / "osha.json"
        json_file.write_text(json.dumps(data))

        records = parse_osha_data(json_file, min_year=2020)
        assert len(records) == 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_osha_data(Path("/nonexistent/osha.json"))

    def test_violation_merge(self, tmp_path):
        """Test that violation aggregates are merged when available."""
        inspections = [
            {"activity_nr": 100, "estab_name": "TEST", "open_date": "2024-01-01T00:00:00"},
        ]
        violations = {
            "100": {
                "total_initial_penalty": 7500.0,
                "total_current_penalty": 5000.0,
                "num_violations": 3,
                "serious_violations": 2,
                "willful_violations": 0,
                "repeat_violations": 1,
            }
        }

        insp_file = tmp_path / "osha.json"
        insp_file.write_text(json.dumps(inspections))

        # Write violations cache next to inspections
        from src.scrapers.osha import VIOLATIONS_CACHE
        import src.scrapers.osha as osha_mod

        orig_cache = osha_mod.VIOLATIONS_CACHE
        viol_file = tmp_path / "osha_violations.json"
        viol_file.write_text(json.dumps(violations))
        osha_mod.VIOLATIONS_CACHE = viol_file

        try:
            records = parse_osha_data(insp_file, min_year=2020)
            assert records[0]["total_initial_penalty"] == 7500.0
            assert records[0]["total_current_penalty"] == 5000.0
            assert records[0]["num_violations"] == 3
            assert records[0]["serious_violations"] == 2
            assert records[0]["repeat_violations"] == 1
        finally:
            osha_mod.VIOLATIONS_CACHE = orig_cache

    def test_null_fields_default(self, tmp_path):
        data = [{"activity_nr": 300, "open_date": "2024-01-01T00:00:00"}]
        json_file = tmp_path / "osha.json"
        json_file.write_text(json.dumps(data))

        records = parse_osha_data(json_file, min_year=2020)
        assert records[0]["establishment_name"] == ""
        assert records[0]["total_current_penalty"] == 0.0
        assert records[0]["num_violations"] == 0
