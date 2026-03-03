"""Tests for employer name normalization."""

import pytest
from src.normalization.employers import normalize_employer, extract_dba_name, normalize_state


class TestNormalizeEmployer:
    def test_basic(self):
        assert normalize_employer("WALMART INC") == "WALMART"

    def test_llc(self):
        assert normalize_employer("ACME SERVICES LLC") == "ACME SERVICES"

    def test_corporation(self):
        assert normalize_employer("ABC CORPORATION") == "ABC"

    def test_dba(self):
        assert normalize_employer("SMITH ENTERPRISES DBA SMITHS DINER") == "SMITH ENTERPRISES"

    def test_d_b_a(self):
        assert normalize_employer("JONES CO D/B/A JONES CAFE") == "JONES"

    def test_the_prefix(self):
        assert normalize_employer("THE HOME DEPOT") == "HOME DEPOT"

    def test_possessive(self):
        assert normalize_employer("MCDONALD'S") == "MCDONALDS"

    def test_punctuation(self):
        assert normalize_employer("B.J.'S WHOLESALE CLUB, INC.") == "BJS WHOLESALE CLUB"

    def test_ampersand(self):
        assert normalize_employer("JOHNSON & JOHNSON") == "JOHNSON AND JOHNSON"

    def test_abbreviations(self):
        assert normalize_employer("INTL MGMT SVCS") == "INTERNATIONAL MANAGEMENT SERVICES"

    def test_multiple_suffixes(self):
        assert normalize_employer("GLOBAL TECH, INC., LLC") == "GLOBAL TECHNOLOGY"

    def test_empty(self):
        assert normalize_employer("") == ""

    def test_none(self):
        assert normalize_employer(None) == ""

    def test_whitespace(self):
        assert normalize_employer("  ACME   CORP  ") == "ACME"

    def test_case_insensitive(self):
        assert normalize_employer("Walmart Inc") == "WALMART"


class TestExtractDbaName:
    def test_dba(self):
        assert extract_dba_name("SMITH ENTERPRISES DBA SMITHS DINER") == "SMITHS DINER"

    def test_d_b_a(self):
        assert extract_dba_name("JONES CO D/B/A JONES CAFE") == "JONES CAFE"

    def test_no_dba(self):
        assert extract_dba_name("WALMART INC") is None

    def test_empty(self):
        assert extract_dba_name("") is None


class TestNormalizeState:
    def test_code(self):
        assert normalize_state("CA") == "CA"

    def test_full_name(self):
        assert normalize_state("California") == "CA"

    def test_empty(self):
        assert normalize_state("") == ""

    def test_whitespace(self):
        assert normalize_state("  ny  ") == "NY"
