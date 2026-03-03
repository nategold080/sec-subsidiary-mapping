"""Export labor compliance data as CSV, JSON, Excel, and Markdown."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.storage.database import get_connection, init_db, get_stats

EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "exports"


def export_all(output_dir: Path | None = None) -> dict:
    """Export all data formats."""
    out = output_dir or EXPORT_DIR
    out.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    init_db(conn)

    results = {}
    results["csv"] = _export_csv(conn, out)
    results["json"] = _export_json(conn, out)
    results["excel"] = _export_excel(conn, out)
    results["markdown"] = _export_markdown(conn, out)

    conn.close()
    return results


def _export_csv(conn, out: Path) -> list[str]:
    """Export each table as CSV."""
    files = []

    # WHD Cases
    rows = conn.execute("SELECT * FROM whd_cases ORDER BY findings_start_date DESC").fetchall()
    if rows:
        path = out / "whd_cases.csv"
        _write_csv(path, rows)
        files.append(str(path))

    # OSHA Inspections
    rows = conn.execute("SELECT * FROM osha_inspections ORDER BY open_date DESC").fetchall()
    if rows:
        path = out / "osha_inspections.csv"
        _write_csv(path, rows)
        files.append(str(path))

    # NLRB Cases
    rows = conn.execute("SELECT * FROM nlrb_cases ORDER BY date_filed DESC").fetchall()
    if rows:
        path = out / "nlrb_cases.csv"
        _write_csv(path, rows)
        files.append(str(path))

    # Employers
    rows = conn.execute("SELECT * FROM employers ORDER BY compliance_score ASC").fetchall()
    if rows:
        path = out / "employers.csv"
        _write_csv(path, rows)
        files.append(str(path))

    # Cross-links
    rows = conn.execute("SELECT * FROM cross_links").fetchall()
    if rows:
        path = out / "cross_links.csv"
        _write_csv(path, rows)
        files.append(str(path))

    return files


def _export_json(conn, out: Path) -> str:
    """Export full dataset as JSON."""
    data = {
        "metadata": {
            "project": "Employer Labor Compliance Tracker",
            "author": "Nathan Goldberg",
            "contact": "nathanmauricegoldberg@gmail.com",
        },
        "stats": get_stats(conn),
        "whd_cases": [dict(r) for r in conn.execute("SELECT * FROM whd_cases ORDER BY findings_start_date DESC").fetchall()],
        "osha_inspections": [dict(r) for r in conn.execute("SELECT * FROM osha_inspections ORDER BY open_date DESC").fetchall()],
        "nlrb_cases": [dict(r) for r in conn.execute("SELECT * FROM nlrb_cases ORDER BY date_filed DESC").fetchall()],
        "employers": [dict(r) for r in conn.execute("SELECT * FROM employers ORDER BY compliance_score ASC").fetchall()],
    }

    path = out / "labor_compliance.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return str(path)


def _export_excel(conn, out: Path) -> str:
    """Export as styled Excel workbook."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return ""

    wb = Workbook()

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0984E3", end_color="0984E3", fill_type="solid")

    # WHD Cases sheet
    ws = wb.active
    ws.title = "WHD Cases"
    _write_sheet(ws, conn, "SELECT * FROM whd_cases ORDER BY back_wages_owed DESC", header_font, header_fill)

    # OSHA sheet
    ws2 = wb.create_sheet("OSHA Inspections")
    _write_sheet(ws2, conn, "SELECT * FROM osha_inspections ORDER BY total_current_penalty DESC", header_font, header_fill)

    # NLRB sheet
    ws3 = wb.create_sheet("NLRB Cases")
    _write_sheet(ws3, conn, "SELECT * FROM nlrb_cases ORDER BY date_filed DESC", header_font, header_fill)

    # Employers sheet
    ws4 = wb.create_sheet("Employers")
    _write_sheet(ws4, conn, "SELECT * FROM employers ORDER BY compliance_score ASC", header_font, header_fill)

    path = out / "labor_compliance.xlsx"
    wb.save(str(path))
    return str(path)


def _export_markdown(conn, out: Path) -> str:
    """Export a summary Markdown report."""
    s = get_stats(conn)

    lines = [
        "# Employer Labor Compliance Tracker — Summary Report",
        "",
        f"**Built by Nathan Goldberg** | nathanmauricegoldberg@gmail.com",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| WHD Wage & Hour Cases | {s['whd_count']:,} |",
        f"| OSHA Safety Inspections | {s['osha_count']:,} |",
        f"| NLRB Labor Relations Cases | {s['nlrb_count']:,} |",
        f"| Unique Employer Profiles | {s['employer_count']:,} |",
        f"| Cross-Agency Links | {s['cross_link_count']:,} |",
        f"| Total Back Wages | ${s['total_back_wages']:,.0f} |",
        f"| Total WHD Penalties | ${s['total_whd_penalties']:,.0f} |",
        f"| Total OSHA Penalties | ${s['total_osha_penalties']:,.0f} |",
        f"| Workplace Fatalities | {s['total_fatalities']:,} |",
        f"| Employees Affected | {s['employees_affected']:,} |",
        "",
        "## Data Quality",
        "",
        f"| Source | Avg Quality Score |",
        f"|--------|------------------|",
        f"| WHD | {s['avg_quality']['whd']:.3f} |",
        f"| OSHA | {s['avg_quality']['osha']:.3f} |",
        f"| NLRB | {s['avg_quality']['nlrb']:.3f} |",
        "",
    ]

    if s["top_states"]:
        lines.append("## Top States by WHD Cases")
        lines.append("")
        lines.append("| State | Cases |")
        lines.append("|-------|-------|")
        for state, cnt in s["top_states"]:
            lines.append(f"| {state} | {cnt:,} |")
        lines.append("")

    if s["top_industries"]:
        lines.append("## Top Industries")
        lines.append("")
        lines.append("| Industry | Cases |")
        lines.append("|----------|-------|")
        for industry, cnt in s["top_industries"]:
            lines.append(f"| {industry} | {cnt:,} |")
        lines.append("")

    if s["multi_agency_offenders"]:
        lines.append("## Multi-Agency Offenders")
        lines.append("")
        lines.append("Employers flagged across 2+ federal agencies:")
        lines.append("")
        lines.append("| Employer | WHD Cases | OSHA Inspections | NLRB Cases | Total |")
        lines.append("|----------|-----------|-----------------|------------|-------|")
        for emp in s["multi_agency_offenders"]:
            total = emp["whd_case_count"] + emp["osha_inspection_count"] + emp["nlrb_case_count"]
            lines.append(
                f"| {emp['name_normalized']} | {emp['whd_case_count']} | "
                f"{emp['osha_inspection_count']} | {emp['nlrb_case_count']} | {total} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("*Data sourced from DOL Wage & Hour Division, OSHA, and NLRB public records.*")

    path = out / "summary.md"
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return str(path)


def _write_csv(path: Path, rows: list) -> None:
    """Write rows to CSV."""
    if not rows:
        return
    keys = rows[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _write_sheet(ws, conn, query: str, header_font, header_fill) -> None:
    """Write query results to an Excel worksheet."""
    rows = conn.execute(query).fetchall()
    if not rows:
        return

    # Headers
    keys = list(rows[0].keys())
    for col, key in enumerate(keys, 1):
        cell = ws.cell(row=1, column=col, value=key)
        cell.font = header_font
        cell.fill = header_fill

    # Data
    for row_idx, row in enumerate(rows, 2):
        for col_idx, key in enumerate(keys, 1):
            ws.cell(row=row_idx, column=col_idx, value=row[key])

    # Auto-fit column widths (approximate)
    for col_idx, key in enumerate(keys, 1):
        ws.column_dimensions[chr(64 + min(col_idx, 26))].width = max(len(key) + 2, 12)
