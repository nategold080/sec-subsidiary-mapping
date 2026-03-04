"""CLI for NHTSA Vehicle Safety Defect Tracker.

Commands:
  download    - Download NHTSA flat files (complaints, investigations)
  recalls     - Fetch recalls from NHTSA API
  pipeline    - Run full pipeline: download, parse, cross-link
  stats       - Show database statistics
  export      - Export data to CSV/JSON/Excel/Markdown
  dashboard   - Launch Streamlit dashboard
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent


@click.group()
def cli():
    """NHTSA Vehicle Safety Defect Tracker."""
    pass


@cli.command()
@click.option("--force", is_flag=True, help="Force re-download")
def download(force):
    """Download NHTSA flat files (complaints + investigations)."""
    from src.scrapers.complaints import download_complaints_flat_file
    from src.scrapers.investigations import download_investigations_flat_file

    console.print("[bold]Downloading NHTSA complaints flat file...[/bold]")
    path = download_complaints_flat_file(force)
    console.print(f"  [green]Saved to {path}[/green]")

    console.print("[bold]Downloading NHTSA investigations flat file...[/bold]")
    path = download_investigations_flat_file(force)
    console.print(f"  [green]Saved to {path}[/green]")


@cli.command()
@click.option("--years", default="2015-2026", help="Year range (e.g. 2020-2025)")
@click.option("--makes", default=None, help="Comma-separated makes (default: top 30)")
def recalls(years, makes):
    """Fetch recalls from NHTSA API for specified makes and years."""
    from src.scrapers.recalls import fetch_recalls_bulk
    from src.normalization.vehicles import MAJOR_MAKES

    start_year, end_year = (int(y) for y in years.split("-"))
    model_years = list(range(start_year, end_year + 1))

    if makes:
        make_list = [m.strip().upper() for m in makes.split(",")]
    else:
        make_list = MAJOR_MAKES

    console.print(f"[bold]Fetching recalls for {len(make_list)} makes, {len(model_years)} years...[/bold]")

    def progress(done, total, msg):
        if done % 10 == 0 or done == total:
            console.print(f"  [dim]{done}/{total}: {msg}[/dim]")

    results = fetch_recalls_bulk(make_list, model_years, progress_callback=progress)
    console.print(f"\n[bold green]Fetched {len(results)} unique recall campaigns[/bold green]")


@cli.command()
@click.option("--min-year", default=2015, help="Minimum model year for complaints")
@click.option("--max-complaints", default=None, type=int, help="Max complaints to process")
@click.option("--skip-download", is_flag=True, help="Skip flat file downloads")
@click.option("--skip-recalls", is_flag=True, help="Skip recall API fetching")
@click.option("--recall-years", default="2015-2026", help="Year range for recalls")
def pipeline(min_year, max_complaints, skip_download, skip_recalls, recall_years):
    """Run full pipeline: download -> parse -> store -> cross-link."""
    from src.scrapers.complaints import (
        download_complaints_flat_file, parse_complaints_flat_file,
    )
    from src.scrapers.investigations import (
        download_investigations_flat_file, parse_investigations_flat_file,
    )
    from src.scrapers.recalls import fetch_recalls_bulk
    from src.normalization.vehicles import normalize_make, normalize_model, MAJOR_MAKES
    from src.normalization.cross_linker import cross_link_all
    from src.validation.quality import score_complaint, score_recall, score_investigation
    from src.storage.database import (
        get_connection, init_db, upsert_complaint, upsert_recall,
        upsert_investigation, upsert_vehicle, get_stats,
    )

    console.print("[bold cyan]NHTSA Vehicle Safety Pipeline[/bold cyan]\n")

    conn = get_connection()
    init_db(conn)

    # Step 1: Download flat files
    if not skip_download:
        console.print("[bold]Step 1: Downloading flat files...[/bold]")
        download_complaints_flat_file()
        console.print("  Complaints flat file ready")
        download_investigations_flat_file()
        console.print("  Investigations flat file ready")
    else:
        console.print("[bold]Step 1: Skipping downloads (--skip-download)[/bold]")

    # Step 2: Parse and load complaints
    console.print(f"[bold]Step 2: Parsing complaints (min year {min_year})...[/bold]")
    complaints = parse_complaints_flat_file(min_year=min_year, max_records=max_complaints)
    console.print(f"  Parsed {len(complaints):,} complaints")

    console.print("  Storing complaints...")
    for i, rec in enumerate(complaints):
        qs = score_complaint(rec)
        rec["quality_score"] = qs.score
        upsert_complaint(conn, rec)
        upsert_vehicle(conn, rec["make"], rec["model"],
                       normalize_make(rec["make"]), normalize_model(rec["model"]))
        if (i + 1) % 50000 == 0:
            conn.commit()
            console.print(f"    [dim]{i + 1:,}/{len(complaints):,}...[/dim]")
    conn.commit()
    console.print(f"  [green]Loaded {len(complaints):,} complaints[/green]")

    # Step 3: Parse and load investigations
    console.print("[bold]Step 3: Parsing investigations...[/bold]")
    investigations = parse_investigations_flat_file()
    console.print(f"  Parsed {len(investigations):,} investigations")

    for rec in investigations:
        qs = score_investigation(rec)
        rec["quality_score"] = qs.score
        upsert_investigation(conn, rec)
    conn.commit()
    console.print(f"  [green]Loaded {len(investigations):,} investigations[/green]")

    # Step 4: Fetch recalls from API
    if not skip_recalls:
        console.print("[bold]Step 4: Fetching recalls from API...[/bold]")
        start_year, end_year = (int(y) for y in recall_years.split("-"))
        model_years = list(range(start_year, end_year + 1))

        def progress(done, total, msg):
            if done % 20 == 0 or done == total:
                console.print(f"    [dim]{done}/{total}: {msg}[/dim]")

        recall_records = fetch_recalls_bulk(MAJOR_MAKES, model_years, progress_callback=progress)
        console.print(f"  Fetched {len(recall_records):,} recalls")

        for rec in recall_records:
            qs = score_recall(rec)
            rec["quality_score"] = qs.score
            upsert_recall(conn, rec)
            upsert_vehicle(conn, rec["make"], rec["model"],
                           normalize_make(rec["make"]), normalize_model(rec["model"]))
        conn.commit()
        console.print(f"  [green]Loaded {len(recall_records):,} recalls[/green]")
    else:
        console.print("[bold]Step 4: Skipping recalls (--skip-recalls)[/bold]")

    # Step 5: Cross-link
    console.print("[bold]Step 5: Cross-linking records...[/bold]")
    link_results = cross_link_all(conn)
    for link_type, count in link_results.items():
        console.print(f"  {link_type}: {count:,} links")

    # Print summary
    stats = get_stats(conn)
    conn.close()

    console.print()
    console.print("[bold green]Pipeline Complete![/bold green]")
    console.print(f"  Complaints: {stats['complaint_count']:,}")
    console.print(f"  Recalls: {stats['recall_count']:,}")
    console.print(f"  Investigations: {stats['investigation_count']:,}")
    console.print(f"  Cross-links: {stats['cross_link_count']:,}")
    console.print(f"  Vehicles: {stats['vehicle_count']:,}")
    console.print(f"  Crashes: {stats['crash_count']:,}")
    console.print(f"  Deaths: {stats['death_total']:,}")


@cli.command()
def stats():
    """Show database statistics."""
    from src.storage.database import get_connection, get_stats

    conn = get_connection()
    s = get_stats(conn)

    table = Table(title="NHTSA Vehicle Safety Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Complaints", f"{s['complaint_count']:,}")
    table.add_row("Recalls", f"{s['recall_count']:,}")
    table.add_row("Investigations", f"{s['investigation_count']:,}")
    table.add_row("Cross-Links", f"{s['cross_link_count']:,}")
    table.add_row("Unique Vehicles", f"{s['vehicle_count']:,}")
    table.add_row("", "")
    table.add_row("[bold]Safety Impact[/bold]", "")
    table.add_row("  Crashes Reported", f"{s['crash_count']:,}")
    table.add_row("  Fires Reported", f"{s['fire_count']:,}")
    table.add_row("  Total Injuries", f"{s['injury_total']:,}")
    table.add_row("  Total Deaths", f"{s['death_total']:,}")
    table.add_row("  Potentially Affected (Recalls)", f"{s['affected_total']:,}")

    if s["top_makes"]:
        table.add_row("", "")
        table.add_row("[bold]Top 10 Makes by Complaints[/bold]", "")
        for make, cnt in s["top_makes"]:
            table.add_row(f"  {make}", f"{cnt:,}")

    conn.close()
    console.print(table)


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["csv", "json", "excel", "markdown", "all"]), default="all")
def export(fmt):
    """Export data to CSV/JSON/Excel/Markdown."""
    from src.export.exporter import export_all
    export_all(fmt)


@cli.command("fetch-investigation-dockets")
@click.option("--limit", default=None, type=int, help="Max investigations to process")
@click.option("--api-key", default=None, help="Regulations.gov API key (or set REGULATIONS_GOV_API_KEY env)")
def fetch_investigation_dockets(limit, api_key):
    """Fetch investigation docket data from Regulations.gov."""
    from src.scrapers.regulations_gov import get_api_key, fetch_all_investigation_dockets
    from src.storage.database import get_connection, init_db

    key = api_key or get_api_key()
    if not key:
        console.print("[red]ERROR: Regulations.gov API key required.[/red]")
        console.print("  Get a free key at: https://open.gsa.gov/api/regulationsgov/")
        console.print("  Then set REGULATIONS_GOV_API_KEY environment variable")
        console.print("  or add to config/api_keys.yaml")
        return

    conn = get_connection()
    init_db(conn)

    # Get investigation numbers not already in dockets table
    existing = set()
    try:
        rows = conn.execute("SELECT investigation_number FROM investigation_dockets").fetchall()
        existing = {r["investigation_number"] for r in rows}
    except Exception:
        pass

    all_inv = conn.execute(
        "SELECT investigation_number FROM investigations ORDER BY open_date DESC"
    ).fetchall()
    to_fetch = [r["investigation_number"] for r in all_inv if r["investigation_number"] not in existing]

    if limit:
        to_fetch = to_fetch[:limit]

    console.print(f"[bold]Fetching dockets for {len(to_fetch)} investigations ({len(existing)} already cached)...[/bold]")

    def progress(done, total, msg):
        console.print(f"  [dim]{done}/{total}: {msg}[/dim]")

    results = fetch_all_investigation_dockets(to_fetch, key, progress_callback=progress)

    # Store dockets
    for d in results["dockets"]:
        conn.execute("""
            INSERT OR REPLACE INTO investigation_dockets (
                docket_id, investigation_number, docket_type, title,
                document_count, last_modified, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            d["docket_id"], d["investigation_number"], d.get("docket_type"),
            d.get("title"), d.get("document_count", 0), d.get("last_modified"),
            0.8 if d.get("title") else 0.5,
        ))

    # Store documents
    for doc in results["documents"]:
        conn.execute("""
            INSERT OR REPLACE INTO investigation_documents (
                document_id, docket_id, investigation_number, document_type,
                title, posted_date, author, summary, determination,
                affected_population, source_url, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc["document_id"], doc["docket_id"], doc.get("investigation_number"),
            doc.get("document_type"), doc.get("title"), doc.get("posted_date"),
            doc.get("author"), doc.get("summary"), doc.get("determination"),
            doc.get("affected_population"), doc.get("source_url"),
            0.7 if doc.get("title") else 0.4,
        ))

    conn.commit()
    conn.close()

    console.print(f"[green]Stored {len(results['dockets'])} dockets and {len(results['documents'])} documents[/green]")


@cli.command("fetch-vehicle-attributes")
@click.option("--limit", default=None, type=int, help="Max vehicles to process")
def fetch_vehicle_attributes(limit):
    """Fetch vehicle attributes from NHTSA VPIC API."""
    from src.scrapers.vpic import fetch_vehicle_attributes as fetch_attrs
    from src.storage.database import get_connection, init_db, upsert_vehicle_attributes

    conn = get_connection()
    init_db(conn)

    # Get unique make/model/year combinations from complaints
    rows = conn.execute("""
        SELECT DISTINCT v.make_normalized as make, v.model_normalized as model, c.model_year
        FROM vehicles v
        JOIN complaints c ON UPPER(c.make) = v.make_normalized
                         AND UPPER(c.model) = v.model_normalized
        WHERE c.model_year >= 2000
        ORDER BY make, model, model_year
    """).fetchall()

    # Filter out vehicles already in vehicle_attributes
    existing = set()
    try:
        existing_rows = conn.execute(
            "SELECT make, model, model_year FROM vehicle_attributes"
        ).fetchall()
        existing = {(r["make"], r["model"], r["model_year"]) for r in existing_rows}
    except Exception:
        pass

    vehicles = [
        {"make": r["make"], "model": r["model"], "model_year": r["model_year"]}
        for r in rows
        if (r["make"], r["model"], r["model_year"]) not in existing
    ]

    if limit:
        vehicles = vehicles[:limit]

    console.print(f"[bold]Fetching attributes for {len(vehicles)} vehicles ({len(existing)} already cached)...[/bold]")

    def progress(done, total, msg):
        if done % 100 == 0 or done == total:
            console.print(f"  [dim]{done}/{total}: {msg}[/dim]")

    from src.scrapers.vpic import fetch_vehicle_attributes_bulk
    results = fetch_vehicle_attributes_bulk(vehicles, progress_callback=progress)

    stored = 0
    for attrs in results:
        vid = upsert_vehicle_attributes(conn, attrs)
        if vid:
            stored += 1
    conn.commit()
    conn.close()

    console.print(f"[green]Stored {stored} vehicle attribute records[/green]")


@cli.command("build-manufacturer-profiles")
def build_manufacturer_profiles():
    """Build manufacturer risk profiles from existing data."""
    from src.normalization.manufacturer_profiles import build_manufacturer_profiles as build_profiles
    from src.storage.database import get_connection, init_db

    console.print("[bold]Building manufacturer risk profiles...[/bold]")
    conn = get_connection()
    init_db(conn)

    results = build_profiles(conn)
    conn.close()

    console.print(f"  [green]Created {results['profiles_created']} manufacturer profiles[/green]")
    console.print(f"  [green]Created {results['yearly_metrics_created']} yearly metric records[/green]")

    # Show top risk manufacturers
    conn = get_connection()
    rows = conn.execute("""
        SELECT manufacturer_name, risk_tier, risk_score, total_complaints,
               total_deaths, severity_index
        FROM manufacturer_profiles
        WHERE total_complaints >= 50
        ORDER BY risk_score DESC LIMIT 10
    """).fetchall()
    conn.close()

    if rows:
        table = Table(title="Top 10 Highest Risk Manufacturers")
        table.add_column("Manufacturer", style="cyan")
        table.add_column("Risk Tier", style="red")
        table.add_column("Risk Score", style="yellow")
        table.add_column("Complaints", style="green")
        table.add_column("Deaths", style="red")
        table.add_column("Severity", style="yellow")
        for r in rows:
            table.add_row(
                r["manufacturer_name"], r["risk_tier"],
                f"{r['risk_score']:.4f}", f"{r['total_complaints']:,}",
                str(r["total_deaths"]), f"{r['severity_index']:.4f}",
            )
        console.print(table)


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


if __name__ == "__main__":
    cli()
