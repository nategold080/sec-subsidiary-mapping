"""Tests for quality scoring."""

import pytest
from src.validation.quality import (
    score_mine, score_accident, score_inspection,
    score_violation, score_assessed_violation, score_penalty,
)


class TestScoreMine:
    def test_complete_record(self):
        rec = {"mine_id": "M1", "mine_name": "Test", "operator_name": "Op",
               "state": "WV", "mine_type": "Surface", "mine_status": "Active",
               "primary_sic": "Coal", "latitude": "38.0", "longitude": "-80.0",
               "no_employees": 50}
        assert score_mine(rec) == 1.0

    def test_empty_record(self):
        assert score_mine({}) == 0.0

    def test_partial(self):
        rec = {"mine_id": "M1", "mine_name": "Test", "operator_name": "Op"}
        score = score_mine(rec)
        assert 0.3 <= score <= 0.5

    def test_none_values(self):
        rec = {"mine_id": "M1", "mine_name": None, "operator_name": ""}
        score = score_mine(rec)
        assert score == 0.15  # Only mine_id contributes


class TestScoreAccident:
    def test_complete(self):
        rec = {"document_no": "D1", "mine_id": "M1", "operator_name": "Op",
               "accident_dt": "01/01/2020", "degree_injury": "Fatality",
               "classification": "Fall", "narrative": "Details here",
               "nature_injury": "Crushing", "inj_body_part": "Head"}
        assert score_accident(rec) == 1.0

    def test_empty(self):
        assert score_accident({}) == 0.0


class TestScoreInspection:
    def test_complete(self):
        rec = {"event_no": "E1", "mine_id": "M1", "operator_name": "Op",
               "inspection_begin_dt": "01/01/2020", "inspection_end_dt": "01/05/2020",
               "activity": "Regular", "coal_metal_ind": "C"}
        assert score_inspection(rec) == 1.0

    def test_empty(self):
        assert score_inspection({}) == 0.0


class TestScoreViolation:
    def test_complete(self):
        rec = {"violation_no": "V1", "mine_id": "M1", "violator_name": "Op",
               "violation_issue_dt": "01/01/2020", "section_of_act": "104(a)",
               "part_section": "56.14132(a)", "sig_sub": "Y", "proposed_penalty": 1000,
               "coal_metal_ind": "M"}
        assert score_violation(rec) == 1.0

    def test_empty(self):
        assert score_violation({}) == 0.0


class TestScoreAssessed:
    def test_complete(self):
        rec = {"violation_no": "V1", "mine_id": "M1", "operator_name": "Op",
               "violation_issue_dt": "01/01/2020", "section_of_act": "104(a)",
               "proposed_penalty_amt": 2000, "sig_sub": "Y", "negligence": "Moderate",
               "gravity": "Significant"}
        assert score_assessed_violation(rec) == 1.0

    def test_empty(self):
        assert score_assessed_violation({}) == 0.0


class TestScorePenalty:
    def test_complete(self):
        rec = {"docket_no": "D1", "mine_id": "M1", "operator_name": "Op",
               "case_status": "Finalized", "proposed_penalty": 5000,
               "amount_paid": 4500, "cal_yr": 2020}
        assert score_penalty(rec) == 1.0

    def test_empty(self):
        assert score_penalty({}) == 0.0
