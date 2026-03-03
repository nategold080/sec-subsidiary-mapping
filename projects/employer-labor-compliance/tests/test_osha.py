"""Tests for OSHA scraper and parser."""

import pytest
from pathlib import Path

from src.scrapers.osha import parse_osha_csv, _normalize_date, _safe_float, _safe_int


class TestNormalizeDateOSHA:
    def test_iso(self):
        assert _normalize_date("2024-01-15") == "2024-01-15"

    def test_slash(self):
        assert _normalize_date("01/15/2024") == "2024-01-15"

    def test_empty(self):
        assert _normalize_date("") == ""


class TestParseOshaCsv:
    def test_basic(self, tmp_path):
        csv_file = tmp_path / "osha.csv"
        csv_file.write_text(
            "activity_nr,reporting_id,estab_name,site_address,site_city,site_state,site_zip,"
            "naics_code,sic_code,insp_type,open_date,close_case_date,"
            "total_initial_penalty,total_current_penalty,"
            "total_violations,serious_violations,willful_violations,repeat_violations,"
            "nr_in_state_fatality,nr_in_state_inpatient\n"
            "A100,R1,ACME,123 Main,Chicago,IL,60601,722511,5812,Complaint,2024-01-01,,"
            "7500,5000,3,2,0,0,0,0\n"
        )
        records = parse_osha_csv(csv_file, min_year=2020)
        assert len(records) == 1
        assert records[0]["activity_number"] == "A100"
        assert records[0]["establishment_name"] == "ACME"
        assert records[0]["total_current_penalty"] == 5000.0
        assert records[0]["serious_violations"] == 2

    def test_year_filter(self, tmp_path):
        csv_file = tmp_path / "osha.csv"
        csv_file.write_text(
            "activity_nr,estab_name,open_date\n"
            "A100,OLD,2010-01-01\n"
            "A101,NEW,2024-01-01\n"
        )
        records = parse_osha_csv(csv_file, min_year=2015)
        assert len(records) == 1
        assert records[0]["establishment_name"] == "NEW"

    def test_empty_activity_skipped(self, tmp_path):
        csv_file = tmp_path / "osha.csv"
        csv_file.write_text(
            "activity_nr,estab_name,open_date\n"
            ",NOID,2024-01-01\n"
            "A101,HASID,2024-01-01\n"
        )
        records = parse_osha_csv(csv_file, min_year=2020)
        assert len(records) == 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_osha_csv(Path("/nonexistent/osha.csv"))
