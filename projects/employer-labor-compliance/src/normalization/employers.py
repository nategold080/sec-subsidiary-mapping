"""Employer name normalization and entity resolution."""

from __future__ import annotations

import re
from collections import defaultdict

# Common suffixes to strip
SUFFIXES = re.compile(
    r",?\s*("
    r"INC\.?|LLC\.?|LTD\.?|CORP\.?|CORPORATION|COMPANY|CO\.?"
    r"|L\.?L\.?C\.?|L\.?L\.?P\.?|L\.?P\.?"
    r"|P\.?C\.?|P\.?L\.?L\.?C\.?"
    r"|DBA\s+.+|D/B/A\s+.+"
    r"|THE|A\s+.+COMPANY"
    r")\s*$",
    re.IGNORECASE,
)

# Common abbreviation expansions
ABBREVIATIONS = {
    "INTL": "INTERNATIONAL",
    "NATL": "NATIONAL",
    "MGMT": "MANAGEMENT",
    "SVCS": "SERVICES",
    "SVC": "SERVICE",
    "HOSP": "HOSPITAL",
    "ASSOC": "ASSOCIATES",
    "ASSN": "ASSOCIATION",
    "GOVT": "GOVERNMENT",
    "DEPT": "DEPARTMENT",
    "UNIV": "UNIVERSITY",
    "CTR": "CENTER",
    "GRP": "GROUP",
    "CONSTR": "CONSTRUCTION",
    "MAINT": "MAINTENANCE",
    "MFG": "MANUFACTURING",
    "DIST": "DISTRIBUTION",
    "TECH": "TECHNOLOGY",
    "BLDG": "BUILDING",
    "ELEC": "ELECTRIC",
    "ELECTR": "ELECTRICAL",
}


def normalize_employer(name: str) -> str:
    """Normalize an employer name for matching.

    Steps:
    1. Uppercase
    2. Strip suffixes (Inc, LLC, Corp, etc.)
    3. Remove punctuation
    4. Expand common abbreviations
    5. Collapse whitespace
    """
    if not name:
        return ""

    n = name.strip().upper()

    # Strip DBA first (everything after DBA is a trade name)
    dba_match = re.search(r"\s+(?:DBA|D/B/A)\s+", n)
    if dba_match:
        n = n[:dba_match.start()]

    # Strip suffixes (may need multiple passes)
    for _ in range(3):
        prev = n
        n = SUFFIXES.sub("", n).strip().rstrip(",").strip()
        if n == prev:
            break

    # Remove possessive
    n = re.sub(r"'S\b", "S", n)

    # Remove periods within initials (B.J. -> BJ)
    n = re.sub(r"\.(?=[A-Z])", "", n)
    # Remove remaining punctuation except hyphens and ampersands
    n = re.sub(r"[.,;:!?()\"'/]", " ", n)

    # Normalize ampersand
    n = n.replace("&", " AND ")

    # Expand abbreviations
    words = n.split()
    expanded = []
    for w in words:
        expanded.append(ABBREVIATIONS.get(w, w))
    n = " ".join(expanded)

    # Collapse whitespace
    n = re.sub(r"\s+", " ", n).strip()

    # Remove leading "THE "
    if n.startswith("THE "):
        n = n[4:]

    return n


def extract_dba_name(name: str) -> str | None:
    """Extract DBA (doing business as) name if present."""
    if not name:
        return None
    m = re.search(r"\s+(?:DBA|D/B/A)\s+(.+)", name, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def normalize_state(state: str) -> str:
    """Normalize state codes to 2-letter abbreviation."""
    if not state:
        return ""
    s = state.strip().upper()
    # Already 2-letter code
    if len(s) == 2:
        return s
    # Full state name mapping (partial)
    STATE_MAP = {
        "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
        "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
        "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID",
        "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS",
        "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
        "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
        "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
        "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
        "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK",
        "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC",
        "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT",
        "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
        "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC",
        "PUERTO RICO": "PR", "GUAM": "GU", "VIRGIN ISLANDS": "VI",
    }
    return STATE_MAP.get(s, s)
