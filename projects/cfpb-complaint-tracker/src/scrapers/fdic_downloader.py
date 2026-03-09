"""
FDIC BankFind Suite API downloader.

Fetches institution data from the FDIC public API, paginates through
all results, and stores records in the SQLite database.

API endpoint: https://api.fdic.gov/banks/institutions
API docs: https://banks.data.fdic.gov/docs/

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import time
from pathlib import Path
from typing import Generator, Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FDIC_API_BASE = "https://api.fdic.gov/banks/institutions"

# Actual FDIC API field names (verified against live API)
FDIC_FIELDS = [
    "NAME",       # Institution name (API uses NAME, not INSTNAME)
    "CERT",       # FDIC certificate number (unique ID)
    "RSSDID",     # RSSD ID (Federal Reserve ID)
    "CITY",       # City
    "STNAME",     # State name
    "ASSET",      # Total assets (thousands)
    "INSTCAT",    # Institution category
    "INSTAG",     # Institution subagency
    "REGAGNT",    # Primary federal regulator
    "ACTIVE",     # Active status (1 = active)
    "ESTYMD",     # Established date
    "WEBADDR",    # Website URL
    "ZIP",        # ZIP code
    "REPDTE",     # Report date
]

# Map API field names to database column names
FIELD_MAP = {
    "NAME": "institution_name",
    "CERT": "cert_number",
    "RSSDID": "rssd_id",
    "CITY": "city",
    "STNAME": "state",
    "ASSET": "total_assets",
    "INSTCAT": "institution_class",
    "REGAGNT": "regulator",
    "ACTIVE": "active",
    "ESTYMD": "established_date",
    "WEBADDR": "fdic_url",
    "ZIP": "zip_code",
}

USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)

PAGE_SIZE = 10000  # FDIC API supports up to 10000 per page
REQUEST_DELAY = 0.5  # seconds between API calls
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# API Interaction
# ---------------------------------------------------------------------------

def fetch_institutions_page(
    offset: int = 0,
    limit: int = PAGE_SIZE,
    filters: Optional[str] = None,
) -> dict:
    """
    Fetch a single page of institution data from the FDIC API.

    Args:
        offset: Number of records to skip.
        limit: Number of records per page (max 10000).
        filters: Optional FDIC API filter string.

    Returns:
        dict with keys 'data' (list of institution records) and 'totals'
        (metadata including total record count).

    Raises:
        requests.HTTPError: If the API request fails after retries.
    """
    params = {
        "fields": ",".join(FDIC_FIELDS),
        "limit": limit,
        "offset": offset,
        "sort_by": "CERT",
        "sort_order": "ASC",
    }
    if filters:
        params["filters"] = filters

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                FDIC_API_BASE, params=params, headers=headers, timeout=30
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, requests.HTTPError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 2
                console.print(f"  [yellow]Retry {attempt + 1}/{MAX_RETRIES} after {wait}s: {e}[/yellow]")
                time.sleep(wait)
            else:
                raise


def _map_institution_record(raw: dict) -> dict:
    """
    Map a raw FDIC API record to the database schema.

    Args:
        raw: Raw record from the FDIC API response (nested under 'data').

    Returns:
        dict with keys matching the financial_institutions table columns.
    """
    data = raw.get("data", raw)
    record = {}

    for api_field, db_field in FIELD_MAP.items():
        value = data.get(api_field)
        if value is not None and str(value).strip():
            record[db_field] = value
        else:
            record[db_field] = None

    # Type conversions
    if record.get("cert_number") is not None:
        record["cert_number"] = int(record["cert_number"])
    if record.get("rssd_id") is not None:
        try:
            record["rssd_id"] = int(record["rssd_id"])
        except (ValueError, TypeError):
            record["rssd_id"] = None
    if record.get("total_assets") is not None:
        try:
            # FDIC reports assets in thousands
            record["total_assets"] = float(record["total_assets"])
        except (ValueError, TypeError):
            record["total_assets"] = None
    if record.get("active") is not None:
        record["active"] = 1 if str(record["active"]) == "1" else 0

    # canonical_name will be set during normalization
    record["canonical_name"] = None

    return record


# ---------------------------------------------------------------------------
# Download All
# ---------------------------------------------------------------------------

def download_institutions(
    limit: Optional[int] = None,
    active_only: bool = False,
) -> Generator[dict, None, None]:
    """
    Download all institutions from the FDIC API, paginating through results.

    Yields mapped institution records one at a time. Handles pagination
    automatically and respects rate limits.

    Args:
        limit: Maximum total records to download. None for all.
        active_only: If True, only download active institutions.

    Yields:
        dict: An institution record with keys matching the database schema.

    Raises:
        requests.HTTPError: If any API request fails after retries.
    """
    filters = "ACTIVE:1" if active_only else None
    offset = 0
    total_yielded = 0

    console.print("  Fetching institutions from FDIC BankFind API...")

    # Get total count from first page
    first_page = fetch_institutions_page(offset=0, limit=1, filters=filters)
    total_available = first_page.get("totals", {}).get("count", 0)
    console.print(f"  Total institutions available: {total_available:,}")

    while True:
        page_data = fetch_institutions_page(offset=offset, filters=filters)
        records = page_data.get("data", [])
        if not records:
            break

        for raw in records:
            record = _map_institution_record(raw)
            if record.get("cert_number") is not None:
                yield record
                total_yielded += 1
                if limit and total_yielded >= limit:
                    console.print(f"  Reached limit of {limit:,} records.")
                    return

        console.print(f"  Downloaded {total_yielded:,} / {total_available:,} institutions...")
        offset += len(records)

        if len(records) < PAGE_SIZE:
            break

        time.sleep(REQUEST_DELAY)

    console.print(f"  [green]Download complete: {total_yielded:,} institutions[/green]")


# ---------------------------------------------------------------------------
# Pipeline Integration
# ---------------------------------------------------------------------------

def run_fdic_pipeline(
    db_conn,
    limit: Optional[int] = None,
    active_only: bool = False,
    batch_size: int = 1000,
) -> int:
    """
    Run the full FDIC download-and-store pipeline.

    1. Paginate through FDIC API
    2. Map records to database schema
    3. Store in batches

    Args:
        db_conn: Active SQLite database connection.
        limit: Maximum records to process.
        active_only: Only download active institutions.
        batch_size: Number of records per database batch insert.

    Returns:
        Total number of records stored.
    """
    from src.storage.database import store_institutions_batch, start_pipeline_run, complete_pipeline_run

    run_id = start_pipeline_run(db_conn, "fdic_institutions")
    try:
        batch = []
        total = 0
        for institution in download_institutions(limit=limit, active_only=active_only):
            batch.append(institution)
            if len(batch) >= batch_size:
                store_institutions_batch(db_conn, batch)
                total += len(batch)
                batch = []
        if batch:
            store_institutions_batch(db_conn, batch)
            total += len(batch)
        complete_pipeline_run(db_conn, run_id, total)
        console.print(f"  [green]Stored {total:,} institutions in database[/green]")
        return total
    except Exception as e:
        complete_pipeline_run(db_conn, run_id, 0, status="failed", notes=str(e))
        raise
