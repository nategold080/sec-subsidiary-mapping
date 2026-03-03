"""Export SEC subsidiary data to CSV, JSON, Excel, and Markdown.

Generates clean export files from the SQLite database.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXPORT_DIR = PROJECT_ROOT / "data" / "exports"


def export_all(fmt: str = "all"):
    """Export all data in specified format(s)."""
    from src.storage.database import get_connection

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    if fmt in ("csv", "all"):
        _export_csv(conn)
    if fmt in ("json", "all"):
        _export_json(conn)
    if fmt in ("excel", "all"):
        _export_excel(conn)
    if fmt in ("all",):
        _export_markdown_summary(conn)

    conn.close()
    console.print(f"[green]Exports saved to {EXPORT_DIR}[/green]")


def _export_csv(conn):
    """Export to CSV files."""
    # Subsidiaries with parent info
    rows = conn.execute("""
        SELECT
            p.company_name AS parent_company,
            p.ticker AS parent_ticker,
            p.cik AS parent_cik,
            p.sic_code,
            s.name AS subsidiary_name,
            s.jurisdiction_raw,
            s.jurisdiction_code,
            s.jurisdiction_name,
            s.jurisdiction_country,
            s.is_tax_haven,
            ol.ownership_pct,
            ol.filing_date,
            ol.filing_accession,
            ol.source_url,
            ol.quality_score
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        ORDER BY p.company_name, s.name
    """).fetchall()

    path = EXPORT_DIR / "subsidiaries.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "parent_company", "parent_ticker", "parent_cik", "sic_code",
            "subsidiary_name", "jurisdiction_raw", "jurisdiction_code",
            "jurisdiction_name", "jurisdiction_country", "is_tax_haven",
            "ownership_pct", "filing_date", "filing_accession",
            "source_url", "quality_score",
        ])
        for row in rows:
            writer.writerow(list(row))

    console.print(f"  CSV: {len(rows)} records -> {path.name}")

    # Parents summary
    rows = conn.execute("""
        SELECT
            p.cik, p.company_name, p.ticker, p.sic_code, p.sic_description,
            p.exchange, p.state_of_incorporation,
            COUNT(DISTINCT ol.subsidiary_id) AS subsidiary_count,
            SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) AS tax_haven_count,
            COUNT(DISTINCT s.jurisdiction_code) AS jurisdiction_count,
            MIN(ol.filing_date) AS earliest_filing,
            MAX(ol.filing_date) AS latest_filing
        FROM parents p
        LEFT JOIN ownership_links ol ON ol.parent_cik = p.cik
        LEFT JOIN subsidiaries s ON s.id = ol.subsidiary_id
        GROUP BY p.cik
        ORDER BY subsidiary_count DESC
    """).fetchall()

    path = EXPORT_DIR / "parent_companies.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "cik", "company_name", "ticker", "sic_code", "sic_description",
            "exchange", "state_of_incorporation", "subsidiary_count",
            "tax_haven_count", "jurisdiction_count", "earliest_filing",
            "latest_filing",
        ])
        for row in rows:
            writer.writerow(list(row))

    console.print(f"  CSV: {len(rows)} parents -> {path.name}")


def _export_json(conn):
    """Export to JSON."""
    rows = conn.execute("""
        SELECT
            p.company_name AS parent_company,
            p.ticker AS parent_ticker,
            p.cik AS parent_cik,
            s.name AS subsidiary_name,
            s.jurisdiction_code,
            s.jurisdiction_name,
            s.is_tax_haven,
            ol.ownership_pct,
            ol.filing_date,
            ol.quality_score
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        ORDER BY p.company_name, s.name
    """).fetchall()

    data = [dict(row) for row in rows]
    path = EXPORT_DIR / "subsidiaries.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    console.print(f"  JSON: {len(data)} records -> {path.name}")


def _export_excel(conn):
    """Export to styled Excel workbook."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        console.print("[yellow]openpyxl not installed, skipping Excel export[/yellow]")
        return

    wb = Workbook()

    # Sheet 1: Subsidiaries
    ws = wb.active
    ws.title = "Subsidiaries"

    headers = [
        "Parent Company", "Ticker", "CIK", "Subsidiary Name",
        "Jurisdiction", "Country", "Tax Haven", "Ownership %",
        "Filing Date", "Quality Score",
    ]

    header_fill = PatternFill(start_color="0984E3", end_color="0984E3", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font

    rows = conn.execute("""
        SELECT
            p.company_name, p.ticker, p.cik,
            s.name, s.jurisdiction_name, s.jurisdiction_country,
            s.is_tax_haven, ol.ownership_pct, ol.filing_date, ol.quality_score
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        ORDER BY p.company_name, s.name
    """).fetchall()

    for row_idx, row in enumerate(rows, 2):
        for col_idx, value in enumerate(list(row), 1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Auto-fit columns
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    path = EXPORT_DIR / "sec_subsidiaries.xlsx"
    wb.save(path)
    console.print(f"  Excel: {len(rows)} records -> {path.name}")


def _export_markdown_summary(conn):
    """Export summary statistics as Markdown."""
    from src.storage.database import get_stats
    stats = get_stats(conn)

    # Top jurisdictions
    juris_rows = conn.execute("""
        SELECT jurisdiction_code, jurisdiction_name, jurisdiction_country,
               COUNT(*) as cnt,
               SUM(CASE WHEN is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_cnt
        FROM subsidiaries
        WHERE jurisdiction_code != ''
        GROUP BY jurisdiction_code
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()

    # Top companies
    company_rows = conn.execute("""
        SELECT p.company_name, p.ticker, COUNT(DISTINCT ol.subsidiary_id) as cnt,
               SUM(CASE WHEN s.is_tax_haven = 1 THEN 1 ELSE 0 END) as haven_cnt
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        JOIN subsidiaries s ON s.id = ol.subsidiary_id
        GROUP BY ol.parent_cik
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()

    md = f"""# SEC Corporate Subsidiary & Ownership Mapping — Summary

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Built by:** Nathan Goldberg | nathanmauricegoldberg@gmail.com

## Overview

| Metric | Value |
|--------|-------|
| Parent Companies | {stats['parent_count']:,} |
| Unique Subsidiaries | {stats['subsidiary_count']:,} |
| Ownership Links | {stats['link_count']:,} |
| Filings Processed | {stats['filing_count']:,} |
| Tax Haven Entities | {stats['tax_haven_count']:,} |
| Jurisdictions | {stats['jurisdiction_count']:,} |
| Avg Quality Score | {stats['avg_quality']:.3f} |
| Date Range | {stats['date_range'][0] or 'N/A'} to {stats['date_range'][1] or 'N/A'} |

## Top 20 Jurisdictions

| Jurisdiction | Count | Tax Haven |
|-------------|-------|-----------|
"""

    for row in juris_rows:
        haven = "Yes" if row["haven_cnt"] > 0 else ""
        md += f"| {row['jurisdiction_name']} ({row['jurisdiction_code']}) | {row['cnt']:,} | {haven} |\n"

    md += """
## Top 20 Companies by Subsidiary Count

| Company | Ticker | Subsidiaries | Tax Haven Subs |
|---------|--------|-------------|----------------|
"""

    for row in company_rows:
        ticker = row["ticker"] or ""
        md += f"| {row['company_name']} | {ticker} | {row['cnt']:,} | {row['haven_cnt']:,} |\n"

    path = EXPORT_DIR / "summary.md"
    with open(path, "w") as f:
        f.write(md)

    console.print(f"  Markdown: summary -> {path.name}")
