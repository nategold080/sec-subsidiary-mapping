"""Tests for WHD scraper and parser."""

import pytest
from pathlib import Path

from src.scrapers.whd import parse_whd_csv, _normalize_date, _safe_float, _safe_int


class TestNormalizeDateWHD:
    def test_iso(self):
        assert _normalize_date("2024-01-15") == "2024-01-15"

    def test_slash(self):
        assert _normalize_date("01/15/2024") == "2024-01-15"

    def test_empty(self):
        assert _normalize_date("") == ""


class TestSafeFloat:
    def test_normal(self):
        assert _safe_float("123.45") == 123.45

    def test_comma(self):
        assert _safe_float("1,234.56") == 1234.56

    def test_empty(self):
        assert _safe_float("") == 0.0

    def test_invalid(self):
        assert _safe_float("abc") == 0.0


class TestSafeIntWHD:
    def test_normal(self):
        assert _safe_int("42") == 42

    def test_float_str(self):
        assert _safe_int("42.7") == 42

    def test_comma(self):
        assert _safe_int("1,234") == 1234

    def test_empty(self):
        assert _safe_int("") == 0


class TestParseWhdCsv:
    def test_basic(self, tmp_path):
        csv_file = tmp_path / "whd.csv"
        csv_file.write_text(
            "case_id,trade_nm,legal_name,cty_nm,st_cd,naic_cd,findings_start_date,bw_atp_amt,cmp_assd_cnt,ee_atp_cnt,flsa_violtn_cnt\n"
            "100,ACME,ACME INC,Chicago,IL,722511,2024-01-01,5000,1000,10,1\n"
            "101,BETA,BETA LLC,Springfield,IL,722511,2024-02-01,3000,500,5,0\n"
        )
        records = parse_whd_csv(csv_file, min_year=2020)
        assert len(records) == 2
        assert records[0]["case_id"] == "100"
        assert records[0]["trade_name"] == "ACME"
        assert records[0]["back_wages_owed"] == 5000.0
        assert records[0]["flsa_violated"] == 1

    def test_year_filter(self, tmp_path):
        csv_file = tmp_path / "whd.csv"
        csv_file.write_text(
            "case_id,trade_nm,findings_start_date\n"
            "100,OLD,2010-01-01\n"
            "101,NEW,2024-01-01\n"
        )
        records = parse_whd_csv(csv_file, min_year=2015)
        assert len(records) == 1
        assert records[0]["trade_name"] == "NEW"

    def test_empty_case_id_skipped(self, tmp_path):
        csv_file = tmp_path / "whd.csv"
        csv_file.write_text(
            "case_id,trade_nm,findings_start_date\n"
            ",NOCASE,2024-01-01\n"
            "101,HASCASE,2024-01-01\n"
        )
        records = parse_whd_csv(csv_file, min_year=2020)
        assert len(records) == 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_whd_csv(Path("/nonexistent/whd.csv"))
