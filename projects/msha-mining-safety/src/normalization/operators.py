"""Operator name normalization and profile building for MSHA data."""

import re

CORP_SUFFIXES = [
    "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "CO",
    "LTD", "LIMITED", "LP", "LLP", "PLLC", "PC",
    "NA", "SA", "AG", "GMBH", "BV", "NV", "PLC",
    "PTY", "SRL", "SARL",
]

ABBREVIATIONS = {
    "INTL": "INTERNATIONAL",
    "TECH": "TECHNOLOGY",
    "MFG": "MANUFACTURING",
    "MGMT": "MANAGEMENT",
    "SVCS": "SERVICES",
    "SVC": "SERVICE",
    "AMER": "AMERICAN",
    "NATL": "NATIONAL",
    "ASSOC": "ASSOCIATES",
    "BROS": "BROTHERS",
    "CTR": "CENTER",
    "GRP": "GROUP",
    "MTN": "MOUNTAIN",
    "CONSTR": "CONSTRUCTION",
}


def normalize_operator_name(name: str) -> str:
    """Normalize an operator name for matching."""
    if not name:
        return ""
    n = name.upper().strip()
    # Remove DBA/FKA/AKA clauses
    n = re.sub(r"\b(D/?B/?A|F/?K/?A|A/?K/?A)\b.*", "", n)
    # Remove parenthetical content
    n = re.sub(r"\(.*?\)", "", n)
    # Remove "THE" prefix
    n = re.sub(r"^THE\s+", "", n)
    # Remove punctuation (keep spaces and hyphens)
    n = re.sub(r"[^\w\s-]", "", n)
    # Expand abbreviations
    tokens = n.split()
    tokens = [ABBREVIATIONS.get(t, t) for t in tokens]
    n = " ".join(tokens)
    # Strip legal suffixes (3 passes)
    suffix_pattern = r"\b(" + "|".join(CORP_SUFFIXES) + r")\b"
    for _ in range(3):
        n = re.sub(suffix_pattern, "", n)
    # Collapse whitespace
    n = re.sub(r"\s+", " ", n).strip()
    return n


def build_operator_profiles(conn) -> list[dict]:
    """Build operator profiles by aggregating across all tables (bulk SQL)."""
    cur = conn.cursor()

    # 1. Mine-level aggregation (one query)
    mine_agg = {}
    for row in cur.execute("""
        SELECT operator_id, operator_name,
               COUNT(*) as mine_count,
               SUM(CASE WHEN mine_status = 'Active' THEN 1 ELSE 0 END) as active_mine_count,
               COALESCE(SUM(no_employees), 0) as total_employees,
               GROUP_CONCAT(DISTINCT CASE WHEN state IS NOT NULL AND state != '' THEN state END) as states,
               GROUP_CONCAT(DISTINCT CASE WHEN mine_type IS NOT NULL AND mine_type != '' THEN mine_type END) as mine_types,
               GROUP_CONCAT(DISTINCT CASE WHEN primary_sic IS NOT NULL AND primary_sic != '' THEN primary_sic END) as commodities
        FROM mines
        WHERE operator_id IS NOT NULL AND operator_id != ''
        GROUP BY operator_id
    """):
        mine_agg[row["operator_id"]] = dict(row)

    # 2. Accident aggregation (one query)
    acc_agg = {}
    for row in cur.execute("""
        SELECT operator_id,
               COUNT(*) as total_accidents,
               SUM(CASE WHEN degree_injury_cd = '01' THEN 1 ELSE 0 END) as total_fatalities,
               SUM(CASE WHEN degree_injury_cd IN ('01','02','03','04','05') THEN 1 ELSE 0 END) as total_injuries,
               COALESCE(SUM(days_lost), 0) as days_lost
        FROM accidents
        WHERE operator_id IS NOT NULL AND operator_id != ''
        GROUP BY operator_id
    """):
        acc_agg[row["operator_id"]] = dict(row)

    # 3. Inspection aggregation (one query)
    insp_agg = {}
    for row in cur.execute("""
        SELECT operator_id, COUNT(*) as total_inspections
        FROM inspections
        WHERE operator_id IS NOT NULL AND operator_id != ''
        GROUP BY operator_id
    """):
        insp_agg[row["operator_id"]] = dict(row)

    # 4. Violation aggregation (one query, uses violator_id)
    viol_agg = {}
    for row in cur.execute("""
        SELECT violator_id as operator_id,
               COUNT(*) as total_violations,
               SUM(CASE WHEN sig_sub = 'Y' THEN 1 ELSE 0 END) as sig_sub_violations
        FROM violations
        WHERE violator_id IS NOT NULL AND violator_id != ''
        GROUP BY violator_id
    """):
        viol_agg[row["operator_id"]] = dict(row)

    # 5. Assessed-violation penalty aggregation (one query)
    pen_agg = {}
    for row in cur.execute("""
        SELECT operator_id,
               COALESCE(SUM(proposed_penalty_amt), 0) as total_proposed,
               COALESCE(SUM(paid_proposed_penalty_amt), 0) as total_paid
        FROM assessed_violations
        WHERE operator_id IS NOT NULL AND operator_id != ''
        GROUP BY operator_id
    """):
        pen_agg[row["operator_id"]] = dict(row)

    # Merge all into profiles
    profiles = []
    for op_id, m in mine_agg.items():
        op_name = m["operator_name"] or ""
        norm_name = normalize_operator_name(op_name)
        mine_count = m["mine_count"]

        a = acc_agg.get(op_id, {})
        i = insp_agg.get(op_id, {})
        v = viol_agg.get(op_id, {})
        p = pen_agg.get(op_id, {})

        total_fatalities = a.get("total_fatalities", 0) or 0
        total_injuries = a.get("total_injuries", 0) or 0
        total_violations = v.get("total_violations", 0) or 0
        sig_sub_violations = v.get("sig_sub_violations", 0) or 0
        total_proposed = p.get("total_proposed", 0) or 0

        safety_score = compute_safety_score(
            total_fatalities, total_injuries, total_violations,
            sig_sub_violations, total_proposed, mine_count
        )

        # Sort pipe-delimited lists
        states_raw = m.get("states") or ""
        types_raw = m.get("mine_types") or ""
        commod_raw = m.get("commodities") or ""

        profiles.append({
            "operator_id": op_id,
            "operator_name": op_name,
            "normalized_name": norm_name,
            "mine_count": mine_count,
            "active_mine_count": m["active_mine_count"],
            "total_employees": m["total_employees"],
            "total_accidents": a.get("total_accidents", 0) or 0,
            "total_fatalities": total_fatalities,
            "total_injuries": total_injuries,
            "total_inspections": i.get("total_inspections", 0) or 0,
            "total_violations": total_violations,
            "total_proposed_penalties": total_proposed,
            "total_paid_penalties": p.get("total_paid", 0) or 0,
            "sig_sub_violations": sig_sub_violations,
            "days_lost": a.get("days_lost", 0) or 0,
            "states": "|".join(sorted(states_raw.split(","))) if states_raw else "",
            "mine_types": "|".join(sorted(types_raw.split(","))) if types_raw else "",
            "commodities": "|".join(sorted(commod_raw.split(","))[:10]) if commod_raw else "",
            "safety_score": safety_score,
            "risk_tier": assign_risk_tier(safety_score),
        })

    return profiles


def compute_safety_score(
    fatalities: int,
    injuries: int,
    violations: int,
    sig_sub: int,
    penalties: float,
    mine_count: int,
) -> float:
    """Compute composite safety score (0.0-1.0, higher = safer).

    Components:
    - Fatalities (25%): 0 = 1.0, 1 = 0.3, 2+ = 0.05
    - Injury rate (25%): 0 = 1.0, 1-5 = 0.7, 6-20 = 0.4, 21-50 = 0.2, 51+ = 0.05
    - Violation rate (20%): per mine — 0 = 1.0, <10 = 0.7, <50 = 0.4, <100 = 0.2, 100+ = 0.05
    - S&S violations (15%): 0 = 1.0, 1-5 = 0.7, 6-20 = 0.4, 21-50 = 0.2, 51+ = 0.05
    - Penalty severity (15%): $0 = 1.0, <$10K = 0.7, <$100K = 0.4, <$1M = 0.2, $1M+ = 0.05
    """
    # Fatalities (25%)
    if fatalities == 0:
        fat_score = 1.0
    elif fatalities == 1:
        fat_score = 0.3
    else:
        fat_score = 0.05

    # Injuries (25%)
    if injuries == 0:
        inj_score = 1.0
    elif injuries <= 5:
        inj_score = 0.7
    elif injuries <= 20:
        inj_score = 0.4
    elif injuries <= 50:
        inj_score = 0.2
    else:
        inj_score = 0.05

    # Violation rate per mine (20%)
    viol_per_mine = violations / max(mine_count, 1)
    if viol_per_mine == 0:
        viol_score = 1.0
    elif viol_per_mine < 10:
        viol_score = 0.7
    elif viol_per_mine < 50:
        viol_score = 0.4
    elif viol_per_mine < 100:
        viol_score = 0.2
    else:
        viol_score = 0.05

    # S&S violations (15%)
    if sig_sub == 0:
        ss_score = 1.0
    elif sig_sub <= 5:
        ss_score = 0.7
    elif sig_sub <= 20:
        ss_score = 0.4
    elif sig_sub <= 50:
        ss_score = 0.2
    else:
        ss_score = 0.05

    # Penalty severity (15%)
    if penalties == 0:
        pen_score = 1.0
    elif penalties < 10_000:
        pen_score = 0.7
    elif penalties < 100_000:
        pen_score = 0.4
    elif penalties < 1_000_000:
        pen_score = 0.2
    else:
        pen_score = 0.05

    return round(
        fat_score * 0.25
        + inj_score * 0.25
        + viol_score * 0.20
        + ss_score * 0.15
        + pen_score * 0.15,
        3,
    )


def assign_risk_tier(score: float) -> str:
    """Assign risk tier based on safety score."""
    if score >= 0.8:
        return "LOW"
    elif score >= 0.5:
        return "MEDIUM"
    elif score >= 0.3:
        return "HIGH"
    else:
        return "CRITICAL"
