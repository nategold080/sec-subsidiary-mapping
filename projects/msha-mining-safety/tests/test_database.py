"""Tests for database module."""

import sqlite3
import pytest
from src.storage.database import init_db, get_connection, get_stats, upsert_mines_batch, insert_accidents_batch, insert_inspections_batch, insert_violations_batch, insert_assessed_batch, insert_penalties_batch, upsert_profiles_batch


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn=conn)
    return conn


class TestInitDb:
    def test_creates_tables(self, db):
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "mines" in tables
        assert "accidents" in tables
        assert "inspections" in tables
        assert "violations" in tables
        assert "assessed_violations" in tables
        assert "penalties" in tables
        assert "operator_profiles" in tables

    def test_idempotent(self, db):
        init_db(conn=db)  # Should not raise


class TestUpsertMines:
    def test_insert(self, db):
        records = [{"mine_id": "0100001", "mine_name": "Test Mine", "coal_metal_ind": "C",
                     "mine_type": "Underground", "mine_status": "Active", "status_date": "01/01/2020",
                     "controller_id": "C001", "controller_name": "Test Corp", "operator_id": "O001",
                     "operator_name": "Test Op", "state": "WV", "fips_cnty_cd": "001",
                     "fips_cnty_nm": "Test County", "company_type": "Corporation", "district": "D1",
                     "primary_sic": "Coal", "primary_sic_cd": "1220", "secondary_sic": "",
                     "latitude": "38.0", "longitude": "-80.0", "no_employees": 50,
                     "days_per_week": 5, "hours_per_shift": 8, "nearest_town": "Testville",
                     "quality_score": 0.95}]
        n = upsert_mines_batch(records, conn=db)
        assert n == 1
        row = db.execute("SELECT * FROM mines WHERE mine_id = '0100001'").fetchone()
        assert row["mine_name"] == "Test Mine"

    def test_upsert_updates(self, db):
        rec = {"mine_id": "0100001", "mine_name": "Old", "coal_metal_ind": "C",
               "mine_type": "Surface", "mine_status": "Active", "status_date": "",
               "controller_id": "", "controller_name": "", "operator_id": "O1",
               "operator_name": "Op", "state": "PA", "fips_cnty_cd": "", "fips_cnty_nm": "",
               "company_type": "", "district": "", "primary_sic": "", "primary_sic_cd": "",
               "secondary_sic": "", "latitude": "", "longitude": "", "no_employees": None,
               "days_per_week": None, "hours_per_shift": None, "nearest_town": "",
               "quality_score": 0.5}
        upsert_mines_batch([rec], conn=db)
        rec["mine_name"] = "New"
        upsert_mines_batch([rec], conn=db)
        row = db.execute("SELECT mine_name FROM mines WHERE mine_id = '0100001'").fetchone()
        assert row[0] == "New"


class TestInsertAccidents:
    def test_insert(self, db):
        rec = {"document_no": "DOC001", "mine_id": "0100001", "controller_id": "", "controller_name": "",
               "operator_id": "O1", "operator_name": "Op", "contractor_id": "", "subunit": "Underground",
               "accident_dt": "01/15/2020", "cal_yr": 2020, "degree_injury_cd": "01",
               "degree_injury": "Fatality", "fips_state_cd": "54", "ug_location": "",
               "mining_equip": "", "equip_mfr_name": "", "classification": "Fall of roof",
               "accident_type": "Fall of person", "no_injuries": 1, "tot_exper": 10.5,
               "mine_exper": 5.0, "job_exper": 3.0, "occupation": "Miner",
               "activity": "Mining", "injury_source": "Rock", "nature_injury": "Crushing",
               "inj_body_part": "Head", "schedule_charge": 6000, "days_restrict": 0,
               "days_lost": 0, "immed_notify": "Death", "narrative": "Test narrative",
               "coal_metal_ind": "C", "quality_score": 0.9}
        n = insert_accidents_batch([rec], conn=db)
        assert n == 1

    def test_ignore_duplicate(self, db):
        rec = {"document_no": "DOC001", "mine_id": "M1", "controller_id": "", "controller_name": "",
               "operator_id": "", "operator_name": "", "contractor_id": "", "subunit": "",
               "accident_dt": "", "cal_yr": None, "degree_injury_cd": "", "degree_injury": "",
               "fips_state_cd": "", "ug_location": "", "mining_equip": "", "equip_mfr_name": "",
               "classification": "", "accident_type": "", "no_injuries": None, "tot_exper": None,
               "mine_exper": None, "job_exper": None, "occupation": "", "activity": "",
               "injury_source": "", "nature_injury": "", "inj_body_part": "", "schedule_charge": None,
               "days_restrict": None, "days_lost": None, "immed_notify": "", "narrative": "",
               "coal_metal_ind": "", "quality_score": 0.1}
        insert_accidents_batch([rec], conn=db)
        insert_accidents_batch([rec], conn=db)  # Should not raise
        count = db.execute("SELECT COUNT(*) FROM accidents").fetchone()[0]
        assert count == 1


class TestInsertInspections:
    def test_insert(self, db):
        rec = {"event_no": "EV001", "mine_id": "M1", "inspection_begin_dt": "01/01/2020",
               "inspection_end_dt": "01/05/2020", "controller_id": "C1", "controller_name": "Test",
               "operator_id": "O1", "operator_name": "Op", "cal_yr": 2020,
               "activity_code": "A01", "activity": "Regular Inspection", "coal_metal_ind": "C",
               "quality_score": 0.85}
        n = insert_inspections_batch([rec], conn=db)
        assert n == 1


class TestInsertViolations:
    def test_insert(self, db):
        rec = {"event_no": "EV001", "violation_no": "V001", "mine_id": "M1",
               "controller_id": "C1", "controller_name": "Test", "violator_id": "O1",
               "violator_name": "Op", "violator_type": "Operator", "mine_name": "Test Mine",
               "mine_type": "Surface", "coal_metal_ind": "M", "violation_issue_dt": "01/01/2020",
               "cal_yr": 2020, "sig_sub": "Y", "section_of_act": "104(a)",
               "section_of_act_desc": "Citation", "part_section": "56.14132(a)",
               "part_section_desc": "Guards", "proposed_penalty": 1500.0,
               "amount_paid": 1200.0, "quality_score": 0.9}
        n = insert_violations_batch([rec], conn=db)
        assert n == 1


class TestInsertAssessed:
    def test_insert(self, db):
        rec = {"violation_no": "V001", "assessed_id": "A001", "mine_id": "M1",
               "controller_id": "C1", "controller_name": "Test", "operator_id": "O1",
               "operator_name": "Op", "cal_yr": 2020, "violation_issue_dt": "01/01/2020",
               "section_of_act": "104(a)", "part_section": "56.14132(a)",
               "proposed_penalty_amt": 2000.0, "paid_proposed_penalty_amt": 1800.0,
               "penalty_points": 45, "sig_sub": "Y", "likely": "Reasonably Likely",
               "injury_illness": "Lost Workdays", "negligence": "Moderate",
               "gravity": "Significant", "quality_score": 0.88}
        n = insert_assessed_batch([rec], conn=db)
        assert n == 1


class TestInsertPenalties:
    def test_insert(self, db):
        rec = {"docket_no": "WEST-2020-001", "mine_id": "M1", "controller_id": "C1",
               "controller_name": "Test", "operator_id": "O1", "operator_name": "Op",
               "case_status": "Finalized", "proposed_penalty": 5000.0,
               "amount_assessed": 4500.0, "amount_paid": 4500.0, "cal_yr": 2020,
               "quality_score": 0.9}
        n = insert_penalties_batch([rec], conn=db)
        assert n == 1


class TestGetStats:
    def test_empty_db(self, db):
        stats = get_stats(conn=db)
        assert stats["mines"] == 0
        assert stats["accidents"] == 0
        assert stats["total_fatalities"] == 0

    def test_with_data(self, db):
        rec = {"mine_id": "M1", "mine_name": "Test", "coal_metal_ind": "C",
               "mine_type": "Surface", "mine_status": "Active", "status_date": "",
               "controller_id": "", "controller_name": "", "operator_id": "O1",
               "operator_name": "Op", "state": "WV", "fips_cnty_cd": "", "fips_cnty_nm": "",
               "company_type": "", "district": "", "primary_sic": "", "primary_sic_cd": "",
               "secondary_sic": "", "latitude": "", "longitude": "", "no_employees": 10,
               "days_per_week": 5, "hours_per_shift": 8, "nearest_town": "",
               "quality_score": 0.8}
        upsert_mines_batch([rec], conn=db)
        stats = get_stats(conn=db)
        assert stats["mines"] == 1
        assert stats["active_mines"] == 1
        assert stats["states_covered"] == 1
