"""
Click CLI for the CFPB Consumer Complaint Cross-Linked Analysis project.

Provides commands for: scrape, extract, normalize, validate, export, dashboard, pipeline, stats.

Usage:
    python -m src.cli scrape --source cfpb
    python -m src.cli pipeline --full
    python -m src.cli dashboard
"""

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="cfpb-tracker")
def cli():
    """CFPB Consumer Complaint Cross-Linked Analysis.

    Cross-links CFPB consumer complaints with FDIC bank data,
    CRA ratings, and enforcement actions.

    Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
    """
    pass


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--source",
    type=click.Choice([
        "cfpb", "fdic", "cra", "enforcement",
        "financials", "occ", "fed", "fdic-enforcement", "hmda",
        "all", "all-enriched",
    ]),
    default="all",
    help="Data source to scrape. 'all-enriched' includes enrichment sources.",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Use cached data if available. Default: use cache.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Maximum number of records to download (for testing).",
)
def scrape(source: str, cache: bool, limit: int | None):
    """Download raw data from configured sources."""
    from src.storage.database import init_db
    from src.scrapers.cfpb_downloader import run_cfpb_pipeline
    from src.scrapers.fdic_downloader import run_fdic_pipeline
    from src.scrapers.enforcement_scraper import run_enforcement_pipeline
    from src.scrapers.cra_downloader import run_cra_pipeline

    console.print(f"[bold blue]Scraping source: {source}[/bold blue]")
    conn = init_db()

    try:
        if source in ("fdic", "all", "all-enriched"):
            console.print("\n[bold]--- FDIC Institutions ---[/bold]")
            run_fdic_pipeline(conn, limit=limit, active_only=False)

        if source in ("cfpb", "all", "all-enriched"):
            console.print("\n[bold]--- CFPB Complaints ---[/bold]")
            run_cfpb_pipeline(conn, force_download=not cache, limit=limit)

        if source in ("enforcement", "all", "all-enriched"):
            console.print("\n[bold]--- CFPB Enforcement Actions ---[/bold]")
            run_enforcement_pipeline(conn)

        if source in ("cra", "all", "all-enriched"):
            console.print("\n[bold]--- CRA Ratings ---[/bold]")
            run_cra_pipeline(conn)

        # Enrichment sources
        if source in ("financials", "all-enriched"):
            from src.scrapers.fdic_financials import run_financials_pipeline
            console.print("\n[bold]--- FDIC Financial Data ---[/bold]")
            run_financials_pipeline(conn, limit=limit)

        if source in ("occ", "all-enriched"):
            from src.scrapers.occ_enforcement import run_occ_pipeline
            console.print("\n[bold]--- OCC Enforcement Actions ---[/bold]")
            run_occ_pipeline(conn, limit=limit)

        if source in ("fed", "all-enriched"):
            from src.scrapers.fed_enforcement import run_fed_pipeline
            console.print("\n[bold]--- Federal Reserve Enforcement ---[/bold]")
            run_fed_pipeline(conn, limit=limit)

        if source in ("fdic-enforcement", "all-enriched"):
            from src.scrapers.fdic_enforcement import run_fdic_enforcement_pipeline
            console.print("\n[bold]--- FDIC Enforcement Orders ---[/bold]")
            run_fdic_enforcement_pipeline(conn, limit=limit)

        if source in ("hmda", "all-enriched"):
            from src.scrapers.hmda_downloader import run_hmda_pipeline
            console.print("\n[bold]--- HMDA Lending Data ---[/bold]")
            run_hmda_pipeline(conn, limit=limit)

        # Migrate CFPB enforcement into unified table if enrichment sources used
        if source in ("all-enriched", "occ", "fed", "fdic-enforcement"):
            from src.storage.database import migrate_cfpb_enforcement_to_regulatory
            console.print("\n[bold]--- Migrating CFPB enforcement to unified table ---[/bold]")
            migrated = migrate_cfpb_enforcement_to_regulatory(conn)
            console.print(f"  Migrated {migrated} CFPB enforcement actions")
    finally:
        conn.close()

    console.print("[bold green]Scrape complete.[/bold green]")


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--strategy",
    type=click.Choice(["exact", "normalized", "fuzzy", "all"]),
    default="all",
    help="Entity resolution strategy. Default: all.",
)
@click.option(
    "--threshold",
    type=float,
    default=85.0,
    help="Fuzzy match threshold (0-100). Default: 85.",
)
def normalize(strategy: str, threshold: float):
    """Run entity resolution to link complaints to institutions."""
    from src.storage.database import init_db
    from src.normalization.institutions import match_complaints_to_institutions

    console.print(
        f"[bold blue]Running entity resolution: strategy={strategy}, "
        f"threshold={threshold}[/bold blue]"
    )

    conn = init_db()
    try:
        stats = match_complaints_to_institutions(
            conn, fuzzy_threshold=int(threshold)
        )
        console.print(f"\n[bold green]Entity resolution complete.[/bold green]")
        for key, val in stats.items():
            console.print(f"  {key}: {val:,}" if isinstance(val, int) else f"  {key}: {val}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--fix/--no-fix",
    default=False,
    help="Attempt to fix validation issues automatically.",
)
@click.option(
    "--update-scores/--no-update-scores",
    default=True,
    help="Recompute quality scores. Default: yes.",
)
def validate(fix: bool, update_scores: bool):
    """Validate data quality and compute quality scores."""
    from src.storage.database import init_db, update_quality_scores

    console.print("[bold blue]Running validation...[/bold blue]")
    conn = init_db()

    try:
        if update_scores:
            console.print("  Recomputing quality scores...")
            updated = update_quality_scores(conn)
            console.print(f"  Updated {updated:,} institution scores.")

            # Show quality summary
            cursor = conn.execute(
                "SELECT AVG(quality_score), MIN(quality_score), MAX(quality_score) "
                "FROM financial_institutions"
            )
            row = cursor.fetchone()
            if row[0]:
                console.print(f"  Avg: {row[0]:.4f}, Min: {row[1]:.4f}, Max: {row[2]:.4f}")

            cursor = conn.execute(
                "SELECT COUNT(*) FROM financial_institutions WHERE quality_score >= 0.40"
            )
            above = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(*) FROM financial_institutions")
            total = cursor.fetchone()[0]
            pct = (above / total * 100) if total > 0 else 0
            console.print(f"  Above threshold (0.40): {above:,} / {total:,} ({pct:.1f}%)")
    finally:
        conn.close()

    console.print("[bold green]Validation complete.[/bold green]")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--format",
    "export_format",
    type=click.Choice(["csv", "json", "excel", "markdown", "all"]),
    default="all",
    help="Export format. Default: all.",
)
@click.option(
    "--output",
    type=click.Path(),
    default="data/exports/",
    help="Output directory for export files.",
)
@click.option(
    "--min-quality",
    type=float,
    default=0.0,
    help="Minimum quality score for exported records (0.0-1.0).",
)
def export(export_format: str, output: str, min_quality: float):
    """Export data in various formats."""
    from pathlib import Path
    from src.storage.database import init_db
    from src.export.exporter import run_export

    console.print(
        f"[bold blue]Exporting: format={export_format}, "
        f"output={output}[/bold blue]"
    )

    conn = init_db()
    try:
        run_export(conn, Path(output), export_format, min_quality)
    finally:
        conn.close()

    console.print("[bold green]Export complete.[/bold green]")


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--port",
    type=int,
    default=8501,
    help="Port for the Streamlit dashboard. Default: 8501.",
)
def dashboard(port: int):
    """Launch the Streamlit dashboard."""
    import subprocess
    import sys

    console.print(f"[bold blue]Launching dashboard on port {port}...[/bold blue]")
    subprocess.run(
        [
            sys.executable, "-m", "streamlit", "run",
            "src/dashboard/app.py",
            "--server.port", str(port),
            "--server.headless", "true",
        ],
        check=True,
    )


# ---------------------------------------------------------------------------
# risk-profiles
# ---------------------------------------------------------------------------

@cli.command("risk-profiles")
def risk_profiles():
    """Compute institution risk profiles from all available data."""
    from src.storage.database import init_db
    from src.validation.risk_scoring import run_risk_profile_pipeline

    console.print("[bold blue]Computing institution risk profiles...[/bold blue]")
    conn = init_db()
    try:
        stored = run_risk_profile_pipeline(conn)
        console.print(f"[bold green]Risk profiles complete: {stored:,} profiles[/bold green]")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--full/--no-full",
    default=False,
    help="Run the full pipeline end-to-end.",
)
@click.option(
    "--enriched/--no-enriched",
    default=False,
    help="Include enrichment sources (financials, multi-agency enforcement, HMDA).",
)
@click.option(
    "--source",
    type=click.Choice(["cfpb", "fdic", "cra", "enforcement", "all"]),
    default="all",
    help="Limit pipeline to a specific source.",
)
def pipeline(full: bool, enriched: bool, source: str):
    """Run the data pipeline: scrape -> normalize -> validate -> export."""
    from src.storage.database import init_db, update_quality_scores
    from src.scrapers.cfpb_downloader import run_cfpb_pipeline
    from src.scrapers.fdic_downloader import run_fdic_pipeline
    from src.scrapers.enforcement_scraper import run_enforcement_pipeline
    from src.scrapers.cra_downloader import run_cra_pipeline
    from src.normalization.institutions import match_complaints_to_institutions
    from src.export.exporter import run_export
    from pathlib import Path

    console.print(
        f"[bold blue]Running pipeline: full={full}, enriched={enriched}, source={source}[/bold blue]"
    )

    conn = init_db()
    try:
        if full or source in ("fdic", "all"):
            console.print("\n[bold]Stage 1: FDIC Institutions[/bold]")
            run_fdic_pipeline(conn, active_only=False)

        if full or source in ("cfpb", "all"):
            console.print("\n[bold]Stage 2: CFPB Complaints[/bold]")
            run_cfpb_pipeline(conn)

        if full or source in ("enforcement", "all"):
            console.print("\n[bold]Stage 3: Enforcement Actions[/bold]")
            run_enforcement_pipeline(conn)

        if full or source in ("cra", "all"):
            console.print("\n[bold]Stage 4: CRA Ratings[/bold]")
            run_cra_pipeline(conn)

        if full:
            console.print("\n[bold]Stage 5: Entity Resolution[/bold]")
            match_complaints_to_institutions(conn)

            console.print("\n[bold]Stage 6: Quality Scoring[/bold]")
            update_quality_scores(conn)

        # Enrichment stages
        if enriched or full:
            from src.scrapers.fdic_financials import run_financials_pipeline
            console.print("\n[bold]Stage 7: FDIC Financial Data[/bold]")
            run_financials_pipeline(conn)

            from src.scrapers.occ_enforcement import run_occ_pipeline
            from src.scrapers.fed_enforcement import run_fed_pipeline
            from src.scrapers.fdic_enforcement import run_fdic_enforcement_pipeline
            from src.storage.database import migrate_cfpb_enforcement_to_regulatory

            console.print("\n[bold]Stage 8: Multi-Agency Enforcement[/bold]")
            run_occ_pipeline(conn)
            run_fed_pipeline(conn)
            run_fdic_enforcement_pipeline(conn)
            migrated = migrate_cfpb_enforcement_to_regulatory(conn)
            console.print(f"  Migrated {migrated} CFPB actions to unified table")

            from src.scrapers.hmda_downloader import run_hmda_pipeline
            console.print("\n[bold]Stage 9: HMDA Lending Data[/bold]")
            run_hmda_pipeline(conn)

            from src.validation.risk_scoring import run_risk_profile_pipeline
            console.print("\n[bold]Stage 10: Risk Profiles[/bold]")
            run_risk_profile_pipeline(conn)

            console.print("\n[bold]Stage 11: Update Quality Scores[/bold]")
            update_quality_scores(conn)

        if full:
            console.print("\n[bold]Stage 12: Export[/bold]")
            run_export(conn, Path("data/exports/"), "all", 0.0)
    finally:
        conn.close()

    console.print("[bold green]Pipeline complete.[/bold green]")


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@cli.command()
def stats():
    """Display summary statistics for the current database."""
    from src.storage.database import init_db, get_stats

    console.print("[bold blue]Loading statistics...[/bold blue]")

    conn = init_db()
    db_stats = get_stats(conn)
    conn.close()

    # Summary table
    table = Table(title="CFPB Tracker - Database Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Total Complaints", f"{db_stats['total_complaints']:,}")
    table.add_row("Total Institutions", f"{db_stats['total_institutions']:,}")
    table.add_row("Total CRA Ratings", f"{db_stats['total_cra_ratings']:,}")
    table.add_row("Total Enforcement Actions", f"{db_stats['total_enforcement_actions']:,}")
    table.add_row("Total Cross-Links", f"{db_stats['total_cross_links']:,}")
    table.add_row("Avg Match Confidence", f"{db_stats['avg_match_confidence']:.4f}")
    table.add_row("Avg Quality Score", f"{db_stats['avg_quality_score']:.4f}")
    table.add_row(
        "Institutions w/ Enforcement",
        f"{db_stats['institutions_with_enforcement']:,}",
    )
    table.add_row("Financial Records", f"{db_stats.get('total_financials', 0):,}")
    table.add_row("Institutions w/ Financials", f"{db_stats.get('institutions_with_financials', 0):,}")
    table.add_row("Regulatory Enforcement (unified)", f"{db_stats.get('total_regulatory_enforcement', 0):,}")
    table.add_row("Risk Profiles", f"{db_stats.get('total_risk_profiles', 0):,}")
    table.add_row("HMDA Summaries", f"{db_stats.get('total_hmda_summaries', 0):,}")

    console.print(table)

    # Risk tier distribution
    if db_stats.get("risk_tier_distribution"):
        risk_table = Table(title="Risk Tier Distribution")
        risk_table.add_column("Tier", style="cyan")
        risk_table.add_column("Count", style="red", justify="right")
        for item in db_stats["risk_tier_distribution"]:
            risk_table.add_row(item["risk_tier"], f"{item['count']:,}")
        console.print(risk_table)

    # Enforcement by agency
    if db_stats.get("enforcement_by_agency"):
        agency_table = Table(title="Regulatory Enforcement by Agency")
        agency_table.add_column("Agency", style="cyan")
        agency_table.add_column("Actions", style="red", justify="right")
        for item in db_stats["enforcement_by_agency"]:
            agency_table.add_row(item["agency"], f"{item['count']:,}")
        console.print(agency_table)

    if db_stats["top_companies"]:
        co_table = Table(title="Top 10 Companies by Complaints")
        co_table.add_column("Company", style="cyan")
        co_table.add_column("Complaints", style="red", justify="right")
        for item in db_stats["top_companies"]:
            co_table.add_row(item["company"], f"{item['count']:,}")
        console.print(co_table)

    if db_stats["complaints_by_state"]:
        st_table = Table(title="Top 10 States by Complaints")
        st_table.add_column("State", style="cyan")
        st_table.add_column("Complaints", style="red", justify="right")
        for item in db_stats["complaints_by_state"]:
            st_table.add_row(item["state"], f"{item['count']:,}")
        console.print(st_table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
