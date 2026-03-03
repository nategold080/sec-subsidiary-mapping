"""Tests for quality scoring."""

import pytest

from src.validation.quality import score_subsidiary, score_filing, WEIGHTS


class TestScoreSubsidiary:
    def test_full_record(self):
        record = {
            "subsidiary_name": "Alpha Corp",
            "jurisdiction_raw": "Delaware",
            "jurisdiction_code": "DE",
            "parent_cik": "0000320193",
            "filing_date": "2024-01-15",
            "ownership_pct": 100.0,
            "parent_revenue": 383285000000,
            "source_url": "https://sec.gov/...",
        }
        qs = score_subsidiary(record)
        assert qs.score == 1.0
        assert qs.above_threshold is True

    def test_minimal_record(self):
        record = {
            "subsidiary_name": "Alpha Corp",
            "jurisdiction_raw": "Delaware",
            "parent_cik": "0000320193",
        }
        qs = score_subsidiary(record)
        assert qs.score > 0.40
        assert qs.above_threshold is True

    def test_empty_record(self):
        record = {}
        qs = score_subsidiary(record)
        assert qs.score == 0.0
        assert qs.above_threshold is False

    def test_components_add_up(self):
        record = {
            "subsidiary_name": "Alpha Corp",
            "jurisdiction_raw": "Delaware",
            "jurisdiction_code": "DE",
            "parent_cik": "123",
            "filing_date": "2024-01-01",
            "source_url": "https://example.com",
        }
        qs = score_subsidiary(record)
        component_sum = sum(qs.components.values())
        assert abs(qs.score - component_sum) < 0.001

    def test_weights_sum_to_one(self):
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestScoreFiling:
    def test_full_filing(self):
        record = {
            "accession": "0000320193-24-000123",
            "cik": "0000320193",
            "company_name": "Apple Inc.",
            "file_date": "2024-11-01",
            "subsidiary_count": 25,
            "exhibit_url": "https://sec.gov/...",
        }
        qs = score_filing(record)
        assert qs.score == 1.0

    def test_empty_filing(self):
        qs = score_filing({})
        assert qs.score == 0.0
