"""Export NHTSA data to CSV, JSON, Excel, Markdown."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "exports"


def export_all(fmt: str, conn=None) -> None:
    """Export data in the specified format."""
    from src.storage.database import get_connection, get_stats

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    _conn = conn or get_connection()

    if fmt in ("csv", "all"):
        _export_csv(_conn)
    if fmt in ("json", "all"):
        _export_json(_conn)
    if fmt in ("excel", "all"):
        _export_excel(_conn)
    if fmt in ("markdown", "all"):
        _export_markdown(_conn)

    if conn is None:
        _conn.close()


def _export_csv(conn) -> None:
    """Export complaints, recalls, and investigations to CSV."""
    # Complaints
    rows = conn.execute("""
        SELECT c.*, '' as recall_campaigns, '' as investigation_numbers
        FROM complaints c
        ORDER BY date_complaint_filed DESC
    """).fetchall()

    path = EXPORT_DIR / "complaints.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "odi_number", "manufacturer", "make", "model", "model_year",
            "crash", "fire", "injuries", "deaths",
            "date_of_incident", "date_complaint_filed",
            "components", "summary", "quality_score",
        ])
        for r in rows:
            writer.writerow([
                r["odi_number"], r["manufacturer"], r["make"], r["model"],
                r["model_year"], r["crash"], r["fire"],
                r["num_injuries"], r["num_deaths"],
                r["date_of_incident"], r["date_complaint_filed"],
                r["components"], r["summary"], r["quality_score"],
            ])
    print(f"  CSV: {len(rows)} complaints -> complaints.csv")

    # Recalls
    rows = conn.execute("SELECT * FROM recalls ORDER BY report_received_date DESC").fetchall()
    path = EXPORT_DIR / "recalls.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "campaign_number", "manufacturer", "make", "model", "model_year",
            "report_received_date", "component", "summary", "consequence",
            "remedy", "potentially_affected", "park_it", "quality_score",
        ])
        for r in rows:
            writer.writerow([
                r["campaign_number"], r["manufacturer"], r["make"], r["model"],
                r["model_year"], r["report_received_date"], r["component"],
                r["summary"], r["consequence"], r["remedy"],
                r["num_potentially_affected"], r["park_it"], r["quality_score"],
            ])
    print(f"  CSV: {len(rows)} recalls -> recalls.csv")

    # Investigations
    rows = conn.execute("SELECT * FROM investigations ORDER BY open_date DESC").fetchall()
    path = EXPORT_DIR / "investigations.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "investigation_number", "make", "model", "model_year_start",
            "model_year_end", "type", "status", "open_date", "close_date",
            "subject", "quality_score",
        ])
        for r in rows:
            writer.writerow([
                r["investigation_number"], r["make"], r["model"],
                r["model_year_start"], r["model_year_end"],
                r["investigation_type"], r["status"],
                r["open_date"], r["close_date"], r["subject"],
                r["quality_score"],
            ])
    print(f"  CSV: {len(rows)} investigations -> investigations.csv")

    # Manufacturer profiles
    try:
        rows = conn.execute("""
            SELECT * FROM manufacturer_profiles ORDER BY risk_score DESC
        """).fetchall()
        if rows:
            path = EXPORT_DIR / "manufacturer_profiles.csv"
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "manufacturer_name", "risk_tier", "risk_score", "severity_index",
                    "total_complaints", "total_recalls", "total_investigations",
                    "total_vehicles_affected", "unique_models",
                    "total_deaths", "total_injuries", "total_fires", "total_crashes",
                    "death_rate", "injury_rate", "fire_rate", "crash_rate",
                    "complaint_trend", "severity_trend",
                    "years_active_start", "years_active_end", "quality_score",
                ])
                for r in rows:
                    writer.writerow([
                        r["manufacturer_name"], r["risk_tier"], r["risk_score"],
                        r["severity_index"], r["total_complaints"], r["total_recalls"],
                        r["total_investigations"], r["total_vehicles_affected"],
                        r["unique_models"], r["total_deaths"], r["total_injuries"],
                        r["total_fires"], r["total_crashes"],
                        r["death_rate"], r["injury_rate"], r["fire_rate"], r["crash_rate"],
                        r["complaint_trend"], r["severity_trend"],
                        r["years_active_start"], r["years_active_end"], r["quality_score"],
                    ])
            print(f"  CSV: {len(rows)} manufacturer profiles -> manufacturer_profiles.csv")

        # Yearly metrics
        rows = conn.execute("""
            SELECT * FROM manufacturer_yearly_metrics ORDER BY manufacturer_name, year
        """).fetchall()
        if rows:
            path = EXPORT_DIR / "manufacturer_yearly_metrics.csv"
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "manufacturer_name", "year", "complaint_count", "recall_count",
                    "investigation_count", "death_count", "injury_count",
                    "fire_count", "crash_count", "severity_index",
                ])
                for r in rows:
                    writer.writerow([
                        r["manufacturer_name"], r["year"],
                        r["complaint_count"], r["recall_count"],
                        r["investigation_count"], r["death_count"],
                        r["injury_count"], r["fire_count"], r["crash_count"],
                        r["severity_index"],
                    ])
            print(f"  CSV: {len(rows)} yearly metrics -> manufacturer_yearly_metrics.csv")
    except Exception:
        pass  # Tables may not exist yet

    # Vehicle attributes
    try:
        rows = conn.execute("""
            SELECT * FROM vehicle_attributes ORDER BY make, model, model_year
        """).fetchall()
        if rows:
            path = EXPORT_DIR / "vehicle_attributes.csv"
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "vehicle_id", "make", "model", "model_year", "body_class",
                    "drive_type", "fuel_type", "engine_displacement_l",
                    "engine_cylinders", "transmission_type",
                    "electrification_level", "plant_country", "quality_score",
                ])
                for r in rows:
                    writer.writerow([
                        r["vehicle_id"], r["make"], r["model"], r["model_year"],
                        r["body_class"], r["drive_type"], r["fuel_type"],
                        r["engine_displacement_l"], r["engine_cylinders"],
                        r["transmission_type"], r["electrification_level"],
                        r["plant_country"], r["quality_score"],
                    ])
            print(f"  CSV: {len(rows)} vehicle attributes -> vehicle_attributes.csv")
    except Exception:
        pass

    # Investigation dockets
    try:
        rows = conn.execute("""
            SELECT * FROM investigation_dockets ORDER BY investigation_number
        """).fetchall()
        if rows:
            path = EXPORT_DIR / "investigation_dockets.csv"
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "docket_id", "investigation_number", "docket_type",
                    "title", "document_count", "last_modified", "quality_score",
                ])
                for r in rows:
                    writer.writerow([
                        r["docket_id"], r["investigation_number"], r["docket_type"],
                        r["title"], r["document_count"], r["last_modified"],
                        r["quality_score"],
                    ])
            print(f"  CSV: {len(rows)} investigation dockets -> investigation_dockets.csv")
    except Exception:
        pass


def _export_json(conn) -> None:
    """Export all data as JSON."""
    complaints = conn.execute("SELECT * FROM complaints ORDER BY date_complaint_filed DESC").fetchall()
    recalls = conn.execute("SELECT * FROM recalls ORDER BY report_received_date DESC").fetchall()
    investigations = conn.execute("SELECT * FROM investigations ORDER BY open_date DESC").fetchall()
    cross_links = conn.execute("SELECT * FROM cross_links").fetchall()

    # Manufacturer profiles (if available)
    try:
        mfr_profiles = conn.execute("SELECT * FROM manufacturer_profiles ORDER BY risk_score DESC").fetchall()
    except Exception:
        mfr_profiles = []

    data = {
        "generated": datetime.now().isoformat(),
        "complaints": [dict(r) for r in complaints],
        "recalls": [dict(r) for r in recalls],
        "investigations": [dict(r) for r in investigations],
        "cross_links": [dict(r) for r in cross_links],
        "manufacturer_profiles": [dict(r) for r in mfr_profiles],
    }

    path = EXPORT_DIR / "nhtsa_safety.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    total = len(complaints) + len(recalls) + len(investigations)
    print(f"  JSON: {total} records -> nhtsa_safety.json")


def _export_excel(conn) -> None:
    """Export to styled Excel workbook."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0984E3", end_color="0984E3", fill_type="solid")

    def style_headers(ws):
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill

    # Complaints sheet
    ws = wb.active
    ws.title = "Complaints"
    headers = ["ODI #", "Manufacturer", "Make", "Model", "Year",
               "Crash", "Fire", "Injuries", "Deaths",
               "Incident Date", "Filed Date", "Components", "Summary"]
    ws.append(headers)
    rows = conn.execute("SELECT * FROM complaints ORDER BY date_complaint_filed DESC LIMIT 100000").fetchall()
    for r in rows:
        ws.append([
            r["odi_number"], r["manufacturer"], r["make"], r["model"],
            r["model_year"], r["crash"], r["fire"],
            r["num_injuries"], r["num_deaths"],
            r["date_of_incident"], r["date_complaint_filed"],
            r["components"], r["summary"][:200],
        ])
    style_headers(ws)

    # Recalls sheet
    ws = wb.create_sheet("Recalls")
    headers = ["Campaign #", "Manufacturer", "Make", "Model", "Year",
               "Date", "Component", "Summary", "Consequence", "Remedy", "Affected"]
    ws.append(headers)
    rows = conn.execute("SELECT * FROM recalls ORDER BY report_received_date DESC").fetchall()
    for r in rows:
        ws.append([
            r["campaign_number"], r["manufacturer"], r["make"], r["model"],
            r["model_year"], r["report_received_date"], r["component"],
            r["summary"][:200], r["consequence"][:200], r["remedy"][:200],
            r["num_potentially_affected"],
        ])
    style_headers(ws)

    # Investigations sheet
    ws = wb.create_sheet("Investigations")
    headers = ["Investigation #", "Make", "Model", "Year Start", "Year End",
               "Type", "Status", "Open Date", "Subject"]
    ws.append(headers)
    rows = conn.execute("SELECT * FROM investigations ORDER BY open_date DESC").fetchall()
    for r in rows:
        ws.append([
            r["investigation_number"], r["make"], r["model"],
            r["model_year_start"], r["model_year_end"],
            r["investigation_type"], r["status"], r["open_date"],
            r["subject"][:200],
        ])
    style_headers(ws)

    # Manufacturer Profiles sheet
    try:
        rows = conn.execute("""
            SELECT * FROM manufacturer_profiles ORDER BY risk_score DESC
        """).fetchall()
        if rows:
            ws = wb.create_sheet("Manufacturer Risk")
            headers = ["Manufacturer", "Risk Tier", "Risk Score", "Severity Index",
                       "Complaints", "Recalls", "Deaths", "Injuries", "Fires", "Trend"]
            ws.append(headers)
            for r in rows:
                ws.append([
                    r["manufacturer_name"], r["risk_tier"],
                    round(r["risk_score"] or 0, 4),
                    round(r["severity_index"] or 0, 4),
                    r["total_complaints"], r["total_recalls"],
                    r["total_deaths"], r["total_injuries"], r["total_fires"],
                    r["complaint_trend"],
                ])
            style_headers(ws)
    except Exception:
        pass

    path = EXPORT_DIR / "nhtsa_safety.xlsx"
    wb.save(path)
    print(f"  Excel: saved nhtsa_safety.xlsx")


def _export_markdown(conn) -> None:
    """Export summary statistics as Markdown."""
    from src.storage.database import get_stats
    s = get_stats(conn)

    lines = [
        "# NHTSA Vehicle Safety Defect Tracker — Summary",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "**Built by:** Nathan Goldberg | nathanmauricegoldberg@gmail.com",
        "",
        "## Overview",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Complaints | {s['complaint_count']:,} |",
        f"| Recalls | {s['recall_count']:,} |",
        f"| Investigations | {s['investigation_count']:,} |",
        f"| Cross-Links | {s['cross_link_count']:,} |",
        f"| Unique Vehicles | {s['vehicle_count']:,} |",
        f"| Crashes Reported | {s['crash_count']:,} |",
        f"| Fires Reported | {s['fire_count']:,} |",
        f"| Total Injuries | {s['injury_total']:,} |",
        f"| Total Deaths | {s['death_total']:,} |",
        f"| Potentially Affected (Recalls) | {s['affected_total']:,} |",
        "",
        "## Top 10 Makes by Complaints",
        "",
        "| Make | Complaints |",
        "|------|-----------|",
    ]
    for make, cnt in s["top_makes"]:
        lines.append(f"| {make} | {cnt:,} |")

    lines.extend(["", "## Top 10 Components", "", "| Component | Complaints |", "|-----------|-----------|"])
    for comp, cnt in s["top_components"]:
        lines.append(f"| {comp} | {cnt:,} |")

    # Manufacturer risk profiles
    try:
        risk_rows = conn.execute("""
            SELECT manufacturer_name, risk_tier, risk_score, total_complaints,
                   total_deaths, severity_index
            FROM manufacturer_profiles
            WHERE total_complaints >= 50
            ORDER BY risk_score DESC LIMIT 10
        """).fetchall()
        if risk_rows:
            lines.extend([
                "", "## Top 10 Highest Risk Manufacturers", "",
                "| Manufacturer | Risk Tier | Risk Score | Complaints | Deaths | Severity |",
                "|-------------|-----------|------------|------------|--------|----------|",
            ])
            for r in risk_rows:
                lines.append(
                    f"| {r['manufacturer_name']} | {r['risk_tier']} | "
                    f"{r['risk_score']:.4f} | {r['total_complaints']:,} | "
                    f"{r['total_deaths']} | {r['severity_index']:.4f} |"
                )
    except Exception:
        pass

    path = EXPORT_DIR / "summary.md"
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Markdown: summary -> summary.md")
