"""Integration tests for the pipeline."""

import sqlite3
import pytest

from src.storage.database import (
    init_db, get_connection, get_stats,
    upsert_complaint, upsert_recall, upsert_investigation, upsert_vehicle,
    insert_cross_link,
)
from src.normalization.vehicles import normalize_make, normalize_model, normalize_component
from src.normalization.cross_linker import cross_link_all
from src.validation.quality import score_complaint, score_recall, score_investigation


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def _make_complaint(odi, make="FORD", model="F-150", year=2020, **kw):
    defaults = {
        "odi_number": odi,
        "manufacturer": make,
        "make": make, "model": model, "model_year": year,
        "crash": 0, "fire": 0, "num_injuries": 0, "num_deaths": 0,
        "date_of_incident": "2024-01-10",
        "date_complaint_filed": "2024-01-15",
        "components": "ENGINE",
        "summary": "Test complaint description",
        "vin_prefix": "1FT",
        "quality_score": 0.8,
    }
    defaults.update(kw)
    return defaults


def _make_recall(campaign, make="FORD", model="F-150", year=2020, **kw):
    defaults = {
        "campaign_number": campaign,
        "manufacturer": make, "make": make, "model": model,
        "model_year": year,
        "report_received_date": "2024-06-15",
        "component": "ENGINE", "summary": "Recall summary",
        "consequence": "Crash risk", "remedy": "Replace part",
        "notes": "", "num_potentially_affected": 10000,
        "park_it": 0, "park_outside": 0, "quality_score": 0.9,
    }
    defaults.update(kw)
    return defaults


def _make_investigation(inv_num, make="FORD", model="F-150", year=2020, **kw):
    defaults = {
        "investigation_number": inv_num,
        "nhtsa_id": "100001", "make": make, "model": model,
        "model_year_start": year, "model_year_end": year + 1,
        "investigation_type": "PE", "status": "Open",
        "open_date": "2024-06-01", "close_date": "",
        "subject": "Engine stall investigation",
        "description": "Investigating engine stalls.",
        "num_complaints": 100, "num_vehicles": 50000,
        "components": "ENGINE", "quality_score": 0.85,
    }
    defaults.update(kw)
    return defaults


class TestFullPipeline:
    """Integration test simulating a mini pipeline run."""

    def test_pipeline_produces_cross_links(self, db):
        """Load complaints, recalls, investigations and verify cross-linking."""
        # Load 5 Ford F-150 complaints
        for i in range(5):
            upsert_complaint(db, _make_complaint(1000 + i))

        # Load 2 Toyota Camry complaints
        for i in range(2):
            upsert_complaint(db, _make_complaint(
                2000 + i, make="TOYOTA", model="CAMRY", year=2022,
                components="BRAKES",
            ))

        # Load 1 Ford F-150 recall
        upsert_recall(db, _make_recall("24V001000"))

        # Load 1 Toyota Camry recall
        upsert_recall(db, _make_recall(
            "24V002000", make="TOYOTA", model="CAMRY", year=2022,
            component="BRAKES:HYDRAULIC",
        ))

        # Load 1 Ford investigation
        upsert_investigation(db, _make_investigation("PE24001"))

        db.commit()

        # Run cross-linking
        results = cross_link_all(db)

        # Should have complaint→recall and complaint→investigation links
        assert results["complaint_to_recall"] > 0
        assert results["complaint_to_investigation"] > 0

        # Verify stats
        stats = get_stats(db)
        assert stats["complaint_count"] == 7
        assert stats["recall_count"] == 2
        assert stats["investigation_count"] == 1
        assert stats["cross_link_count"] > 0

    def test_no_false_cross_links(self, db):
        """Ensure unrelated records don't get linked."""
        # Honda Civic complaint
        upsert_complaint(db, _make_complaint(
            3001, make="HONDA", model="CIVIC", year=2021,
            components="ELECTRICAL SYSTEM",
        ))

        # Ford F-150 recall
        upsert_recall(db, _make_recall("24V003000"))

        db.commit()
        results = cross_link_all(db)

        assert results["complaint_to_recall"] == 0


class TestQualityScoring:
    def test_complaint_scoring_components(self):
        rec = _make_complaint(9001)
        qs = score_complaint(rec)
        assert qs.score > 0.5
        assert "has_make_model" in qs.components
        assert qs.components["has_make_model"] == 1.0

    def test_recall_scoring_components(self):
        rec = _make_recall("24V009000")
        qs = score_recall(rec)
        assert qs.score > 0.5
        assert qs.components["has_campaign_number"] == 1.0

    def test_investigation_scoring_components(self):
        rec = _make_investigation("PE24009")
        qs = score_investigation(rec)
        assert qs.score > 0.5
        assert qs.components["has_investigation_number"] == 1.0


class TestNormalizationPipeline:
    def test_make_alias_chain(self):
        """Verify full normalization chain for various inputs."""
        assert normalize_make("chevy") == "CHEVROLET"
        assert normalize_make("FORD MOTOR COMPANY") == "FORD"
        assert normalize_make("Tesla, Inc.") == "TESLA"
        assert normalize_make("BAYERISCHE MOTOREN WERKE") == "BMW"
        assert normalize_make("FCA US LLC") == "CHRYSLER"

    def test_model_normalization(self):
        assert normalize_model("F-150") == "F-150"
        assert normalize_model("camry") == "CAMRY"
        assert normalize_model("Civic (2020-2023)") == "CIVIC"

    def test_component_passthrough(self):
        assert normalize_component("BRAKES") == "BRAKES"
        assert normalize_component("  engine  ") == "ENGINE"


class TestDatabaseConstraints:
    def test_unique_cross_link(self, db):
        """Duplicate cross-links should be ignored."""
        link = {
            "source_type": "complaint", "source_id": "1001",
            "target_type": "recall", "target_id": "24V001000",
            "link_method": "make_model_year_component",
            "confidence": 0.9,
        }
        insert_cross_link(db, link)
        db.commit()

        # Second insert should return None (ignored)
        result = insert_cross_link(db, link)
        assert result is None

    def test_upsert_complaint_updates(self, db):
        """Upsert should update fields on conflict."""
        rec = _make_complaint(5001, summary="Original")
        upsert_complaint(db, rec)
        db.commit()

        rec["summary"] = "Updated"
        upsert_complaint(db, rec)
        db.commit()

        row = db.execute("SELECT summary FROM complaints WHERE odi_number = 5001").fetchone()
        assert row["summary"] == "Updated"

    def test_upsert_recall_updates(self, db):
        rec = _make_recall("24V005000", summary="Original")
        upsert_recall(db, rec)
        db.commit()

        rec["summary"] = "Updated"
        upsert_recall(db, rec)
        db.commit()

        row = db.execute("SELECT summary FROM recalls WHERE campaign_number = '24V005000'").fetchone()
        assert row["summary"] == "Updated"

    def test_vehicle_dedup(self, db):
        """Same normalized make/model should not create duplicate vehicles."""
        upsert_vehicle(db, "FORD", "F-150", "FORD", "F-150")
        upsert_vehicle(db, "Ford", "f-150", "FORD", "F-150")
        db.commit()

        count = db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
        assert count == 1
