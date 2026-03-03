"""Tests for export module."""

import sqlite3
from pathlib import Path

import pytest

from src.storage.database import init_db, upsert_complaint, upsert_recall, upsert_investigation


@pytest.fixture
def populated_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_db(conn)

    upsert_complaint(conn, {
        "odi_number": 1001,
        "manufacturer": "Toyota", "make": "TOYOTA", "model": "CAMRY",
        "model_year": 2023, "crash": 1, "fire": 0,
        "num_injuries": 1, "num_deaths": 0,
        "date_of_incident": "2024-01-10", "date_complaint_filed": "2024-01-15",
        "components": "BRAKES", "summary": "Brake failure on highway",
        "vin_prefix": "JTD", "quality_score": 0.85,
    })
    upsert_recall(conn, {
        "campaign_number": "23V432000",
        "manufacturer": "Toyota", "make": "TOYOTA", "model": "CAMRY",
        "model_year": 2023, "report_received_date": "2023-06-15",
        "component": "BRAKES", "summary": "Brake fluid leak",
        "consequence": "Crash risk", "remedy": "Replace brake line",
        "notes": "", "num_potentially_affected": 50000,
        "park_it": 0, "park_outside": 0, "quality_score": 0.9,
    })
    upsert_investigation(conn, {
        "investigation_number": "PE25002",
        "nhtsa_id": "102047", "make": "TOYOTA", "model": "CAMRY",
        "model_year_start": 2022, "model_year_end": 2024,
        "investigation_type": "PE", "status": "Open",
        "open_date": "2025-03-21", "close_date": "",
        "subject": "Brake system failures",
        "description": "Investigating brake failures.",
        "num_complaints": 329, "num_vehicles": 1000000,
        "components": "BRAKES", "quality_score": 0.9,
    })
    conn.commit()
    return conn, tmp_path


class TestExportCSV:
    def test_csv_export(self, populated_db, monkeypatch):
        conn, tmp_path = populated_db
        export_dir = tmp_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        import src.export.exporter as exp
        monkeypatch.setattr(exp, "EXPORT_DIR", export_dir)
        exp._export_csv(conn)

        assert (export_dir / "complaints.csv").exists()
        assert (export_dir / "recalls.csv").exists()
        assert (export_dir / "investigations.csv").exists()

        # Verify content
        import csv
        with open(export_dir / "complaints.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["make"] == "TOYOTA"
        assert rows[0]["crash"] == "1"


class TestExportJSON:
    def test_json_export(self, populated_db, monkeypatch):
        conn, tmp_path = populated_db
        export_dir = tmp_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        import json
        import src.export.exporter as exp
        monkeypatch.setattr(exp, "EXPORT_DIR", export_dir)
        exp._export_json(conn)

        path = export_dir / "nhtsa_safety.json"
        assert path.exists()

        with open(path) as f:
            data = json.load(f)

        assert len(data["complaints"]) == 1
        assert len(data["recalls"]) == 1
        assert len(data["investigations"]) == 1
        assert data["complaints"][0]["make"] == "TOYOTA"


class TestExportMarkdown:
    def test_markdown_export(self, populated_db, monkeypatch):
        conn, tmp_path = populated_db
        export_dir = tmp_path / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        import src.export.exporter as exp
        monkeypatch.setattr(exp, "EXPORT_DIR", export_dir)
        exp._export_markdown(conn)

        path = export_dir / "summary.md"
        assert path.exists()

        content = path.read_text()
        assert "NHTSA Vehicle Safety" in content
        assert "Nathan Goldberg" in content
        assert "TOYOTA" in content
