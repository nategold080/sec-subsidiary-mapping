"""CLI for SEC Subsidiary Mapping.

Commands:
  discover  - Find 10-K filings with Exhibit 21
  fetch     - Download raw Exhibit 21 HTML files
  parse     - Parse exhibits and extract subsidiaries
  pipeline  - Run full discover -> fetch -> parse -> store pipeline
  stats     - Show database statistics
  export    - Export data to CSV/JSON/Excel
  dashboard - Launch Streamlit dashboard
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent


@click.group()
def cli():
    """SEC Corporate Subsidiary & Ownership Mapping."""
    pass


@cli.command()
@click.option("--start-date", default="2023-01-01", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--max-filings", default=5000, help="Maximum filings to discover")
@click.option("--force", is_flag=True, help="Re-discover even if cached")
def discover(start_date, end_date, max_filings, force):
    """Discover 10-K filings with Exhibit 21."""
    from src.scrapers.edgar_search import discover_filings
    filings = discover_filings(start_date, end_date, max_filings, force)
    console.print(f"\n[bold green]Discovered {len(filings)} filings[/bold green]")


@cli.command()
@click.option("--start-date", default="2023-01-01", help="Start date")
@click.option("--end-date", default=None, help="End date")
@click.option("--max-fetch", default=None, type=int, help="Max exhibits to fetch")
def fetch(start_date, end_date, max_fetch):
    """Download raw Exhibit 21 HTML files."""
    from src.scrapers.edgar_search import discover_filings, fetch_exhibits_batch
    filings = discover_filings(start_date, end_date)
    results = fetch_exhibits_batch(filings, max_fetch)
    console.print(f"\n[bold green]Fetched {len(results)} exhibits[/bold green]")


@cli.command()
@click.option("--start-date", default="2023-01-01", help="Start date")
@click.option("--end-date", default=None, help="End date")
@click.option("--max-parse", default=None, type=int, help="Max exhibits to parse")
def parse(start_date, end_date, max_parse):
    """Parse fetched exhibits and extract subsidiaries."""
    from src.scrapers.edgar_search import discover_filings, fetch_exhibit
    from src.extractors.exhibit21_parser import parse_exhibit21
    from src.normalization.jurisdictions import normalize_jurisdiction

    filings = discover_filings(start_date, end_date)
    if max_parse:
        filings = filings[:max_parse]

    total_subs = 0
    parsed = 0
    failed = 0

    for filing in filings:
        content = fetch_exhibit(filing)
        if not content:
            failed += 1
            continue

        result = parse_exhibit21(content)
        if result.subsidiaries:
            parsed += 1
            total_subs += len(result.subsidiaries)
            # Normalize jurisdictions
            for sub in result.subsidiaries:
                norm = normalize_jurisdiction(sub.jurisdiction_raw)
                if norm:
                    sub.jurisdiction_raw = f"{sub.jurisdiction_raw} -> {norm.code}"
        else:
            failed += 1

    console.print(f"\n[bold green]Parsed {parsed} exhibits, {total_subs} subsidiaries[/bold green]")
    if failed:
        console.print(f"[yellow]Failed to parse: {failed}[/yellow]")


@cli.command()
@click.option("--start-date", default="2023-01-01", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--max-filings", default=5000, help="Maximum filings to process")
@click.option("--force", is_flag=True, help="Force re-discovery and re-fetch")
def pipeline(start_date, end_date, max_filings, force):
    """Run full pipeline: discover -> fetch -> parse -> store."""
    from src.scrapers.edgar_search import (
        discover_filings, fetch_exhibit, fetch_company_info,
    )
    from src.extractors.exhibit21_parser import parse_exhibit21
    from src.normalization.jurisdictions import normalize_jurisdiction
    from src.validation.quality import score_subsidiary
    from src.storage.database import (
        get_connection, init_db, upsert_parent, upsert_filing,
        insert_subsidiary, insert_ownership_link, get_stats,
    )

    import httpx

    console.print("[bold cyan]SEC Subsidiary Mapping Pipeline[/bold cyan]")
    console.print(f"Date range: {start_date} to {end_date or 'today'}")
    console.print()

    # Step 1: Discover filings
    console.print("[bold]Step 1: Discovering filings...[/bold]")
    filings = discover_filings(start_date, end_date, max_filings, force)
    console.print(f"  {len(filings)} filings discovered")

    # Step 2: Initialize database
    console.print("[bold]Step 2: Initializing database...[/bold]")
    conn = get_connection()
    init_db(conn)

    # Step 3: Process each filing
    console.print(f"[bold]Step 3: Processing {len(filings)} filings...[/bold]")

    total_subs = 0
    parsed_count = 0
    failed_count = 0
    company_info_cache = {}

    headers = {
        "User-Agent": "DataFactory/1.0 (SEC-Subsidiary-Mapping; research; nathanmauricegoldberg@gmail.com)",
        "Accept": "text/html,application/xhtml+xml,*/*",
    }

    with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
        for i, filing in enumerate(filings):
            if (i + 1) % 50 == 0 or i == 0:
                console.print(
                    f"[dim]  Processing {i + 1}/{len(filings)} "
                    f"({parsed_count} parsed, {total_subs} subsidiaries)...[/dim]"
                )

            # Upsert parent company
            cik = filing["cik"]
            if cik not in company_info_cache:
                upsert_parent(conn, {
                    "cik": cik,
                    "company_name": filing["company_name"],
                    "ticker": filing.get("ticker", ""),
                })
                company_info_cache[cik] = True

            # Fetch exhibit
            content = fetch_exhibit(filing, client=client)
            if not content:
                upsert_filing(conn, {
                    **filing,
                    "parse_error": "fetch_failed",
                    "subsidiary_count": 0,
                })
                failed_count += 1
                time.sleep(0.12)
                continue

            # Parse exhibit
            result = parse_exhibit21(content)

            upsert_filing(conn, {
                **filing,
                "parse_method": result.parse_method,
                "subsidiary_count": len(result.subsidiaries),
                "raw_text_length": result.raw_text_length,
                "parse_error": result.error,
            })

            if not result.subsidiaries:
                failed_count += 1
                continue

            parsed_count += 1

            # Process each subsidiary
            for sub in result.subsidiaries:
                # Normalize jurisdiction
                norm = normalize_jurisdiction(sub.jurisdiction_raw)

                sub_record = {
                    "name": sub.name,
                    "name_normalized": _normalize_name(sub.name),
                    "jurisdiction_raw": sub.jurisdiction_raw,
                    "jurisdiction_code": norm.code if norm else "",
                    "jurisdiction_name": norm.name if norm else "",
                    "jurisdiction_country": norm.country if norm else "",
                    "is_tax_haven": norm.is_tax_haven if norm else False,
                }

                sub_id = insert_subsidiary(conn, sub_record)

                # Quality score
                quality_record = {
                    "subsidiary_name": sub.name,
                    "jurisdiction_raw": sub.jurisdiction_raw,
                    "jurisdiction_code": norm.code if norm else "",
                    "parent_cik": cik,
                    "filing_date": filing.get("file_date", ""),
                    "ownership_pct": sub.ownership_pct,
                    "source_url": filing.get("exhibit_url", ""),
                }
                qs = score_subsidiary(quality_record)

                # Insert ownership link
                insert_ownership_link(conn, {
                    "parent_cik": cik,
                    "subsidiary_id": sub_id,
                    "filing_accession": filing["accession"],
                    "filing_date": filing.get("file_date", ""),
                    "ownership_pct": sub.ownership_pct,
                    "source_url": filing.get("exhibit_url", ""),
                    "quality_score": qs.score,
                    "quality_components": qs.components,
                })

                total_subs += 1

            # Commit every 10 filings
            if (i + 1) % 10 == 0:
                conn.commit()

            time.sleep(0.12)

    conn.commit()

    # Print summary
    stats = get_stats(conn)
    conn.close()

    console.print()
    console.print("[bold green]Pipeline Complete![/bold green]")
    console.print(f"  Parent companies: {stats['parent_count']}")
    console.print(f"  Filings processed: {stats['filing_count']}")
    console.print(f"  Subsidiaries: {stats['subsidiary_count']}")
    console.print(f"  Ownership links: {stats['link_count']}")
    console.print(f"  Tax haven entities: {stats['tax_haven_count']}")
    console.print(f"  Jurisdictions: {stats['jurisdiction_count']}")
    console.print(f"  Avg quality: {stats['avg_quality']:.3f}")
    console.print(f"  Date range: {stats['date_range'][0]} to {stats['date_range'][1]}")
    console.print(f"  Parse success: {parsed_count}/{len(filings)}")
    console.print(f"  Parse failures: {failed_count}")


@cli.command()
def stats():
    """Show database statistics."""
    from src.storage.database import get_connection, get_stats

    conn = get_connection()
    s = get_stats(conn)

    table = Table(title="SEC Subsidiary Mapping Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Parent Companies", f"{s['parent_count']:,}")
    table.add_row("Filings Processed", f"{s['filing_count']:,}")
    table.add_row("Unique Subsidiaries", f"{s['subsidiary_count']:,}")
    table.add_row("Ownership Links", f"{s['link_count']:,}")
    table.add_row("Tax Haven Entities", f"{s['tax_haven_count']:,}")
    table.add_row("Jurisdictions", f"{s['jurisdiction_count']:,}")
    table.add_row("Avg Quality Score", f"{s['avg_quality']:.3f}")
    if s["date_range"][0]:
        table.add_row("Date Range", f"{s['date_range'][0]} to {s['date_range'][1]}")

    # Top jurisdictions
    rows = conn.execute("""
        SELECT jurisdiction_code, jurisdiction_name, COUNT(*) as cnt
        FROM subsidiaries
        WHERE jurisdiction_code != ''
        GROUP BY jurisdiction_code
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()

    if rows:
        table.add_row("", "")
        table.add_row("[bold]Top Jurisdictions[/bold]", "")
        for row in rows:
            table.add_row(f"  {row['jurisdiction_code']} ({row['jurisdiction_name']})", f"{row['cnt']:,}")

    # Top parent companies by subsidiary count
    rows = conn.execute("""
        SELECT p.company_name, p.ticker, COUNT(*) as cnt
        FROM ownership_links ol
        JOIN parents p ON p.cik = ol.parent_cik
        GROUP BY ol.parent_cik
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchall()

    if rows:
        table.add_row("", "")
        table.add_row("[bold]Top Companies by Subsidiaries[/bold]", "")
        for row in rows:
            name = row["company_name"]
            if row["ticker"]:
                name += f" ({row['ticker']})"
            table.add_row(f"  {name}", f"{row['cnt']:,}")

    conn.close()
    console.print(table)


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "excel", "all"]), default="all")
def export(fmt):
    """Export data to CSV/JSON/Excel."""
    from src.export.exporter import export_all
    export_all(fmt)


@cli.command()
@click.option("--port", default=8501, help="Streamlit port")
def dashboard(port):
    """Launch Streamlit dashboard."""
    import subprocess
    app_path = PROJECT_ROOT / "src" / "dashboard" / "app.py"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(port),
        "--server.headless", "true",
    ])


def _normalize_name(name: str) -> str:
    """Normalize a subsidiary name for deduplication."""
    n = name.strip().upper()
    # Remove common suffixes
    for suffix in [
        ", INC.", " INC.", " INC", ", LLC", " LLC", ", LTD.", " LTD.",
        " LTD", ", L.L.C.", " L.L.C.", ", L.P.", " L.P.", ", LP", " LP",
        " CORP.", " CORP", " CORPORATION", " COMPANY", " CO.", " CO",
        " LIMITED", " GMBH", " S.A.", " S.A", " B.V.", " B.V",
        " N.V.", " N.V", " PTE.", " PTE", " PTY.", " PTY",
        " S.R.L.", " S.R.L", " AG", " PLC", " S.A.S.", " S.A.S",
        " S.P.A.", " S.P.A", " A.S.", " A.S", " AB", " OY",
        " K.K.", " K.K",
    ]:
        if n.endswith(suffix):
            n = n[:-len(suffix)]

    # Normalize common abbreviations
    n = n.replace("&", "AND")
    n = re.sub(r"\s+", " ", n).strip()
    return n


if __name__ == "__main__":
    cli()
