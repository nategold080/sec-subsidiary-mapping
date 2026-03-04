"""Tests for VPIC vehicle attribute classification and scraper."""

import sqlite3

import pytest

from src.scrapers.vpic import (
    _classify_body,
    _classify_electrification,
    _classify_fuel,
    _infer_drive_type,
    _build_basic_attributes,
)
from src.storage.database import init_db, upsert_vehicle, upsert_vehicle_attributes


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


class TestClassifyBody:
    def test_suv_models(self):
        assert _classify_body("", "RAV4") == "SUV/Crossover"
        assert _classify_body("", "CR-V") == "SUV/Crossover"
        assert _classify_body("", "EXPLORER") == "SUV/Crossover"
        assert _classify_body("", "MODEL Y") == "SUV/Crossover"

    def test_truck_models(self):
        assert _classify_body("", "F-150") == "Truck"
        assert _classify_body("", "SILVERADO") == "Truck"
        assert _classify_body("", "TACOMA") == "Truck"
        assert _classify_body("", "RAM 1500") == "Truck"

    def test_van_models(self):
        assert _classify_body("", "ODYSSEY") == "Van/Minivan"
        assert _classify_body("", "SIENNA") == "Van/Minivan"
        assert _classify_body("", "PACIFICA") == "Van/Minivan"

    def test_vehicle_type_motorcycle(self):
        assert _classify_body("MOTORCYCLE", "SPORTSTER") == "Motorcycle"

    def test_vehicle_type_bus(self):
        assert _classify_body("BUS", "SCHOOLBUS") == "Bus"

    def test_default_sedan(self):
        assert _classify_body("", "CAMRY") == "Sedan/Car"
        assert _classify_body("", "ACCORD") == "Sedan/Car"
        assert _classify_body("", "CIVIC") == "Sedan/Car"

    def test_vehicle_type_suv(self):
        assert _classify_body("MULTIPURPOSE PASSENGER VEHICLE", "UNKNOWN") == "SUV/Crossover"


class TestClassifyFuel:
    def test_ev_makes(self):
        assert _classify_fuel("TESLA", "MODEL 3", 2023) == "Electric"
        assert _classify_fuel("RIVIAN", "R1T", 2023) == "Electric"
        assert _classify_fuel("LUCID", "AIR", 2023) == "Electric"

    def test_ev_models(self):
        assert _classify_fuel("CHEVROLET", "BOLT EV", 2023) == "Electric"
        assert _classify_fuel("NISSAN", "LEAF", 2023) == "Electric"
        assert _classify_fuel("FORD", "MUSTANG MACH-E", 2023) == "Electric"

    def test_hybrid_models(self):
        assert _classify_fuel("TOYOTA", "PRIUS", 2023) == "Hybrid"
        assert _classify_fuel("TOYOTA", "CAMRY HYBRID", 2023) == "Hybrid"
        assert _classify_fuel("HONDA", "ACCORD HYBRID", 2023) == "Hybrid"

    def test_phev_models(self):
        assert _classify_fuel("TOYOTA", "PRIUS PRIME", 2023) == "Plug-in Hybrid"
        assert _classify_fuel("TOYOTA", "RAV4 PRIME", 2023) == "Plug-in Hybrid"

    def test_gasoline_default(self):
        assert _classify_fuel("FORD", "F-150", 2023) == "Gasoline"
        assert _classify_fuel("TOYOTA", "CAMRY", 2023) == "Gasoline"

    def test_diesel(self):
        assert _classify_fuel("RAM", "2500 DIESEL", 2023) == "Diesel"


class TestClassifyElectrification:
    def test_bev(self):
        assert _classify_electrification("TESLA", "MODEL 3", 2023) == "BEV"
        assert _classify_electrification("CHEVROLET", "BOLT EV", 2023) == "BEV"

    def test_phev(self):
        assert _classify_electrification("TOYOTA", "RAV4 PRIME", 2023) == "PHEV"

    def test_hybrid(self):
        assert _classify_electrification("TOYOTA", "PRIUS", 2023) == "Full Hybrid"

    def test_none(self):
        assert _classify_electrification("FORD", "F-150", 2023) == "None"


class TestInferDriveType:
    def test_awd(self):
        assert _infer_drive_type("BMW", "X5 XDRIVE") == "AWD"
        assert _infer_drive_type("AUDI", "Q5 QUATTRO") == "AWD"

    def test_4matic(self):
        assert _infer_drive_type("MERCEDES-BENZ", "E350 4MATIC") == "AWD"

    def test_none_default(self):
        assert _infer_drive_type("TOYOTA", "CAMRY") is None


class TestBuildBasicAttributes:
    def test_returns_complete_dict(self):
        attrs = _build_basic_attributes("TOYOTA", "CAMRY", 2023)
        assert attrs["make"] == "TOYOTA"
        assert attrs["model"] == "CAMRY"
        assert attrs["model_year"] == 2023
        assert attrs["fuel_type"] == "Gasoline"
        assert attrs["body_class"] == "Sedan/Car"
        assert attrs["electrification_level"] == "None"

    def test_ev_attributes(self):
        attrs = _build_basic_attributes("TESLA", "MODEL 3", 2023)
        assert attrs["fuel_type"] == "Electric"
        assert attrs["electrification_level"] == "BEV"

    def test_suv_attributes(self):
        attrs = _build_basic_attributes("TOYOTA", "RAV4", 2023)
        assert attrs["body_class"] == "SUV/Crossover"


class TestUpsertVehicleAttributes:
    def test_insert_with_matching_vehicle(self, db):
        """Vehicle attributes should link to existing vehicle."""
        upsert_vehicle(db, "TOYOTA", "CAMRY", "TOYOTA", "CAMRY")
        db.commit()

        attrs = _build_basic_attributes("TOYOTA", "CAMRY", 2023)
        vid = upsert_vehicle_attributes(db, attrs)
        db.commit()

        assert vid is not None
        row = db.execute(
            "SELECT * FROM vehicle_attributes WHERE vehicle_id = ?", (vid,)
        ).fetchone()
        assert row["body_class"] == "Sedan/Car"
        assert row["fuel_type"] == "Gasoline"

    def test_no_matching_vehicle_returns_none(self, db):
        """No matching vehicle should return None."""
        attrs = _build_basic_attributes("NONEXISTENT", "CAR", 2023)
        vid = upsert_vehicle_attributes(db, attrs)
        assert vid is None

    def test_quality_score_computed(self, db):
        """Quality score should be computed on insert."""
        upsert_vehicle(db, "TESLA", "MODEL 3", "TESLA", "MODEL 3")
        db.commit()

        attrs = _build_basic_attributes("TESLA", "MODEL 3", 2023)
        vid = upsert_vehicle_attributes(db, attrs)
        db.commit()

        row = db.execute(
            "SELECT quality_score FROM vehicle_attributes WHERE vehicle_id = ?", (vid,)
        ).fetchone()
        assert row["quality_score"] > 0
