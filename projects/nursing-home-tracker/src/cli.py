"""CLI interface for Nursing Home Inspection & Deficiency Tracker.

Commands: download, extract, normalize, validate, export, dashboard, stats,
          download-hcris, extract-hcris, pipeline
"""

import click
from pathlib import Path
from rich.console import Console

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent


@click.group()
@click.version_option(version="0.2.0")
def cli():
    """Nursing Home Inspection & Deficiency Tracker

    Cross-linked database of nursing home quality, ownership, enforcement,
    and financial data from CMS. Connects deficiency citations, penalties,
    ownership chains (including PE/REIT), staffing levels, quality measures,
    cost reports, and related-party transactions across 14,710+ US nursing homes.
    """
    pass


@cli.command()
@click.option("--source", "-s", help="Specific source to download (default: all)")
@click.option("--force", "-f", is_flag=True, help="Re-download even if cached")
def download(source, force):
    """Download CSV datasets from CMS data.cms.gov."""
    from src.scrapers.cms_downloader import download_all, download_source
    if source:
        download_source(source, force=force)
    else:
        download_all(force=force)


@cli.command("download-hcris")
@click.option("--force", "-f", is_flag=True, help="Re-download even if cached")
@click.option("--years", "-y", help="Comma-separated fiscal years (default: 2019-2024)")
def download_hcris(force, years):
    """Download HCRIS cost report EAV data (SNF Form 2540-10)."""
    from src.scrapers.hcris_downloader import download_hcris as _download
    year_list = None
    if years:
        year_list = [int(y.strip()) for y in years.split(",")]
    _download(force=force, years=year_list)


@cli.command("download-ownership")
@click.option("--force", "-f", is_flag=True, help="Re-download even if cached")
def download_ownership(force):
    """Download SNF All Owners and Change of Ownership datasets."""
    from src.scrapers.snf_owners_downloader import download_all_ownership
    download_all_ownership(force=force)


@cli.command()
@click.option("--source", "-s", help="Extract from specific source only")
def extract(source):
    """Extract and parse structured records from raw CSV downloads."""
    from src.extractors.csv_parser import extract_all, extract_source
    if source:
        extract_source(source)
    else:
        extract_all()


@cli.command("extract-hcris")
def extract_hcris():
    """Extract cost reports, RPT, rent/leases, and capital costs from HCRIS data."""
    from src.extractors.hcris_parser import extract_hcris as _extract
    from src.storage.database import init_db, insert_records, clear_table

    init_db()
    cost_reports, rpt_records, rent_leases, capital_costs = _extract()

    if cost_reports:
        clear_table("cost_reports")
        insert_records("cost_reports", cost_reports)
        console.print(f"  [green]✓[/green] Stored {len(cost_reports):,} cost reports")

    if rpt_records:
        clear_table("related_party_transactions")
        insert_records("related_party_transactions", rpt_records)
        console.print(f"  [green]✓[/green] Stored {len(rpt_records):,} related-party transactions")

    if rent_leases:
        clear_table("hcris_revenue_by_payer")
        insert_records("hcris_revenue_by_payer", rent_leases)
        console.print(f"  [green]✓[/green] Stored {len(rent_leases):,} revenue-by-payer records")

    if capital_costs:
        clear_table("hcris_capital_costs")
        insert_records("hcris_capital_costs", capital_costs)
        console.print(f"  [green]✓[/green] Stored {len(capital_costs):,} capital cost records")


@cli.command()
def normalize():
    """Normalize entities and classify ownership types (PE, REIT, nonprofit, etc.)."""
    from src.normalization.owners import normalize_owners
    normalize_owners()


@cli.command("normalize-rpt")
def normalize_rpt():
    """Normalize related-party transaction names and cross-link with ownership."""
    from src.normalization.related_parties import normalize_related_parties
    normalize_related_parties()


@cli.command("build-profiles")
def build_profiles():
    """Build aggregated owner profiles from ownership and quality data."""
    from src.storage.database import build_owner_profiles
    build_owner_profiles()


@cli.command()
def validate():
    """Run data quality validation and compute quality scores."""
    from src.validation.quality import validate_all, detect_rpt_anomalies
    validate_all()
    detect_rpt_anomalies()


@cli.command("detect-networks")
def detect_networks():
    """Detect shared address networks among owner LLCs."""
    from src.normalization.owners import detect_shared_address_networks
    detect_shared_address_networks()


@cli.command("download-oig")
@click.option("--force", "-f", is_flag=True, help="Re-download even if cached")
def download_oig(force):
    """Download OIG LEIE exclusion list."""
    from src.scrapers.oig_downloader import download_oig as _download
    _download(force=force)


@cli.command("extract-oig")
def extract_oig():
    """Parse OIG LEIE CSV and cross-link to nursing home ownership."""
    from src.extractors.oig_parser import parse_oig_csv, cross_link_oig
    from src.storage.database import init_db, insert_records, clear_table

    init_db()
    records = parse_oig_csv()
    if records:
        clear_table("oig_exclusions")
        insert_records("oig_exclusions", records)
        console.print(f"  [green]✓[/green] Stored {len(records):,} OIG exclusion records")
        cross_link_oig()


@cli.command("download-sec")
def download_sec():
    """Download 10-K filing metadata from SEC EDGAR for healthcare REITs."""
    from src.scrapers.sec_edgar import download_sec_filings
    download_sec_filings()


@cli.command("download-hcai-ca")
@click.option("--force", "-f", is_flag=True, help="Re-download even if cached")
def download_hcai_ca(force):
    """Download CA HCAI long-term care facility financial disclosures."""
    from src.scrapers.ca_hcai_downloader import download_hcai_files
    download_hcai_files(force=force)


@cli.command("extract-hcai-ca")
def extract_hcai_ca():
    """Parse and store CA HCAI disclosure reports."""
    from src.extractors.ca_hcai_parser import parse_all_hcai_files, store_hcai_records
    from src.storage.database import init_db
    init_db()
    records = parse_all_hcai_files()
    if records:
        store_hcai_records(records)


@cli.command()
@click.option("--format", "-f", "fmt",
              type=click.Choice(["csv", "json", "excel", "markdown", "all"]),
              default="all")
@click.option("--output-dir", "-o", default="data/exports", help="Output directory")
def export(fmt, output_dir):
    """Export data in various formats."""
    from src.export.exporter import export_data
    export_data(fmt, output_dir)


@cli.command("build-deploy-db")
def build_deploy_db():
    """Build a compact deploy database with pre-aggregated summary tables."""
    from scripts.build_deploy_db import build_deploy_db as _build
    _build()


@cli.command()
@click.option("--port", "-p", type=int, default=8501, help="Dashboard port")
def dashboard(port):
    """Launch the Streamlit dashboard."""
    import subprocess
    subprocess.run([
        "streamlit", "run", "src/dashboard/app.py",
        "--server.port", str(port)
    ])


@cli.command()
def stats():
    """Show database statistics."""
    from src.storage.database import get_stats
    get_stats()


@cli.command()
@click.option("--skip-download", is_flag=True, help="Skip download step (use cached data)")
@click.option("--force-download", is_flag=True, help="Force re-download even if cached")
def pipeline(skip_download, force_download):
    """Run the full pipeline: download → extract → store → normalize → enrich → validate."""
    console.print("[bold blue]Starting full pipeline...[/bold blue]")
    from src.scrapers.cms_downloader import download_all
    from src.scrapers.hcris_downloader import download_hcris as dl_hcris
    from src.scrapers.snf_owners_downloader import download_all_ownership
    from src.extractors.csv_parser import extract_all
    from src.extractors.hcris_parser import extract_hcris
    from src.normalization.owners import normalize_owners
    from src.normalization.related_parties import normalize_related_parties
    from src.validation.quality import validate_all
    from src.storage.database import (init_db, store_source_data, insert_records,
                                       clear_table, build_owner_profiles)

    # Initialize database
    console.print("\n[bold]Initializing database...[/bold]")
    init_db()

    if not skip_download:
        console.print("\n[bold]Step 1: Downloading CMS datasets...[/bold]")
        download_all(force=force_download)

        console.print("\n[bold]Step 2: Downloading HCRIS + ownership + OIG + SEC + CA HCAI...[/bold]")
        dl_hcris(force=force_download)
        download_all_ownership(force=force_download)
        try:
            from src.scrapers.oig_downloader import download_oig as dl_oig
            dl_oig(force=force_download)
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] OIG download skipped: {e}")
        try:
            from src.scrapers.sec_edgar import download_sec_filings
            download_sec_filings()
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] SEC EDGAR download skipped: {e}")
        try:
            from src.scrapers.ca_hcai_downloader import download_hcai_files
            download_hcai_files(force=force_download)
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] CA HCAI download skipped: {e}")
    else:
        console.print("\n[bold]Step 1-2: Skipping download (using cached data)...[/bold]")

    console.print("\n[bold]Step 3: Extracting CMS CSV records...[/bold]")
    all_records = extract_all()

    console.print("\n[bold]Step 4: Storing CMS records...[/bold]")
    # Load providers first, then other tables
    if "provider_info" in all_records and all_records["provider_info"]:
        store_source_data("provider_info", all_records["provider_info"])
    for source_key, records in all_records.items():
        if source_key != "provider_info" and records:
            store_source_data(source_key, records)

    # Extract and store HCRIS data
    console.print("\n[bold]Step 5: Extracting HCRIS cost report data...[/bold]")
    try:
        cost_reports, rpt_records, rent_leases, capital_costs = extract_hcris()
        if cost_reports:
            clear_table("cost_reports")
            insert_records("cost_reports", cost_reports)
            console.print(f"  [green]✓[/green] Stored {len(cost_reports):,} cost reports")
        if rpt_records:
            clear_table("related_party_transactions")
            insert_records("related_party_transactions", rpt_records)
            console.print(f"  [green]✓[/green] Stored {len(rpt_records):,} related-party transactions")
        if rent_leases:
            clear_table("hcris_revenue_by_payer")
            insert_records("hcris_revenue_by_payer", rent_leases)
            console.print(f"  [green]✓[/green] Stored {len(rent_leases):,} revenue-by-payer records")
        if capital_costs:
            clear_table("hcris_capital_costs")
            insert_records("hcris_capital_costs", capital_costs)
            console.print(f"  [green]✓[/green] Stored {len(capital_costs):,} capital cost records")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] HCRIS extraction skipped: {e}")

    # Extract and store OIG exclusions
    console.print("\n[bold]Step 6: Extracting OIG exclusion records...[/bold]")
    try:
        from src.extractors.oig_parser import parse_oig_csv
        oig_records = parse_oig_csv()
        if oig_records:
            clear_table("oig_exclusions")
            insert_records("oig_exclusions", oig_records)
            console.print(f"  [green]✓[/green] Stored {len(oig_records):,} OIG exclusion records")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] OIG extraction skipped: {e}")

    # Extract and store CA HCAI data
    console.print("\n[bold]Step 7: Extracting CA HCAI financial disclosures...[/bold]")
    try:
        from src.extractors.ca_hcai_parser import parse_all_hcai_files, store_hcai_records
        hcai_records = parse_all_hcai_files()
        if hcai_records:
            store_hcai_records(hcai_records)
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] CA HCAI extraction skipped: {e}")

    console.print("\n[bold]Step 8: Normalizing entities...[/bold]")
    normalize_owners()
    try:
        normalize_related_parties()
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] RPT normalization skipped: {e}")

    # Cross-link OIG after ownership normalization
    console.print("\n[bold]Step 9: Cross-linking OIG exclusions to ownership...[/bold]")
    try:
        from src.extractors.oig_parser import cross_link_oig
        cross_link_oig()
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] OIG cross-linking skipped: {e}")

    console.print("\n[bold]Step 10: Building owner profiles...[/bold]")
    try:
        build_owner_profiles()
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Owner profiles skipped: {e}")

    console.print("\n[bold]Step 11: Validating data quality...[/bold]")
    validate_all()

    console.print("\n[bold]Step 12: Detecting RPT anomalies...[/bold]")
    try:
        from src.validation.quality import detect_rpt_anomalies
        detect_rpt_anomalies()
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] RPT anomaly detection skipped: {e}")

    console.print("\n[bold]Step 13: Detecting shared address networks...[/bold]")
    try:
        from src.normalization.owners import detect_shared_address_networks
        detect_shared_address_networks()
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Address network detection skipped: {e}")

    console.print("\n[bold]Step 14: Recording pipeline run...[/bold]")
    try:
        from src.storage.database import get_connection
        _conn = get_connection()
        # Count total records across all tables
        total_recs = 0
        sources_list = []
        for sk, recs in all_records.items():
            if recs:
                total_recs += len(recs)
                sources_list.append(sk)
        _conn.execute(
            """INSERT INTO pipeline_runs (completed_at, status, sources_processed, total_records)
               VALUES (datetime('now'), 'completed', ?, ?)""",
            (",".join(sources_list), total_recs),
        )
        _conn.commit()
        _conn.close()
        console.print(f"  [green]✓[/green] Pipeline run logged: {total_recs:,} records from {len(sources_list)} sources")
    except Exception as e:
        console.print(f"  [yellow]⚠[/yellow] Pipeline run logging skipped: {e}")

    console.print("\n[bold green]Pipeline complete![/bold green]")


if __name__ == "__main__":
    cli()
