"""CLI for H-1B Employer Compliance Tracker."""

import time
from pathlib import Path

import click

from src.storage.database import (
    get_connection, init_db, upsert_lca, upsert_uscis,
    upsert_whd, upsert_debarments, get_stats,
)
from src.validation.quality import score_lca, score_uscis, score_whd


@click.group()
def cli():
    """H-1B Employer Compliance Tracker."""
    pass


@cli.command()
def init():
    """Initialize the database."""
    conn = get_connection()
    init_db(conn)
    conn.close()
    click.echo("Database initialized.")


@cli.command()
@click.option("--years", "-y", multiple=True, type=int, help="Fiscal years to download")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_lca(years, force):
    """Download and import LCA disclosure data."""
    from src.scrapers.lca import download_lca, parse_lca, AVAILABLE_YEARS

    if not years:
        years = AVAILABLE_YEARS

    conn = get_connection()
    init_db(conn)

    total = 0
    for fy in years:
        click.echo(f"Downloading LCA FY{fy}...")
        try:
            path = download_lca(fy, force=force)
            click.echo(f"  Parsing {path.name}...")
            records = parse_lca(path, fiscal_year=fy)

            # Score records
            for rec in records:
                rec["quality_score"] = score_lca(rec)

            click.echo(f"  Importing {len(records):,} records...")
            n = upsert_lca(conn, records)
            total += n
            click.echo(f"  Done: {n:,} records imported")
            time.sleep(3)  # Rate limit between files
        except Exception as e:
            click.echo(f"  Error: {e}", err=True)

    conn.close()
    click.echo(f"\nTotal LCA records imported: {total:,}")


@cli.command()
@click.option("--years", "-y", multiple=True, type=int, help="Fiscal years to download")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_uscis(years, force):
    """Download and import USCIS employer data hub."""
    from src.scrapers.uscis import download_uscis, parse_uscis_csv, AVAILABLE_YEARS

    if not years:
        years = AVAILABLE_YEARS

    conn = get_connection()
    init_db(conn)

    total = 0
    for fy in years:
        click.echo(f"Downloading USCIS FY{fy}...")
        try:
            path = download_uscis(fy, force=force)
            click.echo(f"  Parsing {path.name}...")
            records = parse_uscis_csv(path, fiscal_year=fy)

            for rec in records:
                rec["quality_score"] = score_uscis(rec)

            click.echo(f"  Importing {len(records):,} records...")
            n = upsert_uscis(conn, records)
            total += n
            click.echo(f"  Done: {n:,} records imported")
            time.sleep(2)
        except Exception as e:
            click.echo(f"  Error: {e}", err=True)

    conn.close()
    click.echo(f"\nTotal USCIS records imported: {total:,}")


@cli.command()
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_whd(force):
    """Download and import WHD enforcement data."""
    from src.scrapers.whd import download_debarments

    conn = get_connection()
    init_db(conn)

    # Download debarment/willful violator lists
    click.echo("Downloading debarment & willful violator lists...")
    try:
        records = download_debarments(force=force)
        for rec in records:
            rec["quality_score"] = score_whd(rec)
        n = upsert_debarments(conn, records)
        click.echo(f"  Imported {n} debarment/willful violator records")
    except Exception as e:
        click.echo(f"  Error: {e}", err=True)

    conn.close()


@cli.command()
def crosslink():
    """Build cross-links between data sources and employer profiles."""
    from src.normalization.cross_linker import build_cross_links, build_employer_profiles

    conn = get_connection()
    init_db(conn)

    click.echo("Building cross-links...")
    n_links = build_cross_links(conn)
    click.echo(f"  Created {n_links:,} cross-links")

    click.echo("Building employer profiles...")
    n_profiles = build_employer_profiles(conn)
    click.echo(f"  Created {n_profiles:,} employer profiles")

    conn.close()


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output directory")
def export(output):
    """Export data to CSV, JSON, and Markdown."""
    from src.export.exporter import export_all

    conn = get_connection()
    out_dir = Path(output) if output else None

    click.echo("Exporting data...")
    results = export_all(conn, out_dir)

    for name, count in results.items():
        click.echo(f"  {name}: {count:,}")

    conn.close()
    click.echo("Export complete.")


@cli.command()
def stats():
    """Show database statistics."""
    conn = get_connection()
    s = get_stats(conn)
    conn.close()

    click.echo("H-1B Employer Compliance Tracker — Statistics")
    click.echo("=" * 50)
    click.echo(f"LCA Applications:     {s.get('lca_applications', 0):>10,}")
    click.echo(f"Unique Employers:     {s.get('unique_employers', 0):>10,}")
    click.echo(f"USCIS Employers:      {s.get('uscis_employers', 0):>10,}")
    click.echo(f"WHD Violations:       {s.get('whd_violations', 0):>10,}")
    click.echo(f"Debarments:           {s.get('debarments', 0):>10,}")
    click.echo(f"Employer Profiles:    {s.get('employer_profiles', 0):>10,}")
    click.echo(f"Cross-Links:          {s.get('cross_links', 0):>10,}")
    click.echo(f"Fiscal Years:         {s.get('fiscal_years', 0):>10}")
    click.echo(f"States:               {s.get('states', 0):>10}")
    click.echo(f"Average Wage:         ${s.get('avg_wage', 0):>10,.0f}")
    click.echo(f"Total Workers:        {s.get('total_workers', 0):>10,}")
    click.echo(f"Total Back Wages:     ${s.get('total_back_wages', 0):>10,.0f}")
    click.echo()
    click.echo(f"LCA Quality Avg:      {s.get('lca_applications_quality_avg', 0):>10.3f}")
    click.echo(f"USCIS Quality Avg:    {s.get('uscis_employers_quality_avg', 0):>10.3f}")
    click.echo(f"WHD Quality Avg:      {s.get('whd_violations_quality_avg', 0):>10.3f}")


@cli.command()
def pipeline():
    """Run the full pipeline: scrape all → crosslink → export."""
    from src.scrapers.lca import download_lca, parse_lca, AVAILABLE_YEARS as LCA_YEARS
    from src.scrapers.uscis import download_uscis, parse_uscis_csv, AVAILABLE_YEARS as USCIS_YEARS
    from src.scrapers.whd import download_debarments
    from src.normalization.cross_linker import build_cross_links, build_employer_profiles
    from src.export.exporter import export_all

    conn = get_connection()
    init_db(conn)

    # 1. LCA data
    click.echo("=" * 50)
    click.echo("PHASE 1: LCA Data")
    click.echo("=" * 50)
    for fy in LCA_YEARS:
        click.echo(f"  FY{fy}...", nl=False)
        try:
            path = download_lca(fy)
            records = parse_lca(path, fiscal_year=fy)
            for rec in records:
                rec["quality_score"] = score_lca(rec)
            n = upsert_lca(conn, records)
            click.echo(f" {n:,} records")
            time.sleep(3)
        except Exception as e:
            click.echo(f" Error: {e}")

    # 2. USCIS data
    click.echo("\n" + "=" * 50)
    click.echo("PHASE 2: USCIS Employer Data")
    click.echo("=" * 50)
    for fy in USCIS_YEARS:
        click.echo(f"  FY{fy}...", nl=False)
        try:
            path = download_uscis(fy)
            records = parse_uscis_csv(path, fiscal_year=fy)
            for rec in records:
                rec["quality_score"] = score_uscis(rec)
            n = upsert_uscis(conn, records)
            click.echo(f" {n:,} records")
            time.sleep(2)
        except Exception as e:
            click.echo(f" Error: {e}")

    # 3. WHD / Debarments
    click.echo("\n" + "=" * 50)
    click.echo("PHASE 3: Debarments & Willful Violators")
    click.echo("=" * 50)
    try:
        records = download_debarments()
        for rec in records:
            rec["quality_score"] = score_whd(rec)
        n = upsert_debarments(conn, records)
        click.echo(f"  {n} debarment/violator records")
    except Exception as e:
        click.echo(f"  Error: {e}")

    # 4. Cross-links
    click.echo("\n" + "=" * 50)
    click.echo("PHASE 4: Cross-Linking")
    click.echo("=" * 50)
    n_links = build_cross_links(conn)
    click.echo(f"  {n_links:,} cross-links created")

    n_profiles = build_employer_profiles(conn)
    click.echo(f"  {n_profiles:,} employer profiles built")

    # 5. Export
    click.echo("\n" + "=" * 50)
    click.echo("PHASE 5: Export")
    click.echo("=" * 50)
    results = export_all(conn)
    for name, count in results.items():
        click.echo(f"  {name}: {count:,}")

    # 6. Stats
    click.echo("\n" + "=" * 50)
    click.echo("COMPLETE")
    click.echo("=" * 50)
    s = get_stats(conn)
    click.echo(f"  LCA Applications:  {s.get('lca_applications', 0):,}")
    click.echo(f"  USCIS Employers:   {s.get('uscis_employers', 0):,}")
    click.echo(f"  Employer Profiles: {s.get('employer_profiles', 0):,}")
    click.echo(f"  Cross-Links:       {s.get('cross_links', 0):,}")
    click.echo(f"  WHD Violations:    {s.get('whd_violations', 0):,}")
    click.echo(f"  Debarments:        {s.get('debarments', 0):,}")

    conn.close()


@cli.command()
@click.option("--port", "-p", default=8501, type=int)
def dashboard(port):
    """Launch the Streamlit dashboard."""
    import subprocess
    app_path = Path(__file__).parent / "dashboard" / "app.py"
    subprocess.run(["streamlit", "run", str(app_path), "--server.port", str(port)])


if __name__ == "__main__":
    cli()
