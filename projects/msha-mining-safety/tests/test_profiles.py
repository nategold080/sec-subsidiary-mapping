"""Tests for operator profile building (bulk SQL version)."""

import sqlite3
import pytest
from src.storage.database import init_db, upsert_mines_batch, insert_accidents_batch, insert_violations_batch
from src.normalization.operators import build_operator_profiles


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn=conn)
    return conn


def _mine(mine_id, operator_id, operator_name, state="WV", status="Active"):
    return {
        "mine_id": mine_id, "mine_name": f"Mine {mine_id}", "coal_metal_ind": "C",
        "mine_type": "Surface", "mine_status": status, "status_date": "",
        "controller_id": "", "controller_name": "", "operator_id": operator_id,
        "operator_name": operator_name, "state": state, "fips_cnty_cd": "",
        "fips_cnty_nm": "", "company_type": "", "district": "", "primary_sic": "Coal",
        "primary_sic_cd": "", "secondary_sic": "", "latitude": "", "longitude": "",
        "no_employees": 10, "days_per_week": 5, "hours_per_shift": 8,
        "nearest_town": "", "quality_score": 0.8,
    }


def _accident(doc_no, mine_id, operator_id, degree_cd="03"):
    return {
        "document_no": doc_no, "mine_id": mine_id, "controller_id": "",
        "controller_name": "", "operator_id": operator_id, "operator_name": "Op",
        "contractor_id": "", "subunit": "", "accident_dt": "01/01/2020",
        "cal_yr": 2020, "degree_injury_cd": degree_cd, "degree_injury": "Test",
        "fips_state_cd": "", "ug_location": "", "mining_equip": "",
        "equip_mfr_name": "", "classification": "", "accident_type": "",
        "no_injuries": 1, "tot_exper": 5.0, "mine_exper": 2.0, "job_exper": 1.0,
        "occupation": "", "activity": "", "injury_source": "", "nature_injury": "",
        "inj_body_part": "", "schedule_charge": 0, "days_restrict": 0,
        "days_lost": 10, "immed_notify": "", "narrative": "", "coal_metal_ind": "C",
        "quality_score": 0.7,
    }


class TestBuildProfiles:
    def test_single_operator(self, db):
        upsert_mines_batch([_mine("M1", "O1", "Test Op")], conn=db)
        profiles = build_operator_profiles(db)
        assert len(profiles) == 1
        assert profiles[0]["operator_id"] == "O1"
        assert profiles[0]["mine_count"] == 1
        assert profiles[0]["active_mine_count"] == 1

    def test_multiple_operators(self, db):
        upsert_mines_batch([
            _mine("M1", "O1", "Op One"),
            _mine("M2", "O2", "Op Two"),
            _mine("M3", "O1", "Op One"),
        ], conn=db)
        profiles = build_operator_profiles(db)
        assert len(profiles) == 2
        p1 = next(p for p in profiles if p["operator_id"] == "O1")
        assert p1["mine_count"] == 2

    def test_accident_aggregation(self, db):
        upsert_mines_batch([_mine("M1", "O1", "Op")], conn=db)
        insert_accidents_batch([
            _accident("D1", "M1", "O1", "01"),  # fatality
            _accident("D2", "M1", "O1", "03"),  # other injury
        ], conn=db)
        profiles = build_operator_profiles(db)
        p = profiles[0]
        assert p["total_accidents"] == 2
        assert p["total_fatalities"] == 1
        assert p["total_injuries"] == 2  # 01 and 03 both in injury codes
        assert p["days_lost"] == 20  # 10 + 10

    def test_safety_score_present(self, db):
        upsert_mines_batch([_mine("M1", "O1", "Op")], conn=db)
        profiles = build_operator_profiles(db)
        assert profiles[0]["safety_score"] == 1.0  # perfect — no accidents/violations
        assert profiles[0]["risk_tier"] == "LOW"

    def test_states_populated(self, db):
        upsert_mines_batch([
            _mine("M1", "O1", "Op", state="WV"),
            _mine("M2", "O1", "Op", state="KY"),
        ], conn=db)
        profiles = build_operator_profiles(db)
        states = profiles[0]["states"]
        assert "KY" in states
        assert "WV" in states

    def test_inactive_mine_count(self, db):
        upsert_mines_batch([
            _mine("M1", "O1", "Op", status="Active"),
            _mine("M2", "O1", "Op", status="Abandoned"),
        ], conn=db)
        profiles = build_operator_profiles(db)
        assert profiles[0]["mine_count"] == 2
        assert profiles[0]["active_mine_count"] == 1

    def test_normalized_name(self, db):
        upsert_mines_batch([_mine("M1", "O1", "Acme Mining Corp LLC")], conn=db)
        profiles = build_operator_profiles(db)
        assert profiles[0]["normalized_name"] == "ACME MINING"

    def test_empty_db(self, db):
        profiles = build_operator_profiles(db)
        assert len(profiles) == 0
