"""Tests for jurisdiction normalization."""

import pytest

from src.normalization.jurisdictions import normalize_jurisdiction, is_tax_haven


class TestNormalizeJurisdiction:
    def test_us_state_abbreviation(self):
        result = normalize_jurisdiction("DE")
        assert result is not None
        assert result.code == "DE"
        assert result.name == "Delaware"
        assert result.country == "US"
        assert result.is_us_state is True
        assert result.is_tax_haven is False

    def test_us_state_full_name(self):
        result = normalize_jurisdiction("California")
        assert result is not None
        assert result.code == "CA"
        assert result.name == "California"
        assert result.is_us_state is True

    def test_us_state_with_suffix(self):
        result = normalize_jurisdiction("Delaware, U.S.")
        assert result is not None
        assert result.code == "DE"
        assert result.is_us_state is True

    def test_us_state_with_usa(self):
        result = normalize_jurisdiction("Nevada, USA")
        assert result is not None
        assert result.code == "NV"

    def test_country_name(self):
        result = normalize_jurisdiction("Hong Kong")
        assert result is not None
        assert result.code == "HK"
        assert result.is_us_state is False

    def test_country_uk(self):
        result = normalize_jurisdiction("United Kingdom")
        assert result is not None
        assert result.code == "GB"

    def test_tax_haven_cayman(self):
        result = normalize_jurisdiction("Cayman Islands")
        assert result is not None
        assert result.code == "KY"
        assert result.is_tax_haven is True

    def test_tax_haven_bermuda(self):
        result = normalize_jurisdiction("Bermuda")
        assert result is not None
        assert result.code == "BM"
        assert result.is_tax_haven is True

    def test_tax_haven_bvi(self):
        result = normalize_jurisdiction("British Virgin Islands")
        assert result is not None
        assert result.code == "VG"
        assert result.is_tax_haven is True

    def test_tax_haven_luxembourg(self):
        result = normalize_jurisdiction("Luxembourg")
        assert result is not None
        assert result.code == "LU"
        assert result.is_tax_haven is True

    def test_ireland(self):
        result = normalize_jurisdiction("Ireland")
        assert result is not None
        assert result.code == "IE"
        assert result.is_tax_haven is True  # Classified as tax haven

    def test_canada(self):
        result = normalize_jurisdiction("Canada")
        assert result is not None
        assert result.code == "CA"
        assert result.is_tax_haven is False

    def test_japan(self):
        result = normalize_jurisdiction("Japan")
        assert result is not None
        assert result.code == "JP"
        assert result.is_tax_haven is False

    def test_empty_string(self):
        assert normalize_jurisdiction("") is None

    def test_none(self):
        assert normalize_jurisdiction(None) is None

    def test_new_york(self):
        result = normalize_jurisdiction("New York")
        assert result is not None
        assert result.code == "NY"
        assert result.is_us_state is True

    def test_district_of_columbia(self):
        result = normalize_jurisdiction("District of Columbia")
        assert result is not None
        assert result.code == "DC"

    def test_switzerland(self):
        result = normalize_jurisdiction("Switzerland")
        assert result is not None
        assert result.code == "CH"
        assert result.is_tax_haven is True

    def test_netherlands(self):
        result = normalize_jurisdiction("Netherlands")
        assert result is not None
        assert result.code == "NL"

    def test_singapore(self):
        result = normalize_jurisdiction("Singapore")
        assert result is not None
        assert result.code == "SG"
        assert result.is_tax_haven is True

    def test_footnote_stripped(self):
        result = normalize_jurisdiction("Delaware (1)")
        assert result is not None
        assert result.code == "DE"


class TestIsTaxHaven:
    def test_cayman(self):
        assert is_tax_haven("KY") is True

    def test_bermuda(self):
        assert is_tax_haven("BM") is True

    def test_us(self):
        assert is_tax_haven("US") is False

    def test_germany(self):
        assert is_tax_haven("DE") is False
