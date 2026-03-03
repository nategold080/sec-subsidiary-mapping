"""Quality scoring for labor compliance records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityScore:
    score: float
    components: dict[str, float]


WHD_WEIGHTS = {
    "has_case_id": 0.15,
    "has_employer_name": 0.20,
    "has_location": 0.15,
    "has_naics": 0.10,
    "has_dates": 0.10,
    "has_wages_or_penalties": 0.15,
    "has_employees_affected": 0.10,
    "has_violation_flags": 0.05,
}

OSHA_WEIGHTS = {
    "has_activity_number": 0.15,
    "has_employer_name": 0.20,
    "has_location": 0.15,
    "has_industry_code": 0.10,
    "has_dates": 0.10,
    "has_penalties": 0.10,
    "has_violation_counts": 0.10,
    "has_inspection_type": 0.10,
}

NLRB_WEIGHTS = {
    "has_case_number": 0.15,
    "has_case_name": 0.20,
    "has_dates": 0.15,
    "has_status": 0.10,
    "has_case_type": 0.10,
    "has_location": 0.15,
    "has_allegation": 0.15,
}


def score_whd_case(rec: dict) -> QualityScore:
    """Score a WHD case record."""
    components = {}
    components["has_case_id"] = 1.0 if rec.get("case_id") else 0.0
    components["has_employer_name"] = 1.0 if rec.get("trade_name") else 0.0
    components["has_location"] = 1.0 if (rec.get("state") and rec.get("city")) else (0.5 if rec.get("state") else 0.0)
    components["has_naics"] = 1.0 if rec.get("naics_code") else 0.0
    components["has_dates"] = 1.0 if rec.get("findings_start_date") else 0.0
    components["has_wages_or_penalties"] = 1.0 if (rec.get("back_wages_owed", 0) > 0 or rec.get("civil_penalties", 0) > 0) else 0.0
    components["has_employees_affected"] = 1.0 if rec.get("employees_affected", 0) > 0 else 0.0
    has_any_flag = any(rec.get(f, 0) for f in ["flsa_violated", "mspa_violated", "h1b_violated", "fmla_violated", "sca_violated", "dba_violated"])
    components["has_violation_flags"] = 1.0 if has_any_flag else 0.0

    score = sum(components[k] * WHD_WEIGHTS[k] for k in WHD_WEIGHTS)
    return QualityScore(score=round(score, 4), components=components)


def score_osha_inspection(rec: dict) -> QualityScore:
    """Score an OSHA inspection record."""
    components = {}
    components["has_activity_number"] = 1.0 if rec.get("activity_number") else 0.0
    components["has_employer_name"] = 1.0 if rec.get("establishment_name") else 0.0
    components["has_location"] = 1.0 if (rec.get("site_state") and rec.get("site_city")) else (0.5 if rec.get("site_state") else 0.0)
    components["has_industry_code"] = 1.0 if (rec.get("naics_code") or rec.get("sic_code")) else 0.0
    components["has_dates"] = 1.0 if rec.get("open_date") else 0.0
    components["has_penalties"] = 1.0 if rec.get("total_current_penalty", 0) > 0 else 0.0
    components["has_violation_counts"] = 1.0 if rec.get("num_violations", 0) > 0 else 0.0
    components["has_inspection_type"] = 1.0 if rec.get("inspection_type") else 0.0

    score = sum(components[k] * OSHA_WEIGHTS[k] for k in OSHA_WEIGHTS)
    return QualityScore(score=round(score, 4), components=components)


def score_nlrb_case(rec: dict) -> QualityScore:
    """Score an NLRB case record."""
    components = {}
    components["has_case_number"] = 1.0 if rec.get("case_number") else 0.0
    components["has_case_name"] = 1.0 if rec.get("case_name") else 0.0
    components["has_dates"] = 1.0 if rec.get("date_filed") else 0.0
    components["has_status"] = 1.0 if rec.get("status") else 0.0
    components["has_case_type"] = 1.0 if rec.get("case_type") else 0.0
    components["has_location"] = 1.0 if (rec.get("state") and rec.get("city")) else (0.5 if rec.get("state") else 0.0)
    components["has_allegation"] = 1.0 if rec.get("allegation") else 0.0

    score = sum(components[k] * NLRB_WEIGHTS[k] for k in NLRB_WEIGHTS)
    return QualityScore(score=round(score, 4), components=components)


def compute_compliance_score(
    whd_cases: int = 0,
    osha_inspections: int = 0,
    nlrb_cases: int = 0,
    total_back_wages: float = 0,
    total_penalties: float = 0,
    total_fatalities: int = 0,
    willful_violations: int = 0,
) -> float:
    """Compute a composite compliance score (0.0 = worst, 1.0 = best).

    Higher violations = lower score. Uses logarithmic scaling
    so a company with 100 cases isn't linearly 100x worse than 1 case.
    """
    import math

    # Each factor contributes to a penalty score (higher = worse)
    penalty = 0.0

    # Case volume penalty (log-scaled)
    total_cases = whd_cases + osha_inspections + nlrb_cases
    if total_cases > 0:
        penalty += min(0.3, 0.1 * math.log1p(total_cases))

    # Multi-agency penalty
    agencies = sum(1 for x in [whd_cases, osha_inspections, nlrb_cases] if x > 0)
    if agencies >= 3:
        penalty += 0.15
    elif agencies >= 2:
        penalty += 0.08

    # Financial severity
    total_money = total_back_wages + total_penalties
    if total_money > 0:
        penalty += min(0.25, 0.05 * math.log1p(total_money / 10000))

    # Fatality penalty (severe)
    if total_fatalities > 0:
        penalty += min(0.2, 0.1 * math.log1p(total_fatalities))

    # Willful violation penalty
    if willful_violations > 0:
        penalty += min(0.15, 0.05 * math.log1p(willful_violations))

    # Convert penalty to score (1.0 = clean, 0.0 = terrible)
    score = max(0.0, 1.0 - penalty)
    return round(score, 4)
