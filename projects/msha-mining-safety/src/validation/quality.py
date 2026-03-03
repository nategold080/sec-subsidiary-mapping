"""Quality scoring for MSHA records."""


def _has(val) -> float:
    """Return 1.0 if value is present and non-empty, else 0.0."""
    if val is None:
        return 0.0
    if isinstance(val, str) and not val.strip():
        return 0.0
    return 1.0


def score_mine(rec: dict) -> float:
    """Quality score for a mine record (0.0-1.0).

    Components: mine_id (15%), mine_name (15%), operator (15%), state (10%),
    mine_type (10%), mine_status (10%), primary_sic (10%), location (10%), employees (5%)
    """
    return round(
        _has(rec.get("mine_id")) * 0.15
        + _has(rec.get("mine_name")) * 0.15
        + _has(rec.get("operator_name")) * 0.15
        + _has(rec.get("state")) * 0.10
        + _has(rec.get("mine_type")) * 0.10
        + _has(rec.get("mine_status")) * 0.10
        + _has(rec.get("primary_sic")) * 0.10
        + (_has(rec.get("latitude")) * _has(rec.get("longitude"))) * 0.10
        + _has(rec.get("no_employees")) * 0.05,
        3,
    )


def score_accident(rec: dict) -> float:
    """Quality score for an accident record (0.0-1.0).

    Components: document_no (10%), mine_id (10%), operator (10%), date (10%),
    degree_injury (15%), classification (10%), narrative (15%), nature_injury (10%), body_part (10%)
    """
    return round(
        _has(rec.get("document_no")) * 0.10
        + _has(rec.get("mine_id")) * 0.10
        + _has(rec.get("operator_name")) * 0.10
        + _has(rec.get("accident_dt")) * 0.10
        + _has(rec.get("degree_injury")) * 0.15
        + _has(rec.get("classification")) * 0.10
        + _has(rec.get("narrative")) * 0.15
        + _has(rec.get("nature_injury")) * 0.10
        + _has(rec.get("inj_body_part")) * 0.10,
        3,
    )


def score_inspection(rec: dict) -> float:
    """Quality score for an inspection record (0.0-1.0).

    Components: event_no (15%), mine_id (15%), operator (15%),
    begin_date (15%), end_date (10%), activity (15%), coal_metal (15%)
    """
    return round(
        _has(rec.get("event_no")) * 0.15
        + _has(rec.get("mine_id")) * 0.15
        + _has(rec.get("operator_name")) * 0.15
        + _has(rec.get("inspection_begin_dt")) * 0.15
        + _has(rec.get("inspection_end_dt")) * 0.10
        + _has(rec.get("activity")) * 0.15
        + _has(rec.get("coal_metal_ind")) * 0.15,
        3,
    )


def score_violation(rec: dict) -> float:
    """Quality score for a violation record (0.0-1.0).

    Components: violation_no (10%), mine_id (10%), violator (10%), date (10%),
    section_of_act (15%), part_section (15%), sig_sub (10%), penalty (10%), coal_metal (10%)
    """
    return round(
        _has(rec.get("violation_no")) * 0.10
        + _has(rec.get("mine_id")) * 0.10
        + _has(rec.get("violator_name")) * 0.10
        + _has(rec.get("violation_issue_dt")) * 0.10
        + _has(rec.get("section_of_act")) * 0.15
        + _has(rec.get("part_section")) * 0.15
        + _has(rec.get("sig_sub")) * 0.10
        + _has(rec.get("proposed_penalty")) * 0.10
        + _has(rec.get("coal_metal_ind")) * 0.10,
        3,
    )


def score_assessed_violation(rec: dict) -> float:
    """Quality score for an assessed violation record (0.0-1.0).

    Components: violation_no (15%), mine_id (10%), operator (10%), date (10%),
    section_of_act (10%), penalty_amt (15%), sig_sub (10%), negligence (10%), gravity (10%)
    """
    return round(
        _has(rec.get("violation_no")) * 0.15
        + _has(rec.get("mine_id")) * 0.10
        + _has(rec.get("operator_name")) * 0.10
        + _has(rec.get("violation_issue_dt")) * 0.10
        + _has(rec.get("section_of_act")) * 0.10
        + _has(rec.get("proposed_penalty_amt")) * 0.15
        + _has(rec.get("sig_sub")) * 0.10
        + _has(rec.get("negligence")) * 0.10
        + _has(rec.get("gravity")) * 0.10,
        3,
    )


def score_penalty(rec: dict) -> float:
    """Quality score for a penalty docket record (0.0-1.0).

    Components: docket_no (15%), mine_id (15%), operator (15%), case_status (15%),
    proposed_penalty (20%), amount_paid (10%), cal_yr (10%)
    """
    return round(
        _has(rec.get("docket_no")) * 0.15
        + _has(rec.get("mine_id")) * 0.15
        + _has(rec.get("operator_name")) * 0.15
        + _has(rec.get("case_status")) * 0.15
        + _has(rec.get("proposed_penalty")) * 0.20
        + _has(rec.get("amount_paid")) * 0.10
        + _has(rec.get("cal_yr")) * 0.10,
        3,
    )
