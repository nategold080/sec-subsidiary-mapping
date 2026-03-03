"""Tests for export module."""

import sqlite3
import json
import pytest
from pathlib import Path

from src.storage.database import init_db, upsert_whd_case, upsert_osha_inspection
from src.export.exporter import _export_csv, _export_json, _export_markdown


@pytest.fixture
def populated_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    upsert_whd_case(conn, {
        "case_id": "123", "trade_name": "ACME CORP", "legal_name": "ACME",
        "street_address": "123 Main", "city": "Chicago", "state": "IL",
        "zip_code": "60601", "naics_code": "722511", "naics_description": "Restaurants",
        "findings_start_date": "2024-01-01", "findings_end_date": "2024-06-30",
        "back_wages_owed": 15000, "civil_penalties": 5000, "employees_affected": 12,
        "flsa_violated": 1, "mspa_violated": 0, "h1b_violated": 0,
        "fmla_violated": 0, "sca_violated": 0, "dba_violated": 0,
        "employer_normalized": "ACME", "quality_score": 0.85,
    })

    upsert_osha_inspection(conn, {
        "activity_number": "A123", "reporting_id": "R1",
        "establishment_name": "ACME CORP", "site_address": "123 Main",
        "site_city": "Chicago", "site_state": "IL", "site_zip": "60601",
        "naics_code": "722511", "sic_code": "5812",
        "inspection_type": "Complaint", "open_date": "2024-02-01", "close_date": "",
        "total_initial_penalty": 7500, "total_current_penalty": 5000,
        "num_violations": 3, "serious_violations": 2, "willful_violations": 0,
        "repeat_violations": 0, "fatalities": 0, "hospitalized": 0,
        "employer_normalized": "ACME", "quality_score": 0.80,
    })

    conn.commit()
    return conn


class TestExportCSV:
    def test_creates_files(self, populated_db, tmp_path):
        files = _export_csv(populated_db, tmp_path)
        assert len(files) >= 2
        # Check WHD CSV exists and has content
        whd_csv = tmp_path / "whd_cases.csv"
        assert whd_csv.exists()
        lines = whd_csv.read_text().strip().split("\n")
        assert len(lines) == 2  # header + 1 record

    def test_empty_db(self, tmp_path):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        files = _export_csv(conn, tmp_path)
        assert len(files) == 0


class TestExportJSON:
    def test_valid_json(self, populated_db, tmp_path):
        path = _export_json(populated_db, tmp_path)
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["metadata"]["project"] == "Employer Labor Compliance Tracker"
        assert len(data["whd_cases"]) == 1
        assert len(data["osha_inspections"]) == 1


class TestExportMarkdown:
    def test_creates_summary(self, populated_db, tmp_path):
        path = _export_markdown(populated_db, tmp_path)
        content = Path(path).read_text()
        assert "Employer Labor Compliance Tracker" in content
        assert "Nathan Goldberg" in content
        assert "WHD Wage & Hour Cases" in content
