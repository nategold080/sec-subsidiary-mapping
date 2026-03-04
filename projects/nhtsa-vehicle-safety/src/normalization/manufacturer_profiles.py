"""Manufacturer risk scoring and profile builder.

Aggregates complaint, recall, and investigation data into manufacturer-level
risk profiles with severity scoring, trend analysis, and tier classification.
All computed from existing database tables — no new data sources needed.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from src.normalization.vehicles import normalize_make

# Risk score weights (percentile-based)
RISK_WEIGHTS = {
    "death_rate_pctl": 0.30,
    "injury_rate_pctl": 0.20,
    "fire_rate_pctl": 0.15,
    "recall_volume_pctl": 0.10,
    "investigation_rate_pctl": 0.10,
    "response_speed_pctl": 0.10,
    "trend_adjustment": 0.05,
}

RISK_TIERS = {
    "CRITICAL": (0.8, 1.0),
    "HIGH": (0.6, 0.8),
    "MEDIUM": (0.3, 0.6),
    "LOW": (0.0, 0.3),
}

# Minimum complaints to include in risk scoring (avoids noise from tiny manufacturers)
MIN_COMPLAINTS_FOR_SCORING = 50


def build_manufacturer_profiles(conn: sqlite3.Connection) -> dict:
    """Build manufacturer profiles from existing data.

    Returns dict with counts: profiles_created, yearly_metrics_created.
    """
    # Clear existing profiles
    conn.execute("DELETE FROM manufacturer_profiles")
    conn.execute("DELETE FROM manufacturer_yearly_metrics")

    # Step 1: Aggregate complaint metrics per manufacturer
    complaint_metrics = _aggregate_complaint_metrics(conn)

    # Step 2: Aggregate recall metrics per manufacturer
    recall_metrics = _aggregate_recall_metrics(conn)

    # Step 3: Aggregate investigation metrics per manufacturer
    investigation_metrics = _aggregate_investigation_metrics(conn)

    # Step 4: Build yearly metrics for trend analysis
    yearly_data = _build_yearly_metrics(conn)

    # Step 5: Merge all metrics into profiles
    all_manufacturers = set(complaint_metrics.keys()) | set(recall_metrics.keys()) | set(investigation_metrics.keys())
    profiles = []

    for mfr in all_manufacturers:
        cm = complaint_metrics.get(mfr, {})
        rm = recall_metrics.get(mfr, {})
        im = investigation_metrics.get(mfr, {})

        total_complaints = cm.get("total_complaints", 0)
        total_deaths = cm.get("total_deaths", 0)
        total_injuries = cm.get("total_injuries", 0)
        total_fires = cm.get("total_fires", 0)
        total_crashes = cm.get("total_crashes", 0)

        # Rates per 10,000 complaints
        if total_complaints > 0:
            death_rate = total_deaths / total_complaints * 10000
            injury_rate = total_injuries / total_complaints * 10000
            fire_rate = total_fires / total_complaints * 10000
            crash_rate = total_crashes / total_complaints * 10000
            severity_index = (
                total_deaths * 10 + total_injuries * 3 + total_fires * 2 + total_crashes
            ) / total_complaints
        else:
            death_rate = injury_rate = fire_rate = crash_rate = severity_index = 0.0

        # Trend analysis
        years = sorted(yearly_data.get(mfr, {}).keys())
        complaint_trend = _compute_trend([yearly_data.get(mfr, {}).get(y, {}).get("complaints", 0) for y in years[-3:]]) if len(years) >= 2 else "stable"
        severity_trend_vals = [yearly_data.get(mfr, {}).get(y, {}).get("severity", 0) for y in years[-3:]]
        severity_trend = _compute_trend(severity_trend_vals) if len(years) >= 2 else "stable"

        profile = {
            "manufacturer_name": mfr,
            "years_active_start": cm.get("year_start"),
            "years_active_end": cm.get("year_end"),
            "total_complaints": total_complaints,
            "total_recalls": rm.get("total_recalls", 0),
            "total_investigations": im.get("total_investigations", 0),
            "total_vehicles_affected": rm.get("total_affected", 0),
            "unique_models": cm.get("unique_models", 0),
            "total_deaths": total_deaths,
            "total_injuries": total_injuries,
            "total_fires": total_fires,
            "total_crashes": total_crashes,
            "death_rate": round(death_rate, 2),
            "injury_rate": round(injury_rate, 2),
            "fire_rate": round(fire_rate, 2),
            "crash_rate": round(crash_rate, 2),
            "severity_index": round(severity_index, 4),
            "avg_days_to_recall": rm.get("avg_days_to_recall"),
            "median_days_to_recall": rm.get("median_days_to_recall"),
            "investigation_to_recall_rate": im.get("investigation_to_recall_rate"),
            "complaint_trend": complaint_trend,
            "severity_trend": severity_trend,
            "risk_score": 0.0,  # Computed below
            "risk_tier": "LOW",
        }
        profiles.append(profile)

    # Step 6: Compute percentile-based risk scores
    _compute_risk_scores(profiles)

    # Step 7: Quality scores
    for p in profiles:
        p["quality_score"] = _score_profile_quality(p)

    # Step 8: Insert profiles
    profiles_created = 0
    for p in profiles:
        conn.execute("""
            INSERT OR REPLACE INTO manufacturer_profiles (
                manufacturer_name, years_active_start, years_active_end,
                total_complaints, total_recalls, total_investigations,
                total_vehicles_affected, unique_models,
                total_deaths, total_injuries, total_fires, total_crashes,
                death_rate, injury_rate, fire_rate, crash_rate, severity_index,
                avg_days_to_recall, median_days_to_recall,
                investigation_to_recall_rate,
                complaint_trend, severity_trend,
                risk_score, risk_tier, quality_score
            ) VALUES (
                :manufacturer_name, :years_active_start, :years_active_end,
                :total_complaints, :total_recalls, :total_investigations,
                :total_vehicles_affected, :unique_models,
                :total_deaths, :total_injuries, :total_fires, :total_crashes,
                :death_rate, :injury_rate, :fire_rate, :crash_rate, :severity_index,
                :avg_days_to_recall, :median_days_to_recall,
                :investigation_to_recall_rate,
                :complaint_trend, :severity_trend,
                :risk_score, :risk_tier, :quality_score
            )
        """, p)
        profiles_created += 1

    # Step 9: Insert yearly metrics
    yearly_created = 0
    for mfr, years_dict in yearly_data.items():
        for year, data in years_dict.items():
            conn.execute("""
                INSERT OR REPLACE INTO manufacturer_yearly_metrics (
                    manufacturer_name, year, complaint_count, recall_count,
                    investigation_count, death_count, injury_count,
                    fire_count, crash_count, severity_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mfr, year,
                data.get("complaints", 0), data.get("recalls", 0),
                data.get("investigations", 0), data.get("deaths", 0),
                data.get("injuries", 0), data.get("fires", 0),
                data.get("crashes", 0), data.get("severity", 0.0),
            ))
            yearly_created += 1

    conn.commit()
    return {
        "profiles_created": profiles_created,
        "yearly_metrics_created": yearly_created,
    }


def _aggregate_complaint_metrics(conn: sqlite3.Connection) -> dict:
    """Aggregate complaint data per manufacturer."""
    rows = conn.execute("""
        SELECT manufacturer,
               COUNT(*) as total_complaints,
               SUM(num_deaths) as total_deaths,
               SUM(num_injuries) as total_injuries,
               SUM(fire) as total_fires,
               SUM(crash) as total_crashes,
               COUNT(DISTINCT model) as unique_models,
               MIN(model_year) as year_start,
               MAX(model_year) as year_end
        FROM complaints
        WHERE manufacturer != ''
        GROUP BY manufacturer
    """).fetchall()

    metrics = {}
    for r in rows:
        mfr = normalize_make(r["manufacturer"])
        if mfr not in metrics:
            metrics[mfr] = {
                "total_complaints": 0, "total_deaths": 0, "total_injuries": 0,
                "total_fires": 0, "total_crashes": 0, "unique_models": 0,
                "year_start": r["year_start"], "year_end": r["year_end"],
            }
        m = metrics[mfr]
        m["total_complaints"] += r["total_complaints"]
        m["total_deaths"] += r["total_deaths"] or 0
        m["total_injuries"] += r["total_injuries"] or 0
        m["total_fires"] += r["total_fires"] or 0
        m["total_crashes"] += r["total_crashes"] or 0
        m["unique_models"] += r["unique_models"] or 0
        if r["year_start"] and (m["year_start"] is None or r["year_start"] < m["year_start"]):
            m["year_start"] = r["year_start"]
        if r["year_end"] and (m["year_end"] is None or r["year_end"] > m["year_end"]):
            m["year_end"] = r["year_end"]

    return metrics


def _aggregate_recall_metrics(conn: sqlite3.Connection) -> dict:
    """Aggregate recall data per manufacturer."""
    rows = conn.execute("""
        SELECT manufacturer,
               COUNT(*) as total_recalls,
               COALESCE(SUM(num_potentially_affected), 0) as total_affected
        FROM recalls
        WHERE manufacturer != ''
        GROUP BY manufacturer
    """).fetchall()

    metrics = {}
    for r in rows:
        mfr = normalize_make(r["manufacturer"])
        if mfr not in metrics:
            metrics[mfr] = {"total_recalls": 0, "total_affected": 0,
                           "avg_days_to_recall": None, "median_days_to_recall": None}
        metrics[mfr]["total_recalls"] += r["total_recalls"]
        metrics[mfr]["total_affected"] += r["total_affected"]

    return metrics


def _aggregate_investigation_metrics(conn: sqlite3.Connection) -> dict:
    """Aggregate investigation data per manufacturer."""
    # Count investigations per make (using make since investigations don't have manufacturer field)
    rows = conn.execute("""
        SELECT make,
               COUNT(*) as total_investigations,
               SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) as closed_count
        FROM investigations
        WHERE make != ''
        GROUP BY make
    """).fetchall()

    # Count investigations that resulted in recalls (via cross_links)
    recall_linked = conn.execute("""
        SELECT i.make, COUNT(DISTINCT cl.source_id) as linked_count
        FROM cross_links cl
        JOIN investigations i ON cl.source_id = i.investigation_number
        WHERE cl.source_type = 'recall' AND cl.target_type = 'investigation'
        GROUP BY i.make
    """).fetchall()
    recall_linked_map = {}
    for r in recall_linked:
        mfr = normalize_make(r["make"])
        recall_linked_map[mfr] = recall_linked_map.get(mfr, 0) + r["linked_count"]

    metrics = {}
    for r in rows:
        mfr = normalize_make(r["make"])
        if mfr not in metrics:
            metrics[mfr] = {"total_investigations": 0, "investigation_to_recall_rate": None}
        metrics[mfr]["total_investigations"] += r["total_investigations"]

        total_inv = metrics[mfr]["total_investigations"]
        linked = recall_linked_map.get(mfr, 0)
        if total_inv > 0:
            metrics[mfr]["investigation_to_recall_rate"] = round(linked / total_inv, 4)

    return metrics


def _build_yearly_metrics(conn: sqlite3.Connection) -> dict:
    """Build year-by-year metrics for each manufacturer."""
    # Complaints by year
    rows = conn.execute("""
        SELECT manufacturer, model_year as year,
               COUNT(*) as complaints,
               SUM(num_deaths) as deaths,
               SUM(num_injuries) as injuries,
               SUM(fire) as fires,
               SUM(crash) as crashes
        FROM complaints
        WHERE manufacturer != '' AND model_year >= 2000
        GROUP BY manufacturer, model_year
    """).fetchall()

    yearly = defaultdict(lambda: defaultdict(lambda: {
        "complaints": 0, "recalls": 0, "investigations": 0,
        "deaths": 0, "injuries": 0, "fires": 0, "crashes": 0, "severity": 0.0,
    }))

    for r in rows:
        mfr = normalize_make(r["manufacturer"])
        y = r["year"]
        d = yearly[mfr][y]
        d["complaints"] += r["complaints"]
        d["deaths"] += r["deaths"] or 0
        d["injuries"] += r["injuries"] or 0
        d["fires"] += r["fires"] or 0
        d["crashes"] += r["crashes"] or 0
        if d["complaints"] > 0:
            d["severity"] = round(
                (d["deaths"] * 10 + d["injuries"] * 3 + d["fires"] * 2 + d["crashes"])
                / d["complaints"], 4
            )

    # Recalls by year
    recall_rows = conn.execute("""
        SELECT manufacturer, model_year as year, COUNT(*) as recalls
        FROM recalls WHERE manufacturer != '' AND model_year >= 2000
        GROUP BY manufacturer, model_year
    """).fetchall()
    for r in recall_rows:
        mfr = normalize_make(r["manufacturer"])
        yearly[mfr][r["year"]]["recalls"] += r["recalls"]

    # Investigations by year (use open_date year)
    inv_rows = conn.execute("""
        SELECT make, CAST(substr(open_date, 1, 4) AS INTEGER) as year,
               COUNT(*) as investigations
        FROM investigations
        WHERE make != '' AND open_date != '' AND length(open_date) >= 4
        GROUP BY make, year
    """).fetchall()
    for r in inv_rows:
        mfr = normalize_make(r["make"])
        if r["year"] and r["year"] >= 2000:
            yearly[mfr][r["year"]]["investigations"] += r["investigations"]

    return yearly


def _compute_trend(values: list) -> str:
    """Compute trend direction from a list of values (last 3 years).

    Uses simple linear regression slope.
    Returns: 'increasing', 'decreasing', or 'stable'.
    """
    if len(values) < 2:
        return "stable"

    # Filter out zeros (no data)
    non_zero = [(i, v) for i, v in enumerate(values) if v > 0]
    if len(non_zero) < 2:
        return "stable"

    # Simple slope calculation
    n = len(non_zero)
    xs = [p[0] for p in non_zero]
    ys = [p[1] for p in non_zero]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)

    if denominator == 0:
        return "stable"

    slope = numerator / denominator
    # Normalize slope relative to mean to get percentage change
    if y_mean > 0:
        relative_slope = slope / y_mean
    else:
        return "stable"

    if relative_slope > 0.10:
        return "increasing"
    elif relative_slope < -0.10:
        return "decreasing"
    return "stable"


def _compute_risk_scores(profiles: list) -> None:
    """Compute percentile-based risk scores for all profiles.

    Modifies profiles in-place.
    """
    # Only score manufacturers with enough complaints to be meaningful
    scorable = [p for p in profiles if p["total_complaints"] >= MIN_COMPLAINTS_FOR_SCORING]

    if not scorable:
        return

    # Compute percentiles for each metric
    def percentile_rank(values: list) -> list:
        """Return percentile ranks (0.0-1.0) for each value."""
        if not values:
            return []
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        ranks = []
        for v in values:
            # Count values below
            below = sum(1 for sv in sorted_vals if sv < v)
            ranks.append(below / max(n - 1, 1))
        return ranks

    death_rates = [p["death_rate"] for p in scorable]
    injury_rates = [p["injury_rate"] for p in scorable]
    fire_rates = [p["fire_rate"] for p in scorable]
    recall_volumes = [p["total_recalls"] for p in scorable]
    inv_rates = [
        p["total_investigations"] / max(p["total_complaints"], 1) * 10000
        for p in scorable
    ]

    dr_pctl = percentile_rank(death_rates)
    ir_pctl = percentile_rank(injury_rates)
    fr_pctl = percentile_rank(fire_rates)
    rv_pctl = percentile_rank(recall_volumes)
    inv_pctl = percentile_rank(inv_rates)

    for i, p in enumerate(scorable):
        # Trend adjustment: worsening trend adds risk
        trend_val = 0.0
        if p["complaint_trend"] == "increasing":
            trend_val += 0.5
        if p["severity_trend"] in ("increasing", "worsening"):
            trend_val += 0.5

        risk_score = (
            RISK_WEIGHTS["death_rate_pctl"] * dr_pctl[i]
            + RISK_WEIGHTS["injury_rate_pctl"] * ir_pctl[i]
            + RISK_WEIGHTS["fire_rate_pctl"] * fr_pctl[i]
            + RISK_WEIGHTS["recall_volume_pctl"] * rv_pctl[i]
            + RISK_WEIGHTS["investigation_rate_pctl"] * inv_pctl[i]
            + RISK_WEIGHTS["response_speed_pctl"] * 0.5  # Default (no timing data yet)
            + RISK_WEIGHTS["trend_adjustment"] * trend_val
        )

        p["risk_score"] = round(min(risk_score, 1.0), 4)
        p["risk_tier"] = _get_tier(p["risk_score"])

    # Assign LOW tier to manufacturers below the scoring threshold
    scored_names = {p["manufacturer_name"] for p in scorable}
    for p in profiles:
        if p["manufacturer_name"] not in scored_names:
            p["risk_score"] = 0.0
            p["risk_tier"] = "LOW"


def _get_tier(score: float) -> str:
    """Get risk tier from score."""
    for tier, (low, high) in RISK_TIERS.items():
        if low <= score <= high:
            return tier
    return "LOW"


def _score_profile_quality(profile: dict) -> float:
    """Quality score for a manufacturer profile."""
    checks = {
        "has_complaints": 0.20 if profile["total_complaints"] > 0 else 0.0,
        "has_recalls": 0.15 if profile["total_recalls"] > 0 else 0.0,
        "has_investigations": 0.15 if profile["total_investigations"] > 0 else 0.0,
        "has_years": 0.10 if profile["years_active_start"] and profile["years_active_end"] else 0.0,
        "has_models": 0.10 if profile["unique_models"] > 0 else 0.0,
        "has_severity": 0.15 if profile["severity_index"] is not None else 0.0,
        "has_risk_score": 0.15 if profile["risk_score"] > 0 else 0.0,
    }
    return round(sum(checks.values()), 3)
