"""CLI for Employer Labor Compliance Tracker."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """Employer Labor Compliance Tracker — Multi-agency employer violation database."""
    pass


@cli.command()
@click.option("--whd/--no-whd", default=True, help="Download WHD data")
@click.option("--osha/--no-osha", default=True, help="Download OSHA data")
@click.option("--nlrb/--no-nlrb", default=True, help="Download NLRB data")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape(whd: bool, osha: bool, nlrb: bool, force: bool):
    """Download raw data from all sources."""
    if whd:
        console.print("[bold blue]Downloading WHD compliance data...[/]")
        from src.scrapers.whd import download_whd_data
        try:
            path = download_whd_data(force=force)
            console.print(f"  [green]✓[/] WHD data at {path}")
        except Exception as e:
            console.print(f"  [red]✗ WHD download failed: {e}[/]")

    if osha:
        console.print("[bold blue]Downloading OSHA inspection data...[/]")
        from src.scrapers.osha import download_osha_data
        try:
            path = download_osha_data(force=force)
            console.print(f"  [green]✓[/] OSHA data at {path}")
        except Exception as e:
            console.print(f"  [red]✗ OSHA download failed: {e}[/]")

    if nlrb:
        console.print("[bold blue]Downloading NLRB case data...[/]")
        from src.scrapers.nlrb import download_nlrb_data
        try:
            path = download_nlrb_data(force=force)
            console.print(f"  [green]✓[/] NLRB data at {path}")
        except Exception as e:
            console.print(f"  [red]✗ NLRB download failed: {e}[/]")


@cli.command()
@click.option("--min-year", default=2015, help="Minimum year to include")
def extract(min_year: int):
    """Parse and extract structured records from raw data."""
    from src.scrapers.whd import parse_whd_csv, CACHE_FILE as WHD_FILE
    from src.scrapers.osha import parse_osha_csv, CACHE_FILE as OSHA_FILE
    from src.scrapers.nlrb import parse_nlrb_db, parse_nlrb_csv, NLRB_DB_FILE, NLRB_CSV_FILE

    results = {}

    if WHD_FILE.exists():
        console.print("[bold blue]Parsing WHD data...[/]")
        whd_records = parse_whd_csv(min_year=min_year)
        results["whd"] = whd_records
        console.print(f"  [green]✓[/] {len(whd_records):,} WHD records")

    if OSHA_FILE.exists():
        console.print("[bold blue]Parsing OSHA data...[/]")
        osha_records = parse_osha_csv(min_year=min_year)
        results["osha"] = osha_records
        console.print(f"  [green]✓[/] {len(osha_records):,} OSHA records")

    if NLRB_DB_FILE.exists():
        console.print("[bold blue]Parsing NLRB data (SQLite DB)...[/]")
        nlrb_records = parse_nlrb_db(min_year=min_year)
        results["nlrb"] = nlrb_records
        console.print(f"  [green]✓[/] {len(nlrb_records):,} NLRB records")
    elif NLRB_CSV_FILE.exists():
        console.print("[bold blue]Parsing NLRB data (CSV)...[/]")
        nlrb_records = parse_nlrb_csv(min_year=min_year)
        results["nlrb"] = nlrb_records
        console.print(f"  [green]✓[/] {len(nlrb_records):,} NLRB records")

    return results


@cli.command()
@click.option("--min-year", default=2015, help="Minimum year to include")
def pipeline(min_year: int):
    """Run the full pipeline: extract → normalize → score → store → cross-link."""
    from src.storage.database import get_connection, init_db, upsert_whd_case, upsert_osha_inspection, upsert_nlrb_case
    from src.normalization.employers import normalize_employer
    from src.validation.quality import score_whd_case, score_osha_inspection, score_nlrb_case
    from src.normalization.cross_linker import cross_link_all
    from src.scrapers.whd import parse_whd_csv, CACHE_FILE as WHD_FILE
    from src.scrapers.osha import parse_osha_csv, CACHE_FILE as OSHA_FILE
    from src.scrapers.nlrb import parse_nlrb_db, parse_nlrb_csv, NLRB_DB_FILE, NLRB_CSV_FILE

    conn = get_connection()
    init_db(conn)

    # 1. WHD
    if WHD_FILE.exists():
        console.print("[bold blue]Processing WHD data...[/]")
        records = parse_whd_csv(min_year=min_year)
        for rec in records:
            name = rec.get("trade_name", "") or rec.get("legal_name", "")
            rec["employer_normalized"] = normalize_employer(name)
            qs = score_whd_case(rec)
            rec["quality_score"] = qs.score
            upsert_whd_case(conn, rec)
        conn.commit()
        console.print(f"  [green]✓[/] {len(records):,} WHD cases loaded")
    else:
        console.print("  [yellow]⚠[/] WHD data not found — run 'scrape' first")

    # 2. OSHA
    if OSHA_FILE.exists():
        console.print("[bold blue]Processing OSHA data...[/]")
        records = parse_osha_csv(min_year=min_year)
        for rec in records:
            rec["employer_normalized"] = normalize_employer(rec.get("establishment_name", ""))
            qs = score_osha_inspection(rec)
            rec["quality_score"] = qs.score
            upsert_osha_inspection(conn, rec)
        conn.commit()
        console.print(f"  [green]✓[/] {len(records):,} OSHA inspections loaded")
    else:
        console.print("  [yellow]⚠[/] OSHA data not found — run 'scrape' first")

    # 3. NLRB
    if NLRB_DB_FILE.exists():
        console.print("[bold blue]Processing NLRB data (SQLite DB)...[/]")
        records = parse_nlrb_db(min_year=min_year)
        for rec in records:
            rec["employer_normalized"] = normalize_employer(rec.get("case_name", ""))
            qs = score_nlrb_case(rec)
            rec["quality_score"] = qs.score
            upsert_nlrb_case(conn, rec)
        conn.commit()
        console.print(f"  [green]✓[/] {len(records):,} NLRB cases loaded")
    elif NLRB_CSV_FILE.exists():
        console.print("[bold blue]Processing NLRB data (CSV)...[/]")
        records = parse_nlrb_csv(min_year=min_year)
        for rec in records:
            rec["employer_normalized"] = normalize_employer(rec.get("case_name", ""))
            qs = score_nlrb_case(rec)
            rec["quality_score"] = qs.score
            upsert_nlrb_case(conn, rec)
        conn.commit()
        console.print(f"  [green]✓[/] {len(records):,} NLRB cases loaded")
    else:
        console.print("  [yellow]⚠[/] NLRB data not found — run 'scrape' first")

    # 4. Cross-link
    console.print("[bold blue]Cross-linking records across agencies...[/]")
    results = cross_link_all(conn)
    console.print(f"  [green]✓[/] {results.get('exact_matches', 0):,} exact matches")
    console.print(f"  [green]✓[/] {results.get('fuzzy_matches', 0):,} fuzzy matches")
    console.print(f"  [green]✓[/] {results.get('employers_created', 0):,} employer profiles")

    conn.close()
    console.print("[bold green]Pipeline complete![/]")


@cli.command()
def stats():
    """Show database statistics."""
    from src.storage.database import get_connection, init_db, get_stats

    conn = get_connection()
    init_db(conn)
    s = get_stats(conn)
    conn.close()

    table = Table(title="Employer Labor Compliance — Database Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("WHD Cases", f"{s['whd_count']:,}")
    table.add_row("OSHA Inspections", f"{s['osha_count']:,}")
    table.add_row("NLRB Cases", f"{s['nlrb_count']:,}")
    table.add_row("Unique Employers", f"{s['employer_count']:,}")
    table.add_row("Cross-Links", f"{s['cross_link_count']:,}")
    table.add_row("", "")
    table.add_row("Total Back Wages", f"${s['total_back_wages']:,.0f}")
    table.add_row("Total WHD Penalties", f"${s['total_whd_penalties']:,.0f}")
    table.add_row("Total OSHA Penalties", f"${s['total_osha_penalties']:,.0f}")
    table.add_row("Total Fatalities", f"{s['total_fatalities']:,}")
    table.add_row("Employees Affected", f"{s['employees_affected']:,}")
    table.add_row("", "")
    table.add_row("Avg Quality — WHD", f"{s['avg_quality']['whd']:.3f}")
    table.add_row("Avg Quality — OSHA", f"{s['avg_quality']['osha']:.3f}")
    table.add_row("Avg Quality — NLRB", f"{s['avg_quality']['nlrb']:.3f}")

    console.print(table)

    if s["top_states"]:
        console.print("\n[bold]Top States by WHD Cases:[/]")
        for state, cnt in s["top_states"][:5]:
            console.print(f"  {state}: {cnt:,}")

    if s["multi_agency_offenders"]:
        console.print("\n[bold]Multi-Agency Offenders (top 10):[/]")
        for emp in s["multi_agency_offenders"]:
            console.print(
                f"  {emp['name_normalized']}: "
                f"WHD={emp['whd_case_count']}, "
                f"OSHA={emp['osha_inspection_count']}, "
                f"NLRB={emp['nlrb_case_count']}"
            )


@cli.command()
@click.option("--output-dir", default=None, help="Export directory")
def export(output_dir: str | None):
    """Export data as CSV, JSON, and Excel."""
    from src.export.exporter import export_all

    out = Path(output_dir) if output_dir else None
    export_all(output_dir=out)


@cli.command()
@click.option("--port", default=8501, help="Streamlit port")
def dashboard(port: int):
    """Launch the Streamlit dashboard."""
    import subprocess
    app_path = Path(__file__).parent / "dashboard" / "app.py"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port", str(port),
        "--server.headless", "true",
    ])


if __name__ == "__main__":
    cli()
