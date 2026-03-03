"""Tests for NLRB scraper and parser."""

import json
import sqlite3
import pytest
from pathlib import Path

from src.scrapers.nlrb import (
    parse_nlrb_csv,
    parse_nlrb_db,
    parse_nlrb_jsonl,
    _parse_nlrb_case,
    _normalize_date,
    _safe_int,
)


class TestNormalizeDateNLRB:
    def test_iso(self):
        assert _normalize_date("2024-01-15") == "2024-01-15"

    def test_slash_format(self):
        assert _normalize_date("01/15/2024") == "2024-01-15"

    def test_iso_datetime(self):
        assert _normalize_date("2024-01-15T10:30:00Z") == "2024-01-15"

    def test_empty(self):
        assert _normalize_date("") == ""

    def test_none(self):
        assert _normalize_date(None) == ""


class TestSafeIntNLRB:
    def test_normal(self):
        assert _safe_int("42") == 42

    def test_comma(self):
        assert _safe_int("1,234") == 1234

    def test_float_str(self):
        assert _safe_int("42.7") == 42

    def test_empty(self):
        assert _safe_int("") == 0

    def test_none(self):
        assert _safe_int(None) == 0

    def test_invalid(self):
        assert _safe_int("abc") == 0


class TestParseNlrbCase:
    def test_full_case(self):
        case = {
            "case_number": "13-CA-321456",
            "case_name": "ACME CORP",
            "date_filed": "2024-01-15",
            "date_closed": "2024-06-30",
            "status": "Closed",
            "case_type": "CA",
            "allegation": "8(a)(1) Interference",
            "city": "Chicago",
            "state": "IL",
            "num_employees": "50",
        }
        rec = _parse_nlrb_case(case)
        assert rec["case_number"] == "13-CA-321456"
        assert rec["case_name"] == "ACME CORP"
        assert rec["case_type"] == "CA"

    def test_extract_case_type_from_number(self):
        case = {"case_number": "13-CB-999999", "case_name": "TEST"}
        rec = _parse_nlrb_case(case)
        assert rec["case_type"] == "C"

    def test_camel_case_fields(self):
        case = {
            "caseNumber": "01-CA-100",
            "caseName": "TEST CORP",
            "dateFiled": "2024-03-01",
            "caseStatus": "Open",
            "caseType": "CA",
        }
        rec = _parse_nlrb_case(case)
        assert rec["case_number"] == "01-CA-100"
        assert rec["case_name"] == "TEST CORP"
        assert rec["status"] == "Open"

    def test_empty_case(self):
        rec = _parse_nlrb_case({})
        assert rec["case_number"] == ""
        assert rec["case_name"] == ""


class TestParseNlrbCsv:
    def test_basic(self, tmp_path):
        csv_file = tmp_path / "nlrb.csv"
        csv_file.write_text(
            "case_number,case_name,date_filed,status,case_type,allegation,city,state\n"
            "13-CA-100,ACME,2024-01-01,Open,CA,8(a)(1),Chicago,IL\n"
            "13-CA-101,BETA,2024-02-01,Closed,CA,,Springfield,IL\n"
        )
        records = parse_nlrb_csv(csv_file, min_year=2020)
        assert len(records) == 2
        assert records[0]["case_number"] == "13-CA-100"

    def test_year_filter(self, tmp_path):
        csv_file = tmp_path / "nlrb.csv"
        csv_file.write_text(
            "case_number,case_name,date_filed,status\n"
            "13-CA-100,OLD,2010-01-01,Closed\n"
            "13-CA-101,NEW,2024-01-01,Open\n"
        )
        records = parse_nlrb_csv(csv_file, min_year=2015)
        assert len(records) == 1
        assert records[0]["case_name"] == "NEW"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_nlrb_csv(Path("/nonexistent/file.csv"))


class TestParseNlrbJsonl:
    def test_basic(self, tmp_path):
        jsonl_file = tmp_path / "nlrb.jsonl"
        cases = [
            {"case_number": "13-CA-100", "case_name": "ACME", "date_filed": "2024-01-01"},
            {"case_number": "13-CA-101", "case_name": "BETA", "date_filed": "2024-02-01"},
        ]
        with open(jsonl_file, "w") as f:
            for case in cases:
                f.write(json.dumps(case) + "\n")

        records = parse_nlrb_jsonl(jsonl_file)
        assert len(records) == 2

    def test_empty_lines(self, tmp_path):
        jsonl_file = tmp_path / "nlrb.jsonl"
        jsonl_file.write_text(
            '{"case_number": "13-CA-100", "case_name": "ACME"}\n\n\n'
            '{"case_number": "13-CA-101", "case_name": "BETA"}\n'
        )
        records = parse_nlrb_jsonl(jsonl_file)
        assert len(records) == 2


class TestParseNlrbDb:
    def test_basic(self, tmp_path):
        db_path = tmp_path / "nlrb.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE filing (
                case_number TEXT PRIMARY KEY,
                name TEXT,
                case_type TEXT,
                date_filed TEXT,
                date_closed TEXT,
                status TEXT,
                city TEXT,
                state TEXT,
                number_of_eligible_voters INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE allegation (
                case_number TEXT,
                allegation TEXT
            )
        """)
        conn.execute(
            "INSERT INTO filing VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("13-CA-100", "ACME CORP", "CA", "2024-01-15", "", "Open", "Chicago", "IL", 50),
        )
        conn.execute(
            "INSERT INTO allegation VALUES (?, ?)",
            ("13-CA-100", "8(a)(1) Interference"),
        )
        conn.commit()
        conn.close()

        records = parse_nlrb_db(db_path, min_year=2020)
        assert len(records) == 1
        assert records[0]["case_number"] == "13-CA-100"
        assert records[0]["case_name"] == "ACME CORP"
        assert "8(a)(1)" in records[0]["allegation"]

    def test_year_filter(self, tmp_path):
        db_path = tmp_path / "nlrb.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE filing (
                case_number TEXT PRIMARY KEY, name TEXT, case_type TEXT,
                date_filed TEXT, date_closed TEXT, status TEXT,
                city TEXT, state TEXT, number_of_eligible_voters INTEGER
            )
        """)
        conn.execute("CREATE TABLE allegation (case_number TEXT, allegation TEXT)")
        conn.execute(
            "INSERT INTO filing VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("13-CA-100", "OLD", "CA", "2010-01-15", "", "Closed", "Chicago", "IL", 0),
        )
        conn.execute(
            "INSERT INTO filing VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("13-CA-101", "NEW", "CA", "2024-01-15", "", "Open", "Chicago", "IL", 50),
        )
        conn.commit()
        conn.close()

        records = parse_nlrb_db(db_path, min_year=2015)
        assert len(records) == 1
        assert records[0]["case_name"] == "NEW"
