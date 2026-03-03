"""Tests for EDGAR search and filing discovery (no network calls)."""

import pytest

from src.scrapers.edgar_search import _parse_efts_hit
from src.cli import _normalize_name


class TestParseEFTSHit:
    def test_standard_hit(self):
        hit = {
            "_id": "0000320193-24-000123:a10-kexhibit21.htm",
            "_source": {
                "ciks": ["0000320193"],
                "display_names": ["Apple Inc.  (AAPL)  (CIK 0000320193)"],
                "file_date": "2024-11-01",
                "root_forms": ["10-K"],
            },
        }
        result = _parse_efts_hit(hit)
        assert result is not None
        assert result["accession"] == "0000320193-24-000123"
        assert result["filename"] == "a10-kexhibit21.htm"
        assert result["cik"] == "0000320193"
        assert result["company_name"] == "Apple Inc."
        assert result["ticker"] == "AAPL"
        assert result["file_date"] == "2024-11-01"
        assert "320193" in result["exhibit_url"]

    def test_multi_ticker(self):
        hit = {
            "_id": "0001067983-24-000001:brka-ex21.htm",
            "_source": {
                "ciks": ["0001067983"],
                "display_names": ["BERKSHIRE HATHAWAY INC  (BRK-A, BRK-B)  (CIK 0001067983)"],
                "file_date": "2024-02-26",
            },
        }
        result = _parse_efts_hit(hit)
        assert result["company_name"] == "BERKSHIRE HATHAWAY INC"
        assert result["ticker"] == "BRK-A"

    def test_no_ticker(self):
        hit = {
            "_id": "0001381531-24-000001:ex21.htm",
            "_source": {
                "ciks": ["0001381531"],
                "display_names": ["Domtar CORP  (CIK 0001381531)"],
                "file_date": "2024-03-01",
            },
        }
        result = _parse_efts_hit(hit)
        assert result["company_name"] == "Domtar CORP"
        assert result["ticker"] == ""

    def test_empty_display(self):
        hit = {
            "_id": "0000000001-24-000001:ex21.htm",
            "_source": {
                "ciks": ["0000000001"],
                "display_names": [],
                "file_date": "2024-01-01",
            },
        }
        result = _parse_efts_hit(hit)
        assert result["company_name"] == ""

    def test_multi_cik(self):
        hit = {
            "_id": "0001770450-24-000012:xrx-ex21.htm",
            "_source": {
                "ciks": ["0001770450", "0000108772"],
                "display_names": [
                    "Xerox Holdings Corp  (XRX)  (CIK 0001770450)",
                    "XEROX CORP  (CIK 0000108772)",
                ],
                "file_date": "2024-02-23",
            },
        }
        result = _parse_efts_hit(hit)
        assert result["cik"] == "0001770450"  # First CIK


class TestNormalizeName:
    def test_strip_inc(self):
        assert _normalize_name("Alpha Holdings, Inc.") == "ALPHA HOLDINGS"

    def test_strip_llc(self):
        assert _normalize_name("Beta Holdings, LLC") == "BETA HOLDINGS"

    def test_strip_ltd(self):
        assert _normalize_name("Gamma Services Ltd.") == "GAMMA SERVICES"

    def test_strip_corporation(self):
        assert _normalize_name("Delta Corporation") == "DELTA"

    def test_strip_company(self):
        assert _normalize_name("Epsilon Company") == "EPSILON"

    def test_ampersand(self):
        assert _normalize_name("Alpha & Beta Inc.") == "ALPHA AND BETA"

    def test_gmbh(self):
        assert _normalize_name("Deutsche Tech GmbH") == "DEUTSCHE TECH"

    def test_bv(self):
        assert _normalize_name("Dutch Holding B.V.") == "DUTCH HOLDING"

    def test_sa(self):
        assert _normalize_name("French Company S.A.") == "FRENCH COMPANY"

    def test_plc(self):
        assert _normalize_name("British Holdings PLC") == "BRITISH HOLDINGS"

    def test_kk(self):
        assert _normalize_name("Japan Corp K.K.") == "JAPAN CORP"

    def test_preserves_core_name(self):
        assert _normalize_name("Apple") == "APPLE"

    def test_collapse_spaces(self):
        assert _normalize_name("  Alpha   Beta  ") == "ALPHA BETA"
