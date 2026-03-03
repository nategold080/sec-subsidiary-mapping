"""Export MSHA data to CSV, JSON, and Markdown."""

import csv
import json
import os

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "exports")


def export_all(conn) -> dict:
    """Export all tables to CSV and generate summary."""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    results = {}

    tables = [
        "mines", "accidents", "inspections", "violations",
        "assessed_violations", "penalties", "operator_profiles",
    ]

    for table in tables:
        path = os.path.join(EXPORT_DIR, f"{table}.csv")
        cursor = conn.execute(f"SELECT * FROM {table}")
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for row in rows:
                writer.writerow(row)
        results[f"{table}_csv"] = len(rows)

    # Profiles JSON
    cursor = conn.execute("SELECT * FROM operator_profiles ORDER BY safety_score ASC LIMIT 500")
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    profiles = [dict(zip(cols, row)) for row in rows]
    path = os.path.join(EXPORT_DIR, "operator_profiles.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, default=str)
    results["profiles_json"] = len(profiles)

    # High-risk operators
    cursor = conn.execute(
        "SELECT * FROM operator_profiles WHERE risk_tier IN ('HIGH', 'CRITICAL') ORDER BY safety_score ASC"
    )
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    path = os.path.join(EXPORT_DIR, "high_risk_operators.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for row in rows:
            writer.writerow(row)
    results["high_risk_csv"] = len(rows)

    # Summary Markdown
    from ..storage.database import get_stats
    stats = get_stats(conn=conn)
    summary = _build_summary(stats)
    path = os.path.join(EXPORT_DIR, "summary.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(summary)
    results["summary_md"] = True

    return results


def _build_summary(stats: dict) -> str:
    """Build a Markdown summary of the database."""
    return f"""# MSHA Mining Safety & Enforcement Tracker — Summary

## Key Statistics

| Metric | Value |
|--------|-------|
| Mines | {stats.get('mines', 0):,} |
| Active Mines | {stats.get('active_mines', 0):,} |
| Accidents/Injuries | {stats.get('accidents', 0):,} |
| Fatalities | {stats.get('total_fatalities', 0):,} |
| Permanent Disabilities | {stats.get('total_permanent_disabilities', 0):,} |
| Inspections | {stats.get('inspections', 0):,} |
| Violations | {stats.get('violations', 0):,} |
| Assessed Violations | {stats.get('assessed_violations', 0):,} |
| Penalty Dockets | {stats.get('penalties', 0):,} |
| Total Proposed Penalties | ${stats.get('total_proposed_penalties', 0):,.2f} |
| Total Paid Penalties | ${stats.get('total_paid_penalties', 0):,.2f} |
| Operator Profiles | {stats.get('operator_profiles', 0):,} |
| States Covered | {stats.get('states_covered', 0)} |
| Accident Year Range | {stats.get('accident_year_range', 'N/A')} |

---

Built by **Nathan Goldberg** · nathanmauricegoldberg@gmail.com · [LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)
"""
