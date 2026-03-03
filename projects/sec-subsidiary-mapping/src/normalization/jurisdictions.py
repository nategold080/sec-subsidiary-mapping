"""Jurisdiction normalization.

Maps raw jurisdiction strings from Exhibit 21 filings to standardized
codes. Handles US state names/abbreviations, country names, and common
variations. Flags tax haven jurisdictions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@dataclass
class NormalizedJurisdiction:
    """A normalized jurisdiction."""
    code: str          # ISO 3166-1 alpha-2 or US state abbreviation
    name: str          # Full canonical name
    country: str       # "US" for US states, otherwise ISO country code
    is_us_state: bool
    is_tax_haven: bool
    raw: str           # Original text before normalization


# Load config once
_config = None
_us_states = None
_countries = None
_country_lookup = None
_tax_havens = None


def _load_config():
    """Load jurisdictions config from YAML."""
    global _config, _us_states, _countries, _country_lookup, _tax_havens

    config_path = CONFIG_DIR / "jurisdictions.yaml"
    with open(config_path) as f:
        _config = yaml.safe_load(f)

    _us_states = _config.get("us_states", {})
    _countries = _config.get("countries", {})
    _tax_havens = set(_config.get("tax_havens", []))

    # Build reverse lookup: lowercase name/variation -> code
    _country_lookup = {}
    for code, names in _countries.items():
        if isinstance(names, list):
            for name in names:
                _country_lookup[name.lower()] = code
        else:
            _country_lookup[str(names).lower()] = code


def normalize_jurisdiction(raw: str) -> Optional[NormalizedJurisdiction]:
    """Normalize a raw jurisdiction string.

    Args:
        raw: Raw jurisdiction text from Exhibit 21 (e.g., "Delaware, U.S.",
             "Cayman Islands", "DE", "Hong Kong").

    Returns:
        NormalizedJurisdiction or None if unrecognizable.
    """
    if _config is None:
        _load_config()

    if not raw or not raw.strip():
        return None

    text = raw.strip()
    # Remove trailing periods and parenthetical footnotes
    text = re.sub(r"\s*\(\d+\)\s*$", "", text)
    text = re.sub(r"\.\s*$", "", text)
    text = text.strip()

    if not text:
        return None

    # Strategy 1: Exact US state abbreviation (2 letters)
    upper = text.upper().strip()
    # Handle "DE, U.S." or "CA, USA" patterns
    state_match = re.match(r"^([A-Z]{2})\s*[,/]\s*(U\.?S\.?A?\.?)?\s*$", upper)
    if state_match:
        abbrev = state_match.group(1)
        if abbrev in _us_states:
            return NormalizedJurisdiction(
                code=abbrev, name=_us_states[abbrev], country="US",
                is_us_state=True, is_tax_haven=False, raw=raw,
            )

    # Bare 2-letter code
    if re.match(r"^[A-Z]{2}$", upper) and upper in _us_states:
        return NormalizedJurisdiction(
            code=upper, name=_us_states[upper], country="US",
            is_us_state=True, is_tax_haven=False, raw=raw,
        )

    # Strategy 2: Full US state name
    lower = text.lower().strip()
    # Strip ", U.S." / ", USA" / ", United States" suffix
    lower_stripped = re.sub(
        r",?\s*(u\.?s\.?a?\.?|united\s+states(\s+of\s+america)?)$",
        "", lower
    ).strip()

    for abbrev, name in _us_states.items():
        if lower_stripped == name.lower():
            return NormalizedJurisdiction(
                code=abbrev, name=name, country="US",
                is_us_state=True, is_tax_haven=False, raw=raw,
            )

    # Strategy 3: Country name lookup
    # Try full text first (may include ", U.S." which we want to skip)
    country_code = _match_country(lower_stripped)
    if country_code:
        is_haven = country_code in _tax_havens
        # Get canonical name
        names = _countries.get(country_code, [])
        canonical = names[0] if isinstance(names, list) and names else country_code
        return NormalizedJurisdiction(
            code=country_code, name=canonical, country=country_code,
            is_us_state=False, is_tax_haven=is_haven, raw=raw,
        )

    # Try original lower text too
    if lower != lower_stripped:
        country_code = _match_country(lower)
        if country_code:
            is_haven = country_code in _tax_havens
            names = _countries.get(country_code, [])
            canonical = names[0] if isinstance(names, list) and names else country_code
            return NormalizedJurisdiction(
                code=country_code, name=canonical, country=country_code,
                is_us_state=False, is_tax_haven=is_haven, raw=raw,
            )

    # Strategy 4: 2-letter code as country code
    if re.match(r"^[A-Z]{2}$", upper) and upper in _countries:
        is_haven = upper in _tax_havens
        names = _countries.get(upper, [])
        canonical = names[0] if isinstance(names, list) and names else upper
        return NormalizedJurisdiction(
            code=upper, name=canonical, country=upper,
            is_us_state=False, is_tax_haven=is_haven, raw=raw,
        )

    return None


def _match_country(text: str) -> Optional[str]:
    """Match text against known country names. Returns ISO code or None."""
    # Exact match
    if text in _country_lookup:
        return _country_lookup[text]

    # Substring match (for "Republic of Ireland" matching "Ireland")
    for name, code in _country_lookup.items():
        if name in text or text in name:
            return code

    return None


def is_tax_haven(code: str) -> bool:
    """Check if a jurisdiction code is a tax haven."""
    if _config is None:
        _load_config()
    return code in _tax_havens
