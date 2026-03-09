"""
Export module for CFPB Consumer Complaint Cross-Linked Analysis.

Generates CSV, JSON, Excel, and Markdown exports of the cross-linked dataset.
Supports filtering by quality score threshold.

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

DEFAULT_EXPORT_DIR = Path(__file__).parent.parent.parent / "data" / "exports"

# ---------------------------------------------------------------------------
# Data Retrieval Helpers
# ---------------------------------------------------------------------------

def _get_institutions_with_details(
    db_conn,
    min_quality: float = 0.0,
) -> list[dict]:
    """
    Retrieve institutions with aggregated complaint counts, CRA ratings,
    and enforcement action summaries for export.

    Args:
        db_conn: Active database connection.
        min_quality: Minimum quality score filter (0.0-1.0).

    Returns:
        List of dicts with full institution details for export.
    """
    query = """
        SELECT
            fi.cert_number,
            fi.institution_name,
            fi.canonical_name,
            fi.city,
            fi.state,
            fi.total_assets,
            fi.institution_class,
            fi.regulator,
            fi.active,
            fi.established_date,
            fi.quality_score,
            COALESCE(ic_agg.complaint_count, 0) as complaint_count,
            cra_latest.cra_rating as latest_cra_rating,
            cra_latest.exam_date as cra_exam_date,
            COALESCE(ea_agg.enforcement_count, 0) as enforcement_count,
            COALESCE(ea_agg.total_penalties, 0) as total_penalties
        FROM financial_institutions fi
        LEFT JOIN (
            SELECT cert_number, COUNT(*) as complaint_count
            FROM institution_complaints
            GROUP BY cert_number
        ) ic_agg ON fi.cert_number = ic_agg.cert_number
        LEFT JOIN (
            SELECT cert_number, cra_rating, exam_date,
                   ROW_NUMBER() OVER (PARTITION BY cert_number ORDER BY exam_date DESC) as rn
            FROM cra_ratings
        ) cra_latest ON fi.cert_number = cra_latest.cert_number AND cra_latest.rn = 1
        LEFT JOIN (
            SELECT institution_cert, COUNT(*) as enforcement_count,
                   SUM(COALESCE(penalty_amount, 0)) as total_penalties
            FROM enforcement_actions
            WHERE institution_cert IS NOT NULL
            GROUP BY institution_cert
        ) ea_agg ON fi.cert_number = ea_agg.institution_cert
        WHERE fi.quality_score >= ?
        ORDER BY COALESCE(ic_agg.complaint_count, 0) DESC
    """

    cursor = db_conn.execute(query, (min_quality,))
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def _get_export_timestamp() -> str:
    """Return current UTC timestamp formatted for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

def export_csv(
    db_conn,
    output_dir: Optional[Path] = None,
    min_quality: float = 0.0,
) -> Path:
    """
    Export the cross-linked dataset as a CSV file.

    Args:
        db_conn: Active database connection.
        output_dir: Output directory. Defaults to data/exports/.
        min_quality: Minimum quality score filter.

    Returns:
        Path to the generated CSV file.
    """
    if output_dir is None:
        output_dir = DEFAULT_EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _get_export_timestamp()
    filepath = output_dir / f"cfpb_institutions_{timestamp}.csv"

    console.print(f"  Exporting CSV to {filepath}...")

    records = _get_institutions_with_details(db_conn, min_quality)

    if not records:
        console.print("  [yellow]No records to export.[/yellow]")
        return filepath

    fieldnames = list(records[0].keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    console.print(f"  Exported {len(records)} records to CSV.")
    return filepath


# ---------------------------------------------------------------------------
# JSON Export
# ---------------------------------------------------------------------------

def export_json(
    db_conn,
    output_dir: Optional[Path] = None,
    min_quality: float = 0.0,
    indent: int = 2,
) -> Path:
    """
    Export the cross-linked dataset as a JSON file.

    Args:
        db_conn: Active database connection.
        output_dir: Output directory. Defaults to data/exports/.
        min_quality: Minimum quality score filter.
        indent: JSON indentation level.

    Returns:
        Path to the generated JSON file.
    """
    if output_dir is None:
        output_dir = DEFAULT_EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _get_export_timestamp()
    filepath = output_dir / f"cfpb_institutions_{timestamp}.json"

    console.print(f"  Exporting JSON to {filepath}...")

    records = _get_institutions_with_details(db_conn, min_quality)

    export_data = {
        "metadata": {
            "project": "CFPB Consumer Complaint Cross-Linked Analysis",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "min_quality_filter": min_quality,
            "contact": "Nathan Goldberg | nathanmauricegoldberg@gmail.com",
        },
        "institutions": records,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=indent, default=str)

    console.print(f"  Exported {len(records)} records to JSON.")
    return filepath


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------

def export_excel(
    db_conn,
    output_dir: Optional[Path] = None,
    min_quality: float = 0.0,
) -> Path:
    """
    Export the cross-linked dataset as a styled Excel (.xlsx) file.

    Uses openpyxl for formatting: header styling, column widths,
    number formatting, and conditional formatting for quality scores.

    Args:
        db_conn: Active database connection.
        output_dir: Output directory. Defaults to data/exports/.
        min_quality: Minimum quality score filter.

    Returns:
        Path to the generated Excel file.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, numbers
    except ImportError:
        console.print(
            "  [yellow]openpyxl is not installed — skipping Excel export. "
            "Install with: pip install openpyxl[/yellow]"
        )
        if output_dir is None:
            output_dir = DEFAULT_EXPORT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"cfpb_institutions_{_get_export_timestamp()}.xlsx"
        return filepath

    if output_dir is None:
        output_dir = DEFAULT_EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _get_export_timestamp()
    filepath = output_dir / f"cfpb_institutions_{timestamp}.xlsx"

    console.print(f"  Exporting Excel to {filepath}...")

    records = _get_institutions_with_details(db_conn, min_quality)

    if not records:
        console.print("  [yellow]No records to export.[/yellow]")
        return filepath

    wb = Workbook()
    ws = wb.active
    ws.title = "Institutions"

    # Header styling
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="0984E3", end_color="0984E3", fill_type="solid")

    # Write headers
    headers = list(records[0].keys())
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Write data rows
    for row_idx, record in enumerate(records, 2):
        for col_idx, header in enumerate(headers, 1):
            value = record.get(header)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)

            # Format numeric columns
            if header in ("total_assets", "total_penalties"):
                if value is not None:
                    cell.number_format = '#,##0'
            elif header == "quality_score":
                if value is not None:
                    cell.number_format = '0.0000'

    # Auto-fit column widths (approximate)
    for col_idx, header in enumerate(headers, 1):
        max_len = max(
            len(str(header)),
            max((len(str(record.get(header, ""))) for record in records[:100]), default=10),
        )
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(
            max_len + 2, 50
        )

    # Add metadata sheet
    meta_ws = wb.create_sheet("Metadata")
    meta_ws["A1"] = "CFPB Consumer Complaint Cross-Linked Analysis"
    meta_ws["A1"].font = Font(bold=True, size=14)
    meta_ws["A3"] = "Exported:"
    meta_ws["B3"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta_ws["A4"] = "Records:"
    meta_ws["B4"] = len(records)
    meta_ws["A5"] = "Min Quality Filter:"
    meta_ws["B5"] = min_quality
    meta_ws["A7"] = "Contact:"
    meta_ws["B7"] = "Nathan Goldberg"
    meta_ws["A8"] = "Email:"
    meta_ws["B8"] = "nathanmauricegoldberg@gmail.com"
    meta_ws["A9"] = "LinkedIn:"
    meta_ws["B9"] = "linkedin.com/in/nathangoldberg"

    wb.save(filepath)
    console.print(f"  Exported {len(records)} records to Excel.")
    return filepath


# ---------------------------------------------------------------------------
# Markdown Export
# ---------------------------------------------------------------------------

def export_markdown(
    db_conn,
    output_dir: Optional[Path] = None,
    min_quality: float = 0.0,
    top_n: int = 25,
) -> Path:
    """
    Export a Markdown summary report of the cross-linked dataset.

    Includes summary statistics, top institutions by complaint volume,
    and quality score distribution.

    Args:
        db_conn: Active database connection.
        output_dir: Output directory. Defaults to data/exports/.
        min_quality: Minimum quality score filter.
        top_n: Number of top institutions to include in tables.

    Returns:
        Path to the generated Markdown file.
    """
    if output_dir is None:
        output_dir = DEFAULT_EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = _get_export_timestamp()
    filepath = output_dir / f"cfpb_summary_{timestamp}.md"

    console.print(f"  Exporting Markdown to {filepath}...")

    from src.storage.database import get_stats
    stats = get_stats(db_conn)
    records = _get_institutions_with_details(db_conn, min_quality)

    # Guard against None/missing values in stats
    total_complaints = stats.get("total_complaints") or 0
    total_institutions = stats.get("total_institutions") or 0
    total_cra_ratings = stats.get("total_cra_ratings") or 0
    total_enforcement_actions = stats.get("total_enforcement_actions") or 0
    total_cross_links = stats.get("total_cross_links") or 0
    avg_match_confidence = stats.get("avg_match_confidence") or 0.0
    avg_quality_score = stats.get("avg_quality_score") or 0.0

    lines = [
        "# CFPB Consumer Complaint Cross-Linked Analysis - Summary Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Contact:** Nathan Goldberg | nathanmauricegoldberg@gmail.com | linkedin.com/in/nathangoldberg",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Complaints | {total_complaints:,} |",
        f"| Total Institutions | {total_institutions:,} |",
        f"| Total CRA Ratings | {total_cra_ratings:,} |",
        f"| Total Enforcement Actions | {total_enforcement_actions:,} |",
        f"| Cross-Links Created | {total_cross_links:,} |",
        f"| Avg Match Confidence | {avg_match_confidence:.2%} |",
        f"| Avg Quality Score | {avg_quality_score:.4f} |",
        "",
        "---",
        "",
    ]

    # Top institutions by complaint count
    if records:
        lines.extend([
            f"## Top {min(top_n, len(records))} Institutions by Complaint Volume",
            "",
            "| Rank | Institution | State | Complaints | CRA Rating | Enforcement Actions | Quality |",
            "|------|------------|-------|-----------|------------|-------------------|---------|",
        ])
        for i, rec in enumerate(records[:top_n], 1):
            lines.append(
                f"| {i} | {rec.get('institution_name', 'N/A')} | "
                f"{rec.get('state', 'N/A')} | "
                f"{rec.get('complaint_count', 0):,} | "
                f"{rec.get('latest_cra_rating', 'N/A')} | "
                f"{rec.get('enforcement_count', 0)} | "
                f"{rec.get('quality_score', 0):.2f} |"
            )
        lines.extend(["", "---", ""])

    # Top products by complaint count
    if stats.get("complaints_by_product"):
        lines.extend([
            "## Top Complaint Products",
            "",
            "| Product | Complaints |",
            "|---------|-----------|",
        ])
        for item in stats["complaints_by_product"]:
            lines.append(f"| {item.get('product', 'N/A')} | {item.get('count', 0):,} |")
        lines.extend(["", "---", ""])

    # Top states
    if stats.get("complaints_by_state"):
        lines.extend([
            "## Top States by Complaint Volume",
            "",
            "| State | Complaints |",
            "|-------|-----------|",
        ])
        for item in stats["complaints_by_state"]:
            lines.append(f"| {item.get('state', 'N/A')} | {item.get('count', 0):,} |")
        lines.extend([""])

    # Enrichment data summary
    total_financials = stats.get("total_financials", 0)
    total_reg_enforcement = stats.get("total_regulatory_enforcement", 0)
    total_risk_profiles = stats.get("total_risk_profiles", 0)
    total_hmda = stats.get("total_hmda_summaries", 0)

    if any([total_financials, total_reg_enforcement, total_risk_profiles, total_hmda]):
        lines.extend([
            "---",
            "",
            "## Enrichment Data",
            "",
            "| Dataset | Records |",
            "|---------|---------|",
            f"| Institution Financials | {total_financials:,} |",
            f"| Institutions w/ Financial Data | {stats.get('institutions_with_financials', 0):,} |",
            f"| Regulatory Enforcement (unified) | {total_reg_enforcement:,} |",
            f"| Institution Risk Profiles | {total_risk_profiles:,} |",
            f"| HMDA Lending Summaries | {total_hmda:,} |",
            "",
        ])

    if stats.get("enforcement_by_agency"):
        lines.extend([
            "### Enforcement Actions by Agency",
            "",
            "| Agency | Actions |",
            "|--------|---------|",
        ])
        for item in stats["enforcement_by_agency"]:
            lines.append(f"| {item.get('agency', 'N/A')} | {item.get('count', 0):,} |")
        lines.extend([""])

    if stats.get("risk_tier_distribution"):
        lines.extend([
            "### Risk Tier Distribution",
            "",
            "| Tier | Institutions |",
            "|------|-------------|",
        ])
        for item in stats["risk_tier_distribution"]:
            lines.append(f"| {item.get('risk_tier', 'N/A')} | {item.get('count', 0):,} |")
        lines.extend([""])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    console.print(f"  Exported Markdown summary.")
    return filepath


# ---------------------------------------------------------------------------
# Convenience: Export All
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Enrichment Exports
# ---------------------------------------------------------------------------

def _export_enrichment_csv(db_conn, output_dir: Path, table: str, filename: str, query: str) -> Optional[Path]:
    """Generic helper to export a query result as CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _get_export_timestamp()
    filepath = output_dir / f"{filename}_{timestamp}.csv"

    cursor = db_conn.execute(query)
    columns = [d[0] for d in cursor.description] if cursor.description else []
    rows = cursor.fetchall()

    if not rows:
        return None

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(zip(columns, row)))

    console.print(f"  Exported {len(rows)} {table} records to {filepath}")
    return filepath


def export_enrichment_data(db_conn, output_dir: Optional[Path] = None) -> dict[str, Optional[Path]]:
    """
    Export all enrichment data tables as separate CSVs.

    Returns:
        Dict of table name to file path.
    """
    if output_dir is None:
        output_dir = DEFAULT_EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # Institution financials
    results["institution_financials"] = _export_enrichment_csv(
        db_conn, output_dir, "financials", "institution_financials",
        "SELECT * FROM institution_financials ORDER BY cert_number, report_date DESC",
    )

    # Regulatory enforcement (unified)
    results["regulatory_enforcement"] = _export_enrichment_csv(
        db_conn, output_dir, "regulatory enforcement", "regulatory_enforcement",
        "SELECT * FROM regulatory_enforcement ORDER BY action_date DESC",
    )

    # Institution risk profiles
    results["institution_risk_profiles"] = _export_enrichment_csv(
        db_conn, output_dir, "risk profiles", "institution_risk_profiles",
        "SELECT * FROM institution_risk_profiles ORDER BY overall_risk_score ASC",
    )

    # HMDA summaries
    results["hmda_summaries"] = _export_enrichment_csv(
        db_conn, output_dir, "HMDA summaries", "hmda_summaries",
        "SELECT * FROM hmda_institution_summary ORDER BY report_year DESC, institution_name",
    )

    return results


def export_all(
    db_conn,
    output_dir: Optional[Path] = None,
    min_quality: float = 0.0,
) -> dict[str, Path]:
    """
    Run all export formats and return paths to generated files.

    Args:
        db_conn: Active database connection.
        output_dir: Output directory for all exports.
        min_quality: Minimum quality score filter.

    Returns:
        Dict mapping format name to output file path.
    """
    results = {}
    results["csv"] = export_csv(db_conn, output_dir, min_quality)
    results["json"] = export_json(db_conn, output_dir, min_quality)
    results["excel"] = export_excel(db_conn, output_dir, min_quality)
    results["markdown"] = export_markdown(db_conn, output_dir, min_quality)

    # Export enrichment data
    enrichment = export_enrichment_data(db_conn, output_dir)
    results.update({k: v for k, v in enrichment.items() if v is not None})

    return results


def run_export(
    db_conn,
    output_dir: Path,
    export_format: str = "all",
    min_quality: float = 0.0,
) -> dict[str, Path]:
    """
    Run exports based on format selection (CLI entry point).

    Args:
        db_conn: Active database connection.
        output_dir: Output directory.
        export_format: One of "csv", "json", "excel", "markdown", "all".
        min_quality: Minimum quality score filter.

    Returns:
        Dict of format name to output file path.
    """
    results = {}
    if export_format == "all":
        results = export_all(db_conn, output_dir, min_quality)
    elif export_format == "csv":
        results["csv"] = export_csv(db_conn, output_dir, min_quality)
    elif export_format == "json":
        results["json"] = export_json(db_conn, output_dir, min_quality)
    elif export_format == "excel":
        results["excel"] = export_excel(db_conn, output_dir, min_quality)
    elif export_format == "markdown":
        results["markdown"] = export_markdown(db_conn, output_dir, min_quality)

    for fmt, path in results.items():
        console.print(f"  [green]{fmt}: {path}[/green]")
    return results
