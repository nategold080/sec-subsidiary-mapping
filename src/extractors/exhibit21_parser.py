"""Exhibit 21 HTML/text parser.

Extracts subsidiary names and jurisdictions from SEC Exhibit 21 filings.
Handles multiple HTML formats:
1. Standard HTML tables with header rows
2. Wdesk-style tables with colspan and font styling
3. Pre-formatted text blocks
4. Paragraph/div based listings

All extraction is rule-based (zero LLM dependency).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag


@dataclass
class SubsidiaryRecord:
    """A single subsidiary extracted from an Exhibit 21."""
    name: str
    jurisdiction_raw: str
    ownership_pct: Optional[float] = None
    parent_indicator: Optional[str] = None  # e.g., "(1)", "*"

    def __post_init__(self):
        self.name = self.name.strip()
        self.jurisdiction_raw = self.jurisdiction_raw.strip()


@dataclass
class ExhibitParseResult:
    """Result of parsing an Exhibit 21 file."""
    subsidiaries: list[SubsidiaryRecord] = field(default_factory=list)
    parse_method: str = ""  # "table", "pre", "paragraph", "fallback"
    raw_text_length: int = 0
    error: Optional[str] = None


# Patterns for detecting subsidiary table headers
HEADER_PATTERNS = [
    re.compile(r"name\s+of\s+subsid", re.I),
    re.compile(r"subsid.*name", re.I),
    re.compile(r"name\s+of\s+entit", re.I),
    re.compile(r"entity\s+name", re.I),
    re.compile(r"company\s+name", re.I),
    re.compile(r"name\s+of\s+compan", re.I),
]

JURISDICTION_PATTERNS = [
    re.compile(r"jurisdict", re.I),
    re.compile(r"state.*incorp", re.I),
    re.compile(r"state.*organ", re.I),
    re.compile(r"place.*incorp", re.I),
    re.compile(r"place.*organ", re.I),
    re.compile(r"country.*incorp", re.I),
    re.compile(r"state.*country", re.I),
    re.compile(r"incorp.*jurisdict", re.I),
    re.compile(r"organized\s+under", re.I),
]

OWNERSHIP_PATTERNS = [
    re.compile(r"%\s*own", re.I),
    re.compile(r"percent.*own", re.I),
    re.compile(r"ownership", re.I),
]

# Patterns to skip — these are not subsidiary data rows
SKIP_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"^\s*\*", re.I),  # Footnote
    re.compile(r"^exhibit\s+21", re.I),
    re.compile(r"^subsidiaries\s+of", re.I),
    re.compile(r"^list\s+of\s+subsid", re.I),
    re.compile(r"^the\s+following", re.I),
    re.compile(r"^pursuant\s+to", re.I),
    re.compile(r"^see\s+note", re.I),
    re.compile(r"^note:", re.I),
    re.compile(r"^\(\d+\)\s*$"),  # Just a footnote number
    re.compile(r"^page\s+\d+", re.I),
    re.compile(r"^reg\.\s*s-k", re.I),
    re.compile(r"^item\s+601", re.I),
]


def parse_exhibit21(html: str) -> ExhibitParseResult:
    """Parse an Exhibit 21 HTML/text file and extract subsidiaries.

    Tries multiple strategies in order:
    1. HTML table extraction
    2. Pre-formatted text extraction
    3. Paragraph/line-based extraction

    Args:
        html: Raw HTML/text content of the Exhibit 21 file.

    Returns:
        ExhibitParseResult with extracted subsidiaries.
    """
    result = ExhibitParseResult(raw_text_length=len(html))

    # Strip SGML document wrapper if present
    html = _strip_sgml_wrapper(html)

    # Try table extraction first (most common format)
    subs = _extract_from_tables(html)
    if subs:
        result.subsidiaries = subs
        result.parse_method = "table"
        return result

    # Try pre-formatted text
    subs = _extract_from_pre(html)
    if subs:
        result.subsidiaries = subs
        result.parse_method = "pre"
        return result

    # Try paragraph/line-based extraction
    subs = _extract_from_text(html)
    if subs:
        result.subsidiaries = subs
        result.parse_method = "paragraph"
        return result

    result.parse_method = "none"
    result.error = "No subsidiaries extracted by any method"
    return result


def _strip_sgml_wrapper(html: str) -> str:
    """Strip SEC SGML <DOCUMENT> wrapper if present."""
    # Find the start of actual HTML content
    text_match = re.search(r"<TEXT>\s*", html, re.I)
    if text_match:
        html = html[text_match.end():]
    # Strip closing tags
    html = re.sub(r"</TEXT>\s*</DOCUMENT>\s*$", "", html, flags=re.I)
    return html


def _extract_from_tables(html: str) -> list[SubsidiaryRecord]:
    """Extract subsidiaries from HTML tables."""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")

    if not tables:
        return []

    all_subs = []
    for table in tables:
        subs = _parse_table(table)
        if subs:
            all_subs.extend(subs)

    return all_subs


def _parse_table(table: Tag) -> list[SubsidiaryRecord]:
    """Parse a single HTML table for subsidiary data."""
    rows = table.find_all("tr")
    if not rows:
        return []

    # Find header row and column indices
    header_row_idx = None
    name_col = None
    juris_col = None
    pct_col = None

    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [_clean_text(c.get_text()) for c in cells]

        # Check if this row contains header keywords
        row_text = " ".join(cell_texts)

        has_name_header = any(p.search(row_text) for p in HEADER_PATTERNS)
        has_juris_header = any(p.search(row_text) for p in JURISDICTION_PATTERNS)

        if has_name_header or has_juris_header:
            header_row_idx = i

            # Find which columns contain what
            for j, text in enumerate(cell_texts):
                if any(p.search(text) for p in HEADER_PATTERNS):
                    name_col = j
                elif any(p.search(text) for p in JURISDICTION_PATTERNS):
                    juris_col = j
                elif any(p.search(text) for p in OWNERSHIP_PATTERNS):
                    pct_col = j

            # If we found jurisdiction but not name, name is likely first column
            if juris_col is not None and name_col is None:
                name_col = 0 if juris_col != 0 else 1
            # If we found name but not jurisdiction, jurisdiction is likely second column
            if name_col is not None and juris_col is None:
                juris_col = 1 if name_col != 1 else 0

            break

    # If no explicit header found, try heuristic: 2-column table where
    # first column has company-like names and second has jurisdictions
    if header_row_idx is None:
        return _parse_table_heuristic(rows)

    if name_col is None or juris_col is None:
        return _parse_table_heuristic(rows)

    # Extract data rows after header
    subs = []
    for row in rows[header_row_idx + 1:]:
        cells = row.find_all(["th", "td"])
        cell_texts = [_clean_text(c.get_text()) for c in cells]

        if len(cell_texts) <= max(name_col, juris_col):
            continue

        name = cell_texts[name_col]
        jurisdiction = cell_texts[juris_col]

        # Skip non-data rows
        if _should_skip_row(name, jurisdiction):
            continue

        pct = None
        if pct_col is not None and pct_col < len(cell_texts):
            pct = _parse_percentage(cell_texts[pct_col])

        if name and jurisdiction:
            subs.append(SubsidiaryRecord(
                name=name,
                jurisdiction_raw=jurisdiction,
                ownership_pct=pct,
            ))

    return subs


def _parse_table_heuristic(rows: list[Tag]) -> list[SubsidiaryRecord]:
    """Parse table without explicit headers using heuristics."""
    subs = []

    for row in rows:
        cells = row.find_all(["th", "td"])
        cell_texts = [_clean_text(c.get_text()) for c in cells]

        # Filter out empty cells
        non_empty = [t for t in cell_texts if t]

        if len(non_empty) < 2:
            continue

        # Skip header-like rows
        row_text = " ".join(non_empty)
        if any(p.search(row_text) for p in HEADER_PATTERNS):
            continue
        if any(p.search(row_text) for p in JURISDICTION_PATTERNS):
            continue

        name = non_empty[0]
        jurisdiction = non_empty[1]

        # Validate: name should look like a company, jurisdiction like a place
        if _should_skip_row(name, jurisdiction):
            continue

        # jurisdiction should be a recognizable place
        if not _looks_like_jurisdiction(jurisdiction):
            continue

        pct = None
        if len(non_empty) > 2:
            pct = _parse_percentage(non_empty[2])

        subs.append(SubsidiaryRecord(
            name=name,
            jurisdiction_raw=jurisdiction,
            ownership_pct=pct,
        ))

    return subs


def _extract_from_pre(html: str) -> list[SubsidiaryRecord]:
    """Extract subsidiaries from <pre> formatted text blocks."""
    soup = BeautifulSoup(html, "lxml")
    pre_blocks = soup.find_all("pre")

    if not pre_blocks:
        return []

    subs = []
    for pre in pre_blocks:
        text = pre.get_text()
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue

            # Try to split by multiple spaces (column alignment)
            parts = re.split(r"\s{3,}", line)
            if len(parts) >= 2:
                name = parts[0].strip()
                jurisdiction = parts[1].strip()

                if _should_skip_row(name, jurisdiction):
                    continue
                if not _looks_like_jurisdiction(jurisdiction):
                    continue

                pct = None
                if len(parts) > 2:
                    pct = _parse_percentage(parts[2])

                subs.append(SubsidiaryRecord(
                    name=name,
                    jurisdiction_raw=jurisdiction,
                    ownership_pct=pct,
                ))

    return subs


def _extract_from_text(html: str) -> list[SubsidiaryRecord]:
    """Extract subsidiaries from paragraph/text-based formats.

    Looks for patterns like:
    - "Company Name (Jurisdiction)"
    - "Company Name - Jurisdiction"
    - "Company Name, Jurisdiction"
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n")
    lines = text.split("\n")

    subs = []

    # Pattern: "Company Name (Jurisdiction)"
    paren_pattern = re.compile(
        r"^(.+?)\s*\(([A-Za-z\s.,]+)\)\s*$"
    )
    # Pattern: "Company Name - Jurisdiction" or "Company Name -- Jurisdiction"
    dash_pattern = re.compile(
        r"^(.+?)\s*[-–—]+\s+([A-Za-z\s.,]+)\s*$"
    )

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        if any(p.search(line) for p in SKIP_PATTERNS):
            continue

        # Try parenthetical pattern
        m = paren_pattern.match(line)
        if m:
            name, jurisdiction = m.group(1).strip(), m.group(2).strip()
            if not _should_skip_row(name, jurisdiction) and _looks_like_jurisdiction(jurisdiction):
                subs.append(SubsidiaryRecord(name=name, jurisdiction_raw=jurisdiction))
                continue

        # Try dash pattern
        m = dash_pattern.match(line)
        if m:
            name, jurisdiction = m.group(1).strip(), m.group(2).strip()
            if not _should_skip_row(name, jurisdiction) and _looks_like_jurisdiction(jurisdiction):
                subs.append(SubsidiaryRecord(name=name, jurisdiction_raw=jurisdiction))
                continue

    return subs


def _clean_text(text: str) -> str:
    """Clean extracted text: normalize whitespace, strip, decode entities."""
    # Replace &nbsp; and other whitespace
    text = re.sub(r"[\xa0\u00a0\u2003\u2002\u2009]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Strip parenthetical footnote refs like (1), (2), (a)
    text = re.sub(r"\s*\(\d+\)\s*$", "", text)
    text = re.sub(r"\s*\([a-z]\)\s*$", "", text)
    return text.strip()


def _should_skip_row(name: str, jurisdiction: str) -> bool:
    """Check if a row should be skipped (not a real subsidiary entry)."""
    combined = f"{name} {jurisdiction}"

    for pattern in SKIP_PATTERNS:
        if pattern.search(name):
            return True

    # Skip if name is too short (likely noise)
    if len(name) < 3:
        return True

    # Skip if name is all uppercase single word and less than 4 chars
    if name.isupper() and len(name) < 4 and " " not in name:
        return True

    return False


def _looks_like_jurisdiction(text: str) -> bool:
    """Check if text looks like a valid jurisdiction."""
    if not text or len(text) < 2:
        return False

    t = text.lower().strip()

    # Common US state names and abbreviations
    us_indicators = [
        "delaware", "california", "new york", "texas", "nevada", "florida",
        "georgia", "ohio", "illinois", "pennsylvania", "virginia", "maryland",
        "massachusetts", "michigan", "minnesota", "missouri", "colorado",
        "connecticut", "indiana", "iowa", "kansas", "kentucky", "louisiana",
        "new jersey", "north carolina", "oregon", "tennessee", "washington",
        "wisconsin", "arizona", "oklahoma", "south carolina", "nebraska",
        "utah", "rhode island", "hawaii", "alabama", "arkansas", "montana",
        "wyoming", "maine", "idaho", "new hampshire", "vermont",
        "west virginia", "north dakota", "south dakota", "mississippi",
        "new mexico", "puerto rico", "district of columbia",
    ]

    # Common country/territory names
    country_indicators = [
        "united kingdom", "u.k.", "uk", "england", "canada", "ireland",
        "germany", "france", "japan", "china", "hong kong", "singapore",
        "australia", "netherlands", "switzerland", "luxembourg",
        "cayman", "bermuda", "british virgin", "bvi", "jersey",
        "guernsey", "isle of man", "mauritius", "panama", "bahamas",
        "barbados", "brazil", "india", "korea", "taiwan", "israel",
        "mexico", "italy", "spain", "sweden", "norway", "denmark",
        "belgium", "austria", "poland", "czech", "hungary",
        "united arab", "uae", "saudi", "south africa",
        "united states", "u.s.", "usa",
    ]

    # Check 2-letter state abbreviations
    if re.match(r"^[A-Z]{2}$", text):
        return True

    # Check if text matches any known jurisdiction
    for j in us_indicators + country_indicators:
        if j in t:
            return True

    # Check if text ends with ", U.S." or similar
    if re.search(r",?\s*u\.?s\.?a?\.?$", t):
        return True

    return False


def _parse_percentage(text: str) -> Optional[float]:
    """Parse an ownership percentage from text."""
    text = text.strip().replace("%", "")
    try:
        val = float(text)
        if 0 <= val <= 100:
            return val
        return None
    except (ValueError, TypeError):
        return None
