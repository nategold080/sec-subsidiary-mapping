"""Tests for operator name normalization and safety scoring."""

import pytest
from src.normalization.operators import normalize_operator_name, compute_safety_score, assign_risk_tier


class TestNormalizeOperatorName:
    def test_basic(self):
        assert normalize_operator_name("Acme Mining Corp") == "ACME MINING"

    def test_empty(self):
        assert normalize_operator_name("") == ""

    def test_none(self):
        assert normalize_operator_name(None) == ""

    def test_llc(self):
        assert normalize_operator_name("Big Coal LLC") == "BIG COAL"

    def test_inc(self):
        assert normalize_operator_name("Mountain Industries, Inc.") == "MOUNTAIN INDUSTRIES"

    def test_dba(self):
        assert normalize_operator_name("Smith Mining DBA Smith Coal") == "SMITH MINING"

    def test_fka(self):
        assert normalize_operator_name("NewCo F/K/A OldCo") == "NEWCO"

    def test_parenthetical(self):
        assert normalize_operator_name("Consolidated Coal (WV Division)") == "CONSOLIDATED COAL"

    def test_the_prefix(self):
        assert normalize_operator_name("The Doe Run Company") == "DOE RUN"

    def test_abbreviations(self):
        assert normalize_operator_name("Intl Tech Mfg") == "INTERNATIONAL TECHNOLOGY MANUFACTURING"

    def test_multiple_suffixes(self):
        assert normalize_operator_name("Test Corp Inc LLC") == "TEST"

    def test_punctuation(self):
        assert normalize_operator_name("O'Neal Mining & Gravel, Co.") == "ONEAL MINING GRAVEL"

    def test_whitespace(self):
        assert normalize_operator_name("  Lots  Of   Spaces  ") == "LOTS OF SPACES"

    def test_international_suffix(self):
        assert normalize_operator_name("Heidelberg AG") == "HEIDELBERG"

    def test_gmbh(self):
        assert normalize_operator_name("Knauf Gmbh") == "KNAUF"

    def test_case_insensitive(self):
        assert normalize_operator_name("lower case mining") == "LOWER CASE MINING"

    def test_hyphen_preserved(self):
        assert normalize_operator_name("Arch-Western Resources") == "ARCH-WESTERN RESOURCES"

    def test_constr_expansion(self):
        assert normalize_operator_name("ABC Constr") == "ABC CONSTRUCTION"


class TestComputeSafetyScore:
    def test_perfect_score(self):
        score = compute_safety_score(0, 0, 0, 0, 0, 1)
        assert score == 1.0

    def test_one_fatality(self):
        score = compute_safety_score(1, 0, 0, 0, 0, 1)
        assert score < 1.0
        assert score == round(0.3 * 0.25 + 1.0 * 0.25 + 1.0 * 0.20 + 1.0 * 0.15 + 1.0 * 0.15, 3)

    def test_multiple_fatalities(self):
        score = compute_safety_score(3, 0, 0, 0, 0, 1)
        assert score < 0.8

    def test_worst_case(self):
        score = compute_safety_score(5, 100, 500, 100, 5_000_000, 1)
        assert score == 0.05

    def test_moderate(self):
        score = compute_safety_score(0, 10, 30, 10, 50_000, 1)
        assert 0.3 <= score <= 0.7

    def test_zero_mines_no_crash(self):
        # mine_count=0 should not crash (uses max(mine_count, 1))
        score = compute_safety_score(0, 0, 10, 0, 0, 0)
        assert score > 0


class TestAssignRiskTier:
    def test_low(self):
        assert assign_risk_tier(0.9) == "LOW"

    def test_low_boundary(self):
        assert assign_risk_tier(0.8) == "LOW"

    def test_medium(self):
        assert assign_risk_tier(0.6) == "MEDIUM"

    def test_medium_boundary(self):
        assert assign_risk_tier(0.5) == "MEDIUM"

    def test_high(self):
        assert assign_risk_tier(0.4) == "HIGH"

    def test_high_boundary(self):
        assert assign_risk_tier(0.3) == "HIGH"

    def test_critical(self):
        assert assign_risk_tier(0.1) == "CRITICAL"

    def test_zero(self):
        assert assign_risk_tier(0.0) == "CRITICAL"
