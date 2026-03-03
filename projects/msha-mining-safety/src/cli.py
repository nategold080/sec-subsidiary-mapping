"""CLI for MSHA Mining Safety & Enforcement Tracker."""

import click

from .storage.database import init_db, get_connection, get_stats
from .storage.database import (
    upsert_mines_batch, insert_accidents_batch, insert_inspections_batch,
    insert_violations_batch, insert_assessed_batch, insert_penalties_batch,
    upsert_profiles_batch,
)
from .scrapers.downloader import (
    download_dataset, parse_mines, parse_accidents, parse_inspections,
    parse_violations, parse_assessed_violations, parse_penalties,
)
from .validation.quality import (
    score_mine, score_accident, score_inspection,
    score_violation, score_assessed_violation, score_penalty,
)
from .normalization.operators import build_operator_profiles
from .export.exporter import export_all


@click.group()
def cli():
    """MSHA Mining Safety & Enforcement Tracker."""
    pass


@cli.command()
def init():
    """Initialize the database."""
    init_db()
    click.echo("Database initialized.")


@cli.command("scrape-mines")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_mines(force):
    """Download and import mines data."""
    path = download_dataset("mines", force=force)
    records = parse_mines(path)
    for r in records:
        r["quality_score"] = score_mine(r)
    conn, _ = get_connection()
    try:
        upsert_mines_batch(records, conn=conn)
        click.echo(f"Imported {len(records):,} mines.")
    finally:
        conn.close()


@cli.command("scrape-accidents")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_accidents(force):
    """Download and import accidents/injuries data."""
    path = download_dataset("accidents", force=force)
    records = parse_accidents(path)
    for r in records:
        r["quality_score"] = score_accident(r)
    conn, _ = get_connection()
    try:
        BATCH = 50_000
        total = 0
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            insert_accidents_batch(batch, conn=conn)
            total += len(batch)
            click.echo(f"  {total:,} / {len(records):,} accidents imported...")
        click.echo(f"Imported {total:,} accidents.")
    finally:
        conn.close()


@cli.command("scrape-inspections")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_inspections(force):
    """Download and import inspections data."""
    path = download_dataset("inspections", force=force)
    records = parse_inspections(path)
    for r in records:
        r["quality_score"] = score_inspection(r)
    conn, _ = get_connection()
    try:
        BATCH = 50_000
        total = 0
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            insert_inspections_batch(batch, conn=conn)
            total += len(batch)
            click.echo(f"  {total:,} / {len(records):,} inspections imported...")
        click.echo(f"Imported {total:,} inspections.")
    finally:
        conn.close()


@cli.command("scrape-violations")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_violations(force):
    """Download and import violations data."""
    path = download_dataset("violations", force=force)
    records = parse_violations(path)
    for r in records:
        r["quality_score"] = score_violation(r)
    conn, _ = get_connection()
    try:
        BATCH = 50_000
        total = 0
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            insert_violations_batch(batch, conn=conn)
            total += len(batch)
            click.echo(f"  {total:,} / {len(records):,} violations imported...")
        click.echo(f"Imported {total:,} violations.")
    finally:
        conn.close()


@cli.command("scrape-assessed")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_assessed(force):
    """Download and import assessed violations data."""
    path = download_dataset("assessed_violations", force=force)
    records = parse_assessed_violations(path)
    for r in records:
        r["quality_score"] = score_assessed_violation(r)
    conn, _ = get_connection()
    try:
        BATCH = 50_000
        total = 0
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            insert_assessed_batch(batch, conn=conn)
            total += len(batch)
            click.echo(f"  {total:,} / {len(records):,} assessed violations imported...")
        click.echo(f"Imported {total:,} assessed violations.")
    finally:
        conn.close()


@cli.command("scrape-penalties")
@click.option("--force", is_flag=True, help="Force re-download")
def scrape_penalties(force):
    """Download and import civil penalty docket data."""
    path = download_dataset("penalties", force=force)
    records = parse_penalties(path)
    for r in records:
        r["quality_score"] = score_penalty(r)
    conn, _ = get_connection()
    try:
        BATCH = 50_000
        total = 0
        for i in range(0, len(records), BATCH):
            batch = records[i : i + BATCH]
            insert_penalties_batch(batch, conn=conn)
            total += len(batch)
            click.echo(f"  {total:,} / {len(records):,} penalties imported...")
        click.echo(f"Imported {total:,} penalties.")
    finally:
        conn.close()


@cli.command("build-profiles")
def build_profiles():
    """Build operator safety profiles from aggregated data."""
    conn, _ = get_connection()
    try:
        profiles = build_operator_profiles(conn)
        upsert_profiles_batch(profiles, conn=conn)
        click.echo(f"Built {len(profiles):,} operator profiles.")
    finally:
        conn.close()


@cli.command()
def export():
    """Export data to CSV, JSON, and Markdown."""
    conn, _ = get_connection()
    try:
        results = export_all(conn)
        for k, v in results.items():
            click.echo(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
    finally:
        conn.close()


@cli.command()
def stats():
    """Show database statistics."""
    s = get_stats()
    click.echo("\n=== MSHA Mining Safety Tracker Statistics ===\n")
    for k, v in s.items():
        if isinstance(v, float):
            click.echo(f"  {k}: ${v:,.2f}" if "penalt" in k.lower() else f"  {k}: {v:,.3f}")
        elif isinstance(v, int):
            click.echo(f"  {k}: {v:,}")
        else:
            click.echo(f"  {k}: {v}")
    click.echo()


@cli.command()
@click.option("--skip-violations", is_flag=True, help="Skip large violations datasets")
def pipeline(skip_violations):
    """Run the full pipeline."""
    from click.testing import CliRunner
    runner = CliRunner()

    steps = ["init", "scrape-mines", "scrape-accidents", "scrape-inspections"]
    if not skip_violations:
        steps += ["scrape-violations", "scrape-assessed"]
    steps += ["scrape-penalties", "build-profiles", "export", "stats"]

    for step in steps:
        click.echo(f"\n{'='*60}")
        click.echo(f"  Running: {step}")
        click.echo(f"{'='*60}\n")
        result = runner.invoke(cli, [step])
        if result.output:
            click.echo(result.output)
        if result.exit_code != 0:
            click.echo(f"ERROR in {step}: {result.exception}")
            if result.exception:
                import traceback
                traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
            return


@cli.command()
def dashboard():
    """Launch the Streamlit dashboard."""
    import subprocess
    subprocess.run(["streamlit", "run", "src/dashboard/app.py"])


if __name__ == "__main__":
    cli()
