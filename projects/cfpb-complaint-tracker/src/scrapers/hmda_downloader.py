"""
HMDA (Home Mortgage Disclosure Act) data downloader.

Downloads institution-level mortgage lending summaries from the FFIEC HMDA
data publication. Uses aggregate/summary data rather than loan-level records.

Source: https://ffiec.cfpb.gov/data-publication/

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import csv
import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console

console = Console()

# HMDA API endpoints
HMDA_API_BASE = "https://ffiec.cfpb.gov/v2/data-browser-api"
HMDA_SNAPSHOT_BASE = "https://ffiec.cfpb.gov/data-publication/snapshot-national-loan-level-dataset"
HMDA_FILERS_URL = "https://ffiec.cfpb.gov/v2/reporting/filers"

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"

USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)

REQUEST_DELAY = 1.0
MAX_RETRIES = 3


def _safe_float(value) -> Optional[float]:
    if value is None or value == "" or value == "NA" or value == "Exempt":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    if value is None or value == "" or value == "NA" or value == "Exempt":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def fetch_hmda_filers(year: int) -> list[dict]:
    """
    Fetch list of HMDA filers (institutions) for a given year.

    Args:
        year: Reporting year (e.g., 2022).

    Returns:
        List of filer dicts with LEI and institution name.
    """
    url = f"{HMDA_FILERS_URL}/{year}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            if response.status_code == 200:
                data = response.json()
                filers = data.get("institutions", [])
                console.print(f"  Found {len(filers)} HMDA filers for {year}")
                return filers
            elif response.status_code == 404:
                console.print(f"  [yellow]No HMDA filer data for year {year}[/yellow]")
                return []
            else:
                response.raise_for_status()
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep((attempt + 1) * 2)
            else:
                console.print(f"  [yellow]HMDA filer fetch failed: {e}[/yellow]")
                return []

    return []


def download_hmda_aggregate_csv(year: int) -> Optional[Path]:
    """
    Download HMDA aggregate CSV data for a year.

    Uses the HMDA data browser API to get aggregate statistics.

    Args:
        year: Reporting year.

    Returns:
        Path to downloaded CSV file, or None if download failed.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"hmda_{year}_aggregate.csv"

    if cache_file.exists() and cache_file.stat().st_size > 0:
        console.print(f"  Using cached HMDA data for {year}")
        return cache_file

    # Try the HMDA data browser aggregate endpoint
    url = f"{HMDA_API_BASE}/view/csv?years={year}"
    headers = {"User-Agent": USER_AGENT}

    console.print(f"  Downloading HMDA aggregate data for {year}...")

    try:
        response = requests.get(url, headers=headers, timeout=120, stream=True)
        if response.status_code == 200:
            with open(cache_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            console.print(f"  [green]Downloaded HMDA data for {year}[/green]")
            return cache_file
        else:
            console.print(f"  [yellow]HMDA aggregate download returned {response.status_code}[/yellow]")
    except requests.RequestException as e:
        console.print(f"  [yellow]HMDA download failed: {e}[/yellow]")

    return None


def build_institution_summaries_from_filers(
    year: int,
    institution_lookup: Optional[dict] = None,
) -> list[dict]:
    """
    Build institution-level HMDA summaries from filer data.

    The HMDA filers endpoint provides basic aggregate data per institution.

    Args:
        year: Reporting year.
        institution_lookup: Optional dict mapping institution names to CERT numbers.

    Returns:
        List of HMDA summary dicts ready for database storage.
    """
    filers = fetch_hmda_filers(year)
    if not filers:
        return []

    summaries = []
    for filer in filers:
        lei = filer.get("lei", "")
        name = filer.get("name") or filer.get("respondent", {}).get("name", "")

        if not lei or not name:
            continue

        # Look up CERT number if we have a mapping
        cert_number = None
        if institution_lookup:
            # Try exact match first, then normalized
            cert_number = institution_lookup.get(name.upper())
            if cert_number is None:
                # Try partial match
                for inst_name, cert in institution_lookup.items():
                    if name.upper() in inst_name or inst_name in name.upper():
                        cert_number = cert
                        break

        # Compute quality score based on data completeness
        quality = 0.3  # Base for having lei + name + year
        if cert_number:
            quality += 0.3

        summaries.append({
            "lei": lei,
            "cert_number": cert_number,
            "institution_name": name,
            "report_year": year,
            "total_applications": None,
            "total_originations": None,
            "total_denials": None,
            "denial_rate": None,
            "avg_loan_amount": None,
            "avg_interest_rate": None,
            "total_loan_volume": None,
            "lending_states": None,
            "quality_score": quality,
        })

    console.print(f"  Built {len(summaries)} HMDA institution summaries for {year}")
    return summaries


def parse_hmda_csv_to_summaries(
    csv_path: Path,
    year: int,
    institution_lookup: Optional[dict] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Parse a HMDA CSV file into institution-level summaries.

    Aggregates loan-level records by LEI into institution summaries.

    Args:
        csv_path: Path to the HMDA CSV file.
        year: Reporting year.
        institution_lookup: Optional dict mapping names to CERT numbers.
        limit: Max records to process from the CSV.

    Returns:
        List of HMDA summary dicts.
    """
    # Aggregate per-institution statistics
    institution_data = {}
    records_processed = 0

    console.print(f"  Parsing HMDA CSV: {csv_path.name}...")

    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f, delimiter='|')

        for row in reader:
            lei = row.get("lei", "").strip()
            if not lei:
                continue

            if lei not in institution_data:
                institution_data[lei] = {
                    "lei": lei,
                    "institution_name": row.get("respondent_name", "").strip(),
                    "applications": 0,
                    "originations": 0,
                    "denials": 0,
                    "total_amount": 0.0,
                    "total_rate": 0.0,
                    "rate_count": 0,
                    "states": set(),
                }

            inst = institution_data[lei]
            action = _safe_int(row.get("action_taken"))

            if action is not None:
                inst["applications"] += 1
                if action == 1:  # Originated
                    inst["originations"] += 1
                    amount = _safe_float(row.get("loan_amount"))
                    if amount:
                        inst["total_amount"] += amount
                elif action == 3:  # Denied
                    inst["denials"] += 1

            rate = _safe_float(row.get("interest_rate"))
            if rate and 0 < rate < 30:  # Reasonable interest rate range
                inst["total_rate"] += rate
                inst["rate_count"] += 1

            state = row.get("state_code", "").strip()
            if state:
                inst["states"].add(state)

            records_processed += 1
            if limit and records_processed >= limit:
                break

            if records_processed % 500000 == 0:
                console.print(f"  Processed {records_processed:,} HMDA records, "
                            f"{len(institution_data)} institutions...")

    # Convert aggregates to summary records
    summaries = []
    for lei, data in institution_data.items():
        apps = data["applications"]
        denial_rate = data["denials"] / apps if apps > 0 else None
        avg_amount = data["total_amount"] / data["originations"] if data["originations"] > 0 else None
        avg_rate = data["total_rate"] / data["rate_count"] if data["rate_count"] > 0 else None

        cert_number = None
        if institution_lookup:
            name_upper = data["institution_name"].upper()
            cert_number = institution_lookup.get(name_upper)

        quality = 0.3
        if apps > 0:
            quality += 0.2
        if data["originations"] > 0:
            quality += 0.1
        if avg_rate is not None:
            quality += 0.1
        if cert_number:
            quality += 0.2
        if len(data["states"]) > 0:
            quality += 0.1

        summaries.append({
            "lei": lei,
            "cert_number": cert_number,
            "institution_name": data["institution_name"],
            "report_year": year,
            "total_applications": apps,
            "total_originations": data["originations"],
            "total_denials": data["denials"],
            "denial_rate": round(denial_rate, 4) if denial_rate is not None else None,
            "avg_loan_amount": round(avg_amount, 2) if avg_amount is not None else None,
            "avg_interest_rate": round(avg_rate, 3) if avg_rate is not None else None,
            "total_loan_volume": round(data["total_amount"], 2) if data["total_amount"] > 0 else None,
            "lending_states": json.dumps(sorted(data["states"])) if data["states"] else None,
            "quality_score": round(quality, 2),
        })

    console.print(f"  Parsed {records_processed:,} HMDA records into {len(summaries)} institution summaries")
    return summaries


def build_institution_name_lookup(db_conn) -> dict:
    """
    Build a lookup dict mapping uppercase institution names to CERT numbers.

    Args:
        db_conn: Database connection.

    Returns:
        Dict of {UPPERCASE_NAME: cert_number}.
    """
    cursor = db_conn.execute(
        "SELECT cert_number, institution_name FROM financial_institutions"
    )
    lookup = {}
    for row in cursor.fetchall():
        name = row["institution_name"]
        if name:
            lookup[name.upper()] = row["cert_number"]
    return lookup


def run_hmda_pipeline(
    db_conn,
    years: Optional[list[int]] = None,
    limit: Optional[int] = None,
) -> int:
    """
    Run the HMDA data download and store pipeline.

    Downloads filer data for the specified years and builds
    institution-level summaries.

    Args:
        db_conn: Active database connection.
        years: List of reporting years. Defaults to [2022, 2023].
        limit: Max records per year.

    Returns:
        Total number of HMDA summaries stored.
    """
    from src.storage.database import store_hmda_summaries_batch, start_pipeline_run, complete_pipeline_run

    if years is None:
        years = [2022, 2023]

    run_id = start_pipeline_run(db_conn, "hmda_lending")
    total_stored = 0

    try:
        institution_lookup = build_institution_name_lookup(db_conn)
        console.print(f"  Built institution lookup with {len(institution_lookup)} entries")

        for year in years:
            console.print(f"\n  [bold]Processing HMDA data for {year}...[/bold]")

            # Try aggregate CSV first
            csv_path = download_hmda_aggregate_csv(year)
            if csv_path and csv_path.exists():
                summaries = parse_hmda_csv_to_summaries(
                    csv_path, year, institution_lookup, limit=limit
                )
            else:
                # Fall back to filer data
                summaries = build_institution_summaries_from_filers(
                    year, institution_lookup
                )

            if summaries:
                stored = store_hmda_summaries_batch(db_conn, summaries)
                total_stored += stored
                console.print(f"  Stored {stored:,} HMDA summaries for {year}")

            time.sleep(REQUEST_DELAY)

        complete_pipeline_run(db_conn, run_id, total_stored)
        console.print(f"\n  [green]HMDA pipeline complete: {total_stored:,} summaries stored[/green]")
        return total_stored

    except Exception as e:
        complete_pipeline_run(db_conn, run_id, total_stored, status="failed", notes=str(e))
        raise
