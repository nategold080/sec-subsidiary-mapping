"""Tests for Exhibit 21 HTML parser."""

import pytest

from src.extractors.exhibit21_parser import (
    parse_exhibit21,
    _clean_text,
    _should_skip_row,
    _looks_like_jurisdiction,
    _parse_percentage,
    _strip_sgml_wrapper,
    _extract_from_tables,
    _extract_from_pre,
    _extract_from_text,
)


class TestCleanText:
    def test_strips_whitespace(self):
        assert _clean_text("  hello  ") == "hello"

    def test_collapses_spaces(self):
        assert _clean_text("hello   world") == "hello world"

    def test_strips_nbsp(self):
        assert _clean_text("hello\xa0world") == "hello world"

    def test_strips_footnote_numbers(self):
        assert _clean_text("Company Name (1)") == "Company Name"
        assert _clean_text("Company Name (2)") == "Company Name"

    def test_strips_footnote_letters(self):
        assert _clean_text("Company Name (a)") == "Company Name"


class TestShouldSkipRow:
    def test_empty_name(self):
        assert _should_skip_row("", "Delaware")

    def test_short_name(self):
        assert _should_skip_row("AB", "Delaware")

    def test_exhibit_header(self):
        assert _should_skip_row("Exhibit 21", "")

    def test_subsidiaries_of(self):
        assert _should_skip_row("Subsidiaries of Apple Inc.", "")

    def test_footnote(self):
        assert _should_skip_row("* See note below", "")

    def test_valid_name(self):
        assert not _should_skip_row("Apple Asia Limited", "Hong Kong")

    def test_pursuant(self):
        assert _should_skip_row("Pursuant to Item 601", "")


class TestLooksLikeJurisdiction:
    def test_us_state_full(self):
        assert _looks_like_jurisdiction("Delaware")
        assert _looks_like_jurisdiction("California")
        assert _looks_like_jurisdiction("New York")

    def test_us_state_abbreviation(self):
        assert _looks_like_jurisdiction("DE")
        assert _looks_like_jurisdiction("CA")
        assert _looks_like_jurisdiction("NY")

    def test_country(self):
        assert _looks_like_jurisdiction("Hong Kong")
        assert _looks_like_jurisdiction("United Kingdom")
        assert _looks_like_jurisdiction("Cayman Islands")
        assert _looks_like_jurisdiction("Ireland")

    def test_with_us_suffix(self):
        assert _looks_like_jurisdiction("Delaware, U.S.")
        assert _looks_like_jurisdiction("Nevada, USA")

    def test_empty(self):
        assert not _looks_like_jurisdiction("")
        assert not _looks_like_jurisdiction(" ")

    def test_random_text(self):
        assert not _looks_like_jurisdiction("Some Random Text")


class TestParsePercentage:
    def test_valid(self):
        assert _parse_percentage("100") == 100.0
        assert _parse_percentage("50.5") == 50.5
        assert _parse_percentage("100%") == 100.0

    def test_invalid(self):
        assert _parse_percentage("") is None
        assert _parse_percentage("abc") is None
        assert _parse_percentage("200") is None


class TestStripSGMLWrapper:
    def test_strips_wrapper(self):
        html = "<DOCUMENT>\n<TYPE>EX-21\n<TEXT>\n<html>content</html>\n</TEXT>\n</DOCUMENT>"
        result = _strip_sgml_wrapper(html)
        assert "<html>content</html>" in result
        assert "<DOCUMENT>" not in result

    def test_no_wrapper(self):
        html = "<html>content</html>"
        result = _strip_sgml_wrapper(html)
        assert "content" in result


class TestTableExtraction:
    def test_simple_table(self):
        html = """
        <html><body>
        <table>
            <tr><td><b>Name of Subsidiary</b></td><td><b>Jurisdiction of Incorporation</b></td></tr>
            <tr><td>Alpha Corp</td><td>Delaware</td></tr>
            <tr><td>Beta LLC</td><td>California</td></tr>
        </table>
        </body></html>
        """
        subs = _extract_from_tables(html)
        assert len(subs) == 2
        assert subs[0].name == "Alpha Corp"
        assert subs[0].jurisdiction_raw == "Delaware"
        assert subs[1].name == "Beta LLC"
        assert subs[1].jurisdiction_raw == "California"

    def test_table_with_ownership(self):
        html = """
        <html><body>
        <table>
            <tr><td>Name of Subsidiary</td><td>Jurisdiction</td><td>% Owned</td></tr>
            <tr><td>Alpha Corp</td><td>Delaware</td><td>100</td></tr>
            <tr><td>Beta Corp</td><td>Canada</td><td>51</td></tr>
        </table>
        </body></html>
        """
        subs = _extract_from_tables(html)
        assert len(subs) == 2
        assert subs[0].ownership_pct == 100.0
        assert subs[1].ownership_pct == 51.0

    def test_wdesk_style_table(self):
        """Test the Wdesk-generated format (Apple, Berkshire, etc.)."""
        html = """
        <html><body>
        <table style="border-collapse:collapse">
            <tr><td colspan="3"></td>
                <td colspan="3" style="text-align:center">
                    <font style="font-weight:700">Jurisdiction<br>of Incorporation</font>
                </td></tr>
            <tr><td colspan="3"><font>Apple Asia Limited</font></td>
                <td colspan="3"><font>Hong Kong</font></td></tr>
            <tr><td colspan="3"><font>Apple Canada Inc.</font></td>
                <td colspan="3"><font>Canada</font></td></tr>
        </table>
        </body></html>
        """
        subs = _extract_from_tables(html)
        assert len(subs) >= 2
        names = [s.name for s in subs]
        assert "Apple Asia Limited" in names
        assert "Apple Canada Inc." in names

    def test_heuristic_table(self):
        """Table without explicit headers but clear 2-column structure."""
        html = """
        <html><body>
        <table>
            <tr><td>Alpha Pro Tech, Inc.</td><td>Oklahoma</td></tr>
            <tr><td>Alpha ProTech Engineered Products, Inc.</td><td>Delaware</td></tr>
        </table>
        </body></html>
        """
        subs = _extract_from_tables(html)
        assert len(subs) == 2


class TestPreExtraction:
    def test_pre_block(self):
        html = """
        <html><body>
        <pre>
        Alpha Corporation               Delaware
        Beta International Ltd           United Kingdom
        Gamma Holdings                   Cayman Islands
        </pre>
        </body></html>
        """
        subs = _extract_from_pre(html)
        assert len(subs) >= 2


class TestTextExtraction:
    def test_parenthetical(self):
        html = """
        <html><body>
        <p>Alpha Corp (Delaware)</p>
        <p>Beta Ltd (United Kingdom)</p>
        </body></html>
        """
        subs = _extract_from_text(html)
        assert len(subs) == 2
        assert subs[0].name == "Alpha Corp"
        assert subs[0].jurisdiction_raw == "Delaware"

    def test_dash_separated(self):
        html = """
        <html><body>
        <p>Alpha Corp - Delaware</p>
        <p>Beta Ltd - United Kingdom</p>
        </body></html>
        """
        subs = _extract_from_text(html)
        assert len(subs) == 2


class TestFullParse:
    def test_parse_simple_exhibit(self):
        html = """
        <DOCUMENT>
        <TYPE>EX-21.1
        <TEXT>
        <html><body>
        <p><b>Exhibit 21.1</b></p>
        <p><b>Subsidiaries of Example Corp</b></p>
        <table>
            <tr><td><u>Name of Subsidiary</u></td><td><u>State of Incorporation</u></td></tr>
            <tr><td>Sub One Inc.</td><td>Delaware</td></tr>
            <tr><td>Sub Two LLC</td><td>Nevada</td></tr>
            <tr><td>Sub Three Ltd</td><td>United Kingdom</td></tr>
        </table>
        </body></html>
        </TEXT>
        </DOCUMENT>
        """
        result = parse_exhibit21(html)
        assert result.parse_method == "table"
        assert len(result.subsidiaries) == 3
        assert result.subsidiaries[0].name == "Sub One Inc."
        assert result.subsidiaries[2].jurisdiction_raw == "United Kingdom"
        assert result.error is None

    def test_parse_empty(self):
        result = parse_exhibit21("<html><body></body></html>")
        assert result.parse_method == "none"
        assert len(result.subsidiaries) == 0
        assert result.error is not None
