"""
Quality scoring for CFPB Consumer Complaint Cross-Linked Analysis.

Implements a weighted quality score (0.0 - 1.0) for financial institution
records based on data completeness across all linked tables.

All scoring is deterministic and rule-based -- zero LLM dependency.

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Quality Score Configuration
# ---------------------------------------------------------------------------

# Weight configuration for institution quality scoring
# Weights must sum to 1.0
INSTITUTION_QUALITY_WEIGHTS = {
    "has_institution_name": 0.10,
    "has_location": 0.10,
    "has_financial_data": 0.10,
    "has_complaints_linked": 0.20,
    "has_cra_rating": 0.15,
    "has_enforcement_history": 0.15,
    "has_regulator_info": 0.10,
    "has_cert_number": 0.10,
}

# Minimum quality score threshold for "acceptable" records
MINIMUM_QUALITY_THRESHOLD = 0.40

# CRA rating values (for validation)
VALID_CRA_RATINGS = {
    "Outstanding",
    "Satisfactory",
    "Needs to Improve",
    "Substantial Noncompliance",
}


@dataclass
class QualityReport:
    """Container for a quality assessment of a single institution."""

    cert_number: int
    institution_name: str
    score: float = 0.0
    components: dict = field(default_factory=dict)
    passes_threshold: bool = False
    issues: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Component Checkers
# ---------------------------------------------------------------------------

def _check_has_institution_name(institution: dict) -> bool:
    """Check if institution has a non-empty name."""
    name = institution.get("institution_name", "")
    return bool(name and name.strip())


def _check_has_location(institution: dict) -> bool:
    """Check if institution has both city and state."""
    city = institution.get("city", "")
    state = institution.get("state", "")
    return bool(city and city.strip() and state and state.strip())


def _check_has_financial_data(institution: dict) -> bool:
    """Check if institution has total assets data."""
    assets = institution.get("total_assets")
    return assets is not None and float(assets) > 0


def _check_has_complaints_linked(institution: dict, db_conn=None) -> bool:
    """
    Check if institution has at least one linked CFPB complaint.

    Args:
        institution: Institution dict.
        db_conn: Optional database connection for live lookup.

    Returns:
        True if at least one complaint is linked.
    """
    # If pre-computed complaint_count is available
    if "complaint_count" in institution:
        return int(institution["complaint_count"]) > 0

    # Otherwise check the database
    if db_conn is not None:
        cert = institution.get("cert_number")
        if cert is not None:
            cursor = db_conn.execute(
                "SELECT COUNT(*) FROM institution_complaints WHERE cert_number = ?",
                (cert,),
            )
            return cursor.fetchone()[0] > 0

    return False


def _check_has_cra_rating(institution: dict, db_conn=None) -> bool:
    """
    Check if institution has at least one CRA rating on file.

    Args:
        institution: Institution dict.
        db_conn: Optional database connection for live lookup.

    Returns:
        True if at least one CRA rating exists.
    """
    if "cra_rating" in institution:
        return bool(institution["cra_rating"])

    if db_conn is not None:
        cert = institution.get("cert_number")
        if cert is not None:
            cursor = db_conn.execute(
                "SELECT COUNT(*) FROM cra_ratings WHERE cert_number = ?",
                (cert,),
            )
            return cursor.fetchone()[0] > 0

    return False


def _check_has_enforcement_history(institution: dict, db_conn=None) -> bool:
    """
    Check if institution has at least one enforcement action linked.

    Args:
        institution: Institution dict.
        db_conn: Optional database connection for live lookup.

    Returns:
        True if at least one enforcement action exists.
    """
    if "enforcement_count" in institution:
        return int(institution["enforcement_count"]) > 0

    if db_conn is not None:
        cert = institution.get("cert_number")
        if cert is not None:
            cursor = db_conn.execute(
                "SELECT COUNT(*) FROM enforcement_actions WHERE institution_cert = ?",
                (cert,),
            )
            return cursor.fetchone()[0] > 0

    return False


def _check_has_regulator_info(institution: dict) -> bool:
    """Check if institution has a primary regulator identified."""
    regulator = institution.get("regulator", "")
    return bool(regulator and regulator.strip())


def _check_has_cert_number(institution: dict) -> bool:
    """Check if institution has an FDIC CERT number."""
    cert = institution.get("cert_number")
    return cert is not None


# ---------------------------------------------------------------------------
# Scoring Functions
# ---------------------------------------------------------------------------

def compute_institution_quality_score(
    institution: dict,
    db_conn=None,
    weights: Optional[dict] = None,
) -> QualityReport:
    """
    Compute the quality score for a single financial institution.

    The score is a weighted sum of binary component checks, yielding
    a value between 0.0 and 1.0.

    Args:
        institution: Dict with institution data fields.
        db_conn: Optional database connection for cross-table lookups.
        weights: Optional custom weight dict. Uses defaults if not provided.

    Returns:
        QualityReport with score, component breakdown, and issues.
    """
    if weights is None:
        weights = INSTITUTION_QUALITY_WEIGHTS

    report = QualityReport(
        cert_number=institution.get("cert_number", 0),
        institution_name=institution.get("institution_name", "Unknown"),
    )

    # Evaluate each component
    checkers = {
        "has_institution_name": lambda: _check_has_institution_name(institution),
        "has_location": lambda: _check_has_location(institution),
        "has_financial_data": lambda: _check_has_financial_data(institution),
        "has_complaints_linked": lambda: _check_has_complaints_linked(institution, db_conn),
        "has_cra_rating": lambda: _check_has_cra_rating(institution, db_conn),
        "has_enforcement_history": lambda: _check_has_enforcement_history(institution, db_conn),
        "has_regulator_info": lambda: _check_has_regulator_info(institution),
        "has_cert_number": lambda: _check_has_cert_number(institution),
    }

    total_score = 0.0
    for component, checker in checkers.items():
        passed = checker()
        weight = weights.get(component, 0.0)
        report.components[component] = {
            "passed": passed,
            "weight": weight,
            "contribution": weight if passed else 0.0,
        }
        if passed:
            total_score += weight
        else:
            report.issues.append(f"Missing: {component} (weight: {weight:.2f})")

    report.score = round(total_score, 4)
    report.passes_threshold = report.score >= MINIMUM_QUALITY_THRESHOLD

    return report


def compute_batch_quality_scores(
    institutions: list[dict],
    db_conn=None,
    weights: Optional[dict] = None,
) -> list[QualityReport]:
    """
    Compute quality scores for a batch of institutions.

    Args:
        institutions: List of institution dicts.
        db_conn: Optional database connection for cross-table lookups.
        weights: Optional custom weight dict.

    Returns:
        List of QualityReport objects.
    """
    reports = []
    for inst in institutions:
        report = compute_institution_quality_score(inst, db_conn, weights)
        reports.append(report)
    return reports


def get_quality_summary(reports: list[QualityReport]) -> dict:
    """
    Compute summary statistics from a batch of quality reports.

    Args:
        reports: List of QualityReport objects.

    Returns:
        dict with keys:
            - total_institutions: int
            - avg_score: float
            - min_score: float
            - max_score: float
            - above_threshold: int
            - below_threshold: int
            - threshold_rate: float (0.0-1.0)
            - component_pass_rates: dict mapping component name to pass rate
    """
    if not reports:
        return {
            "total_institutions": 0,
            "avg_score": 0.0,
            "min_score": 0.0,
            "max_score": 0.0,
            "above_threshold": 0,
            "below_threshold": 0,
            "threshold_rate": 0.0,
            "component_pass_rates": {},
        }

    scores = [r.score for r in reports]
    above = sum(1 for r in reports if r.passes_threshold)

    # Component pass rates
    component_counts = {}
    for report in reports:
        for comp, info in report.components.items():
            if comp not in component_counts:
                component_counts[comp] = 0
            if info["passed"]:
                component_counts[comp] += 1

    total = len(reports)
    component_pass_rates = {
        comp: round(count / total, 4) for comp, count in component_counts.items()
    }

    return {
        "total_institutions": total,
        "avg_score": round(sum(scores) / total, 4),
        "min_score": round(min(scores), 4),
        "max_score": round(max(scores), 4),
        "above_threshold": above,
        "below_threshold": total - above,
        "threshold_rate": round(above / total, 4),
        "component_pass_rates": component_pass_rates,
    }
