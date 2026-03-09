"""
Institution risk scoring for CFPB Consumer Complaint Cross-Linked Analysis.

Computes composite risk scores combining complaint patterns, enforcement
history, financial health, and lending data into a single risk metric.

All scoring is deterministic and rule-based -- zero LLM dependency.

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import sqlite3
from typing import Optional

from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Risk Score Configuration
# ---------------------------------------------------------------------------

RISK_SCORE_WEIGHTS = {
    "complaint_volume_normalized": 0.25,  # complaints per $B assets
    "complaint_resolution": 0.10,         # % timely response, % disputed
    "enforcement_severity": 0.20,         # cross-agency enforcement count + penalties
    "financial_health": 0.15,             # capital ratios, ROA, asset quality
    "lending_fairness": 0.15,             # HMDA denial rate disparities
    "cra_rating": 0.15,                   # CRA exam grade (when available)
}

# Risk tiers: higher score = lower risk
RISK_TIERS = {
    "LOW": (0.8, 1.0),
    "MEDIUM": (0.5, 0.8),
    "HIGH": (0.3, 0.5),
    "CRITICAL": (0.0, 0.3),
}

CRA_RATING_SCORES = {
    "Outstanding": 1.0,
    "Satisfactory": 0.7,
    "Needs to Improve": 0.3,
    "Substantial Noncompliance": 0.0,
}


def classify_risk_tier(score: float) -> str:
    """Classify a risk score into a tier."""
    if score >= 0.8:
        return "LOW"
    elif score >= 0.5:
        return "MEDIUM"
    elif score >= 0.3:
        return "HIGH"
    else:
        return "CRITICAL"


def _compute_complaint_volume_score(
    complaint_count: int,
    total_assets_thousands: Optional[float],
) -> tuple[float, float]:
    """
    Compute normalized complaint volume score.

    Returns (score, complaints_per_billion_assets).
    Higher score = lower complaint rate = better.
    """
    if not total_assets_thousands or total_assets_thousands <= 0:
        # No asset data -- use absolute count as proxy
        if complaint_count == 0:
            return 1.0, 0.0
        elif complaint_count < 10:
            return 0.8, 0.0
        elif complaint_count < 100:
            return 0.5, 0.0
        else:
            return 0.2, 0.0

    # Convert assets from thousands to billions
    assets_billions = total_assets_thousands / 1_000_000

    if assets_billions <= 0:
        return 0.5, 0.0

    complaints_per_b = complaint_count / assets_billions

    # Score: fewer complaints per $B = better
    if complaints_per_b == 0:
        score = 1.0
    elif complaints_per_b < 50:
        score = 0.9
    elif complaints_per_b < 200:
        score = 0.7
    elif complaints_per_b < 500:
        score = 0.5
    elif complaints_per_b < 1000:
        score = 0.3
    else:
        score = 0.1

    return score, complaints_per_b


def _compute_complaint_resolution_score(
    timely_rate: Optional[float],
    dispute_rate: Optional[float],
) -> float:
    """
    Compute complaint resolution quality score.

    Args:
        timely_rate: Fraction of complaints with timely response (0-1).
        dispute_rate: Fraction of complaints that were disputed (0-1).

    Returns:
        Score from 0 to 1 (higher = better resolution).
    """
    score = 0.5  # default if no data

    if timely_rate is not None:
        score = timely_rate * 0.7  # 70% weight on timely response

    if dispute_rate is not None:
        # Lower dispute rate = better
        score += (1.0 - dispute_rate) * 0.3

    return min(1.0, max(0.0, score))


def _compute_enforcement_severity_score(
    enforcement_count: int,
    total_penalties: float,
) -> float:
    """
    Compute enforcement severity score.

    Fewer enforcement actions and lower penalties = higher score.
    """
    if enforcement_count == 0:
        return 1.0

    # Penalty severity
    if total_penalties >= 1_000_000_000:
        penalty_score = 0.0
    elif total_penalties >= 100_000_000:
        penalty_score = 0.1
    elif total_penalties >= 10_000_000:
        penalty_score = 0.3
    elif total_penalties >= 1_000_000:
        penalty_score = 0.5
    else:
        penalty_score = 0.7

    # Count severity
    if enforcement_count >= 10:
        count_score = 0.1
    elif enforcement_count >= 5:
        count_score = 0.3
    elif enforcement_count >= 3:
        count_score = 0.5
    else:
        count_score = 0.7

    return (penalty_score * 0.6 + count_score * 0.4)


def _compute_financial_health_score(
    tier1_capital_ratio: Optional[float],
    roa: Optional[float],
    noncurrent_loans_pct: Optional[float],
) -> float:
    """
    Compute financial health score from Call Report metrics.

    Args:
        tier1_capital_ratio: Tier 1 risk-based capital ratio (%).
        roa: Return on assets (%).
        noncurrent_loans_pct: Noncurrent loans to total loans (%).

    Returns:
        Score from 0 to 1 (higher = healthier).
    """
    scores = []

    # Tier 1 Capital Ratio (well-capitalized >= 8%)
    if tier1_capital_ratio is not None:
        if tier1_capital_ratio >= 10:
            scores.append(1.0)
        elif tier1_capital_ratio >= 8:
            scores.append(0.8)
        elif tier1_capital_ratio >= 6:
            scores.append(0.5)
        elif tier1_capital_ratio >= 4:
            scores.append(0.3)
        else:
            scores.append(0.1)

    # ROA (healthy bank > 1%)
    if roa is not None:
        if roa >= 1.5:
            scores.append(1.0)
        elif roa >= 1.0:
            scores.append(0.8)
        elif roa >= 0.5:
            scores.append(0.6)
        elif roa >= 0:
            scores.append(0.4)
        else:
            scores.append(0.1)

    # Noncurrent loans (lower = better)
    if noncurrent_loans_pct is not None:
        if noncurrent_loans_pct <= 0.5:
            scores.append(1.0)
        elif noncurrent_loans_pct <= 1.0:
            scores.append(0.8)
        elif noncurrent_loans_pct <= 2.0:
            scores.append(0.6)
        elif noncurrent_loans_pct <= 5.0:
            scores.append(0.3)
        else:
            scores.append(0.1)

    if not scores:
        return 0.5  # Default if no financial data

    return sum(scores) / len(scores)


def _compute_lending_fairness_score(denial_rate: Optional[float]) -> float:
    """
    Compute lending fairness score from HMDA data.

    Lower denial rates generally indicate fairer lending practices.
    """
    if denial_rate is None:
        return 0.5  # Default if no HMDA data

    if denial_rate <= 0.05:
        return 1.0
    elif denial_rate <= 0.10:
        return 0.8
    elif denial_rate <= 0.20:
        return 0.6
    elif denial_rate <= 0.30:
        return 0.4
    elif denial_rate <= 0.50:
        return 0.2
    else:
        return 0.1


def _compute_cra_score(cra_rating: Optional[str]) -> float:
    """Convert CRA rating to a numeric score."""
    if cra_rating is None:
        return 0.5  # Default if no CRA data
    return CRA_RATING_SCORES.get(cra_rating, 0.5)


def compute_institution_risk_profile(
    institution: dict,
    financial_data: Optional[dict] = None,
    hmda_data: Optional[dict] = None,
) -> dict:
    """
    Compute a complete risk profile for a single institution.

    Args:
        institution: Dict with institution data including cert_number,
            institution_name, total_assets, complaint_count, enforcement_count,
            total_penalties, cra_rating, timely_rate, dispute_rate.
        financial_data: Optional dict with financial metrics.
        hmda_data: Optional dict with HMDA summary data.

    Returns:
        Dict matching institution_risk_profiles table schema.
    """
    from src.scrapers.fdic_financials import classify_asset_tier

    cert = institution.get("cert_number")
    name = institution.get("institution_name", "")
    assets = institution.get("total_assets")
    complaint_count = institution.get("complaint_count", 0)
    enforcement_count = institution.get("enforcement_count", 0)
    total_penalties = institution.get("total_penalties", 0.0)
    cra_rating = institution.get("cra_rating")
    timely_rate = institution.get("timely_rate")
    dispute_rate = institution.get("dispute_rate")

    # Asset tier classification
    asset_tier = classify_asset_tier(assets)

    # Component scores
    complaint_score, complaints_per_b = _compute_complaint_volume_score(
        complaint_count, assets
    )
    resolution_score = _compute_complaint_resolution_score(timely_rate, dispute_rate)
    enforcement_score = _compute_enforcement_severity_score(
        enforcement_count, total_penalties or 0.0
    )

    # Financial health from enrichment data
    if financial_data:
        financial_score = _compute_financial_health_score(
            financial_data.get("tier1_capital_ratio"),
            financial_data.get("roa"),
            financial_data.get("noncurrent_loans_pct"),
        )
    else:
        financial_score = 0.5

    # HMDA lending fairness
    if hmda_data:
        lending_score = _compute_lending_fairness_score(hmda_data.get("denial_rate"))
    else:
        lending_score = 0.5

    cra_score = _compute_cra_score(cra_rating)

    # Weighted composite score
    overall_score = (
        RISK_SCORE_WEIGHTS["complaint_volume_normalized"] * complaint_score +
        RISK_SCORE_WEIGHTS["complaint_resolution"] * resolution_score +
        RISK_SCORE_WEIGHTS["enforcement_severity"] * enforcement_score +
        RISK_SCORE_WEIGHTS["financial_health"] * financial_score +
        RISK_SCORE_WEIGHTS["lending_fairness"] * lending_score +
        RISK_SCORE_WEIGHTS["cra_rating"] * cra_score
    )

    risk_tier = classify_risk_tier(overall_score)

    return {
        "cert_number": cert,
        "institution_name": name,
        "total_assets": assets,
        "asset_tier": asset_tier,
        "complaint_count": complaint_count,
        "complaints_per_billion_assets": round(complaints_per_b, 2),
        "enforcement_count": enforcement_count,
        "total_penalties": total_penalties or 0.0,
        "financial_health_score": round(financial_score, 4),
        "complaint_severity_score": round(complaint_score, 4),
        "overall_risk_score": round(overall_score, 4),
        "risk_tier": risk_tier,
    }


def build_all_risk_profiles(conn: sqlite3.Connection) -> list[dict]:
    """
    Build risk profiles for all institutions in the database.

    Aggregates data from complaints, enforcement, financials, HMDA, and CRA
    into a single risk profile per institution.

    Args:
        conn: Active database connection.

    Returns:
        List of risk profile dicts.
    """
    console.print("  Building institution risk profiles...")

    # Get institutions with complaint counts and enforcement stats
    institutions = conn.execute("""
        SELECT
            fi.cert_number,
            fi.institution_name,
            fi.total_assets,
            COALESCE(ic_agg.complaint_count, 0) as complaint_count,
            COALESCE(ea_agg.enforcement_count, 0) + COALESCE(re_agg.reg_enforcement_count, 0) as enforcement_count,
            COALESCE(ea_agg.total_penalties, 0) + COALESCE(re_agg.reg_total_penalties, 0) as total_penalties,
            cra_latest.cra_rating,
            comp_stats.timely_rate,
            comp_stats.dispute_rate
        FROM financial_institutions fi
        LEFT JOIN (
            SELECT cert_number, COUNT(*) as complaint_count
            FROM institution_complaints
            GROUP BY cert_number
        ) ic_agg ON fi.cert_number = ic_agg.cert_number
        LEFT JOIN (
            SELECT institution_cert, COUNT(*) as enforcement_count,
                   SUM(COALESCE(penalty_amount, 0)) as total_penalties
            FROM enforcement_actions WHERE institution_cert IS NOT NULL
            GROUP BY institution_cert
        ) ea_agg ON fi.cert_number = ea_agg.institution_cert
        LEFT JOIN (
            SELECT cert_number, COUNT(*) as reg_enforcement_count,
                   SUM(COALESCE(penalty_amount, 0)) as reg_total_penalties
            FROM regulatory_enforcement WHERE cert_number IS NOT NULL
            GROUP BY cert_number
        ) re_agg ON fi.cert_number = re_agg.cert_number
        LEFT JOIN (
            SELECT cert_number, cra_rating,
                   ROW_NUMBER() OVER (PARTITION BY cert_number ORDER BY exam_date DESC) as rn
            FROM cra_ratings
        ) cra_latest ON fi.cert_number = cra_latest.cert_number AND cra_latest.rn = 1
        LEFT JOIN (
            SELECT ic.cert_number,
                   CAST(SUM(CASE WHEN c.timely_response = 'Yes' THEN 1 ELSE 0 END) AS REAL) /
                   NULLIF(COUNT(*), 0) as timely_rate,
                   CAST(SUM(CASE WHEN c.consumer_disputed = 'Yes' THEN 1 ELSE 0 END) AS REAL) /
                   NULLIF(COUNT(*), 0) as dispute_rate
            FROM institution_complaints ic
            JOIN cfpb_complaints c ON ic.complaint_id = c.complaint_id
            GROUP BY ic.cert_number
        ) comp_stats ON fi.cert_number = comp_stats.cert_number
    """).fetchall()

    # Get latest financial data per institution
    financials_lookup = {}
    fin_rows = conn.execute("""
        SELECT cert_number, tier1_capital_ratio, roa, noncurrent_loans_pct
        FROM institution_financials
        WHERE (cert_number, report_date) IN (
            SELECT cert_number, MAX(report_date)
            FROM institution_financials
            GROUP BY cert_number
        )
    """).fetchall()
    for row in fin_rows:
        financials_lookup[row["cert_number"]] = dict(row)

    # Get latest HMDA data per institution
    hmda_lookup = {}
    hmda_rows = conn.execute("""
        SELECT cert_number, denial_rate
        FROM hmda_institution_summary
        WHERE cert_number IS NOT NULL
        AND (lei, report_year) IN (
            SELECT lei, MAX(report_year)
            FROM hmda_institution_summary
            GROUP BY lei
        )
    """).fetchall()
    for row in hmda_rows:
        if row["cert_number"]:
            hmda_lookup[row["cert_number"]] = dict(row)

    # Build profiles
    profiles = []
    for inst in institutions:
        inst_dict = dict(inst)
        cert = inst_dict["cert_number"]

        financial_data = financials_lookup.get(cert)
        hmda_data = hmda_lookup.get(cert)

        profile = compute_institution_risk_profile(
            inst_dict, financial_data, hmda_data
        )
        profiles.append(profile)

    console.print(f"  Built {len(profiles)} risk profiles")

    # Summarize risk tiers
    tier_counts = {}
    for p in profiles:
        tier = p["risk_tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    for tier, count in sorted(tier_counts.items()):
        console.print(f"    {tier}: {count:,}")

    return profiles


def run_risk_profile_pipeline(conn: sqlite3.Connection) -> int:
    """
    Run the full risk profile computation pipeline.

    Args:
        conn: Active database connection.

    Returns:
        Number of risk profiles stored.
    """
    from src.storage.database import store_risk_profiles_batch, start_pipeline_run, complete_pipeline_run

    run_id = start_pipeline_run(conn, "risk_profiles")

    try:
        profiles = build_all_risk_profiles(conn)
        if profiles:
            stored = store_risk_profiles_batch(conn, profiles)
            complete_pipeline_run(conn, run_id, stored)
            console.print(f"  [green]Stored {stored:,} risk profiles[/green]")
            return stored
        else:
            complete_pipeline_run(conn, run_id, 0, notes="No institutions found")
            return 0
    except Exception as e:
        complete_pipeline_run(conn, run_id, 0, status="failed", notes=str(e))
        raise
