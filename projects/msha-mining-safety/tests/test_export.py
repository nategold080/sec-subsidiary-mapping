"""Tests for exporter module."""

import sqlite3
import os
import pytest
from src.storage.database import init_db, upsert_mines_batch
from src.export.exporter import export_all, _build_summary


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn=conn)
    return conn


class TestExportAll:
    def test_empty_db(self, db, tmp_path):
        # Patch EXPORT_DIR
        import src.export.exporter as exp
        orig = exp.EXPORT_DIR
        exp.EXPORT_DIR = str(tmp_path)
        try:
            results = export_all(db)
            assert results["mines_csv"] == 0
            assert results["accidents_csv"] == 0
            assert os.path.exists(tmp_path / "summary.md")
        finally:
            exp.EXPORT_DIR = orig

    def test_with_mines(self, db, tmp_path):
        import src.export.exporter as exp
        orig = exp.EXPORT_DIR
        exp.EXPORT_DIR = str(tmp_path)
        try:
            rec = {"mine_id": "M1", "mine_name": "Test", "coal_metal_ind": "C",
                   "mine_type": "Surface", "mine_status": "Active", "status_date": "",
                   "controller_id": "", "controller_name": "", "operator_id": "O1",
                   "operator_name": "Op", "state": "WV", "fips_cnty_cd": "", "fips_cnty_nm": "",
                   "company_type": "", "district": "", "primary_sic": "", "primary_sic_cd": "",
                   "secondary_sic": "", "latitude": "", "longitude": "", "no_employees": 10,
                   "days_per_week": 5, "hours_per_shift": 8, "nearest_town": "",
                   "quality_score": 0.8}
            upsert_mines_batch([rec], conn=db)
            results = export_all(db)
            assert results["mines_csv"] == 1
        finally:
            exp.EXPORT_DIR = orig


class TestBuildSummary:
    def test_output(self):
        stats = {"mines": 100, "active_mines": 50, "accidents": 200,
                 "total_fatalities": 5, "total_permanent_disabilities": 10,
                 "inspections": 1000, "violations": 5000,
                 "assessed_violations": 4000, "penalties": 300,
                 "total_proposed_penalties": 1500000, "total_paid_penalties": 1200000,
                 "operator_profiles": 80, "states_covered": 20,
                 "accident_year_range": "2000–2024"}
        summary = _build_summary(stats)
        assert "MSHA" in summary
        assert "100" in summary
        assert "Nathan Goldberg" in summary
