"""Quality scoring for subsidiary records.

Each record scored 0.0-1.0 based on completeness and data quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class QualityScore:
    """Quality score with component breakdown."""
    score: float
    components: dict[str, float]

    @property
    def above_threshold(self) -> bool:
        return self.score >= 0.40


# Quality scoring weights
WEIGHTS = {
    "has_subsidiary_name": 0.20,
    "has_jurisdiction": 0.20,
    "has_parent_cik": 0.15,
    "has_filing_date": 0.10,
    "has_ownership_pct": 0.10,
    "jurisdiction_normalized": 0.10,
    "has_parent_financials": 0.10,
    "has_source_url": 0.05,
}


def score_subsidiary(record: dict) -> QualityScore:
    """Score a subsidiary record for quality/completeness.

    Args:
        record: Dict with subsidiary data fields.

    Returns:
        QualityScore with total and per-component scores.
    """
    components = {}

    # has_subsidiary_name: 0.20
    name = record.get("subsidiary_name", "")
    components["has_subsidiary_name"] = WEIGHTS["has_subsidiary_name"] if name else 0.0

    # has_jurisdiction: 0.20
    juris = record.get("jurisdiction_raw", "") or record.get("jurisdiction_code", "")
    components["has_jurisdiction"] = WEIGHTS["has_jurisdiction"] if juris else 0.0

    # has_parent_cik: 0.15
    cik = record.get("parent_cik", "")
    components["has_parent_cik"] = WEIGHTS["has_parent_cik"] if cik else 0.0

    # has_filing_date: 0.10
    date = record.get("filing_date", "")
    components["has_filing_date"] = WEIGHTS["has_filing_date"] if date else 0.0

    # has_ownership_pct: 0.10
    pct = record.get("ownership_pct")
    components["has_ownership_pct"] = WEIGHTS["has_ownership_pct"] if pct is not None else 0.0

    # jurisdiction_normalized: 0.10
    code = record.get("jurisdiction_code", "")
    components["jurisdiction_normalized"] = WEIGHTS["jurisdiction_normalized"] if code else 0.0

    # has_parent_financials: 0.10
    rev = record.get("parent_revenue") or record.get("parent_assets")
    components["has_parent_financials"] = WEIGHTS["has_parent_financials"] if rev else 0.0

    # has_source_url: 0.05
    url = record.get("source_url", "")
    components["has_source_url"] = WEIGHTS["has_source_url"] if url else 0.0

    total = sum(components.values())
    return QualityScore(score=round(total, 4), components=components)


def score_filing(record: dict) -> QualityScore:
    """Score a filing-level record for quality."""
    components = {}
    components["has_accession"] = 0.20 if record.get("accession") else 0.0
    components["has_cik"] = 0.20 if record.get("cik") else 0.0
    components["has_company_name"] = 0.15 if record.get("company_name") else 0.0
    components["has_filing_date"] = 0.15 if record.get("file_date") else 0.0
    components["has_subsidiaries"] = 0.20 if record.get("subsidiary_count", 0) > 0 else 0.0
    components["has_exhibit_url"] = 0.10 if record.get("exhibit_url") else 0.0

    total = sum(components.values())
    return QualityScore(score=round(total, 4), components=components)
