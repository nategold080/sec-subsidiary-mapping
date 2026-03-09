"""
FDIC Financial Data downloader.

Fetches quarterly Call Report financial data from the FDIC API
for all institutions in the database.

API endpoint: https://api.fdic.gov/financials
Docs: https://banks.data.fdic.gov/docs/

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import time
from typing import Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FDIC_FINANCIALS_API = "https://banks.data.fdic.gov/api/financials"

# Key financial fields from the FDIC SDI / Call Reports
FINANCIAL_FIELDS = [
    "CERT",        # Certificate number
    "REPDTE",      # Report date (YYYYMMDD)
    "ASSET",       # Total assets (thousands)
    "DEP",         # Total deposits (thousands)
    "LNLSNET",    # Net loans and leases (thousands)
    "NETINC",      # Net income (thousands)
    "NITEFPCT",    # Net interest margin (%)
    "RBCRWAJ",     # Risk-based capital ratio (%)
    "IDT1RWAJR",   # Tier 1 risk-based capital ratio (%)
    "REPTE1",      # Leverage ratio / equity capital to assets (%)
    "ROA",         # Return on assets (%)
    "ROE",         # Return on equity (%)
    "NCLNLSR",     # Noncurrent loans to loans (%)
    "EEFFR",       # Efficiency ratio (%)
    "OFFDOM",      # Number of domestic offices
    "NUMEMP",      # Number of employees
]

USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)

REQUEST_DELAY = 0.3
MAX_RETRIES = 3
PAGE_SIZE = 10000


# ---------------------------------------------------------------------------
# API Interaction
# ---------------------------------------------------------------------------

def fetch_financials_page(
    offset: int = 0,
    limit: int = PAGE_SIZE,
    filters: Optional[str] = None,
    sort_by: str = "REPDTE",
    sort_order: str = "DESC",
) -> dict:
    """
    Fetch a page of financial data from the FDIC API.

    Args:
        offset: Records to skip.
        limit: Records per page.
        filters: FDIC API filter string (e.g., "CERT:3511").
        sort_by: Field to sort by.
        sort_order: ASC or DESC.

    Returns:
        API response as dict with 'data' and 'totals' keys.
    """
    params = {
        "fields": ",".join(FINANCIAL_FIELDS),
        "limit": limit,
        "offset": offset,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    if filters:
        params["filters"] = filters

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(
                FDIC_FINANCIALS_API, params=params, headers=headers, timeout=30
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


def _safe_float(value) -> Optional[float]:
    """Convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    """Convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _map_financial_record(raw: dict) -> dict:
    """
    Map a raw FDIC financials API record to our database schema.

    Args:
        raw: Raw record from the API (may have nested 'data' key).

    Returns:
        dict matching institution_financials table columns.
    """
    data = raw.get("data", raw)

    # Compute quality score for this financial record
    fields_present = sum(1 for f in [
        "ASSET", "DEP", "LNLSNET", "NETINC", "ROA", "ROE",
        "IDT1RWAJR", "REPTE1", "NCLNLSR", "EEFFR"
    ] if data.get(f) is not None)
    quality = round(fields_present / 10.0, 2)

    return {
        "cert_number": _safe_int(data.get("CERT")),
        "report_date": str(data.get("REPDTE", "")),
        "total_assets": _safe_float(data.get("ASSET")),
        "total_deposits": _safe_float(data.get("DEP")),
        "total_loans": _safe_float(data.get("LNLSNET")),
        "net_income": _safe_float(data.get("NETINC")),
        "net_interest_income": _safe_float(data.get("NITEFPCT")),
        "tier1_capital_ratio": _safe_float(data.get("IDT1RWAJR")),
        "leverage_ratio": _safe_float(data.get("REPTE1")),
        "roa": _safe_float(data.get("ROA")),
        "roe": _safe_float(data.get("ROE")),
        "noncurrent_loans_pct": _safe_float(data.get("NCLNLSR")),
        "efficiency_ratio": _safe_float(data.get("EEFFR")),
        "num_offices": _safe_int(data.get("OFFDOM")),
        "num_employees": _safe_int(data.get("NUMEMP")),
        "quality_score": quality,
    }


# ---------------------------------------------------------------------------
# Bulk Download
# ---------------------------------------------------------------------------

def download_financials_for_cert(
    cert_number: int,
    quarters: int = 8,
) -> list[dict]:
    """
    Download financial data for a single institution.

    Args:
        cert_number: FDIC certificate number.
        quarters: Number of quarterly reports to fetch (default: 8 = 2 years).

    Returns:
        List of mapped financial records.
    """
    result = fetch_financials_page(
        filters=f"CERT:{cert_number}",
        limit=quarters,
        sort_by="REPDTE",
        sort_order="DESC",
    )

    records = []
    for raw in result.get("data", []):
        mapped = _map_financial_record(raw)
        if mapped["cert_number"] is not None and mapped["report_date"]:
            records.append(mapped)

    return records


def download_all_financials_bulk(
    report_date: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Download financial data for all institutions in bulk.

    If report_date is specified, fetches data for that specific quarter.
    Otherwise fetches the most recent available quarter.

    Args:
        report_date: Specific report date (YYYYMMDD format). None for latest.
        limit: Maximum records to fetch. None for all.

    Returns:
        List of mapped financial records.
    """
    filters = f"REPDTE:{report_date}" if report_date else None
    offset = 0
    all_records = []
    total_available = None

    console.print("  Fetching financial data from FDIC API (bulk)...")

    while True:
        page_data = fetch_financials_page(
            offset=offset,
            limit=PAGE_SIZE,
            filters=filters,
            sort_by="CERT",
            sort_order="ASC",
        )

        if total_available is None:
            total_available = page_data.get("totals", {}).get("count", 0)
            console.print(f"  Total financial records available: {total_available:,}")

        records = page_data.get("data", [])
        if not records:
            break

        for raw in records:
            mapped = _map_financial_record(raw)
            if mapped["cert_number"] is not None and mapped["report_date"]:
                all_records.append(mapped)
                if limit and len(all_records) >= limit:
                    return all_records

        console.print(f"  Downloaded {len(all_records):,} / {total_available:,} financial records...")
        offset += len(records)

        if len(records) < PAGE_SIZE:
            break

        time.sleep(REQUEST_DELAY)

    console.print(f"  [green]Download complete: {len(all_records):,} financial records[/green]")
    return all_records


def get_latest_report_dates(n: int = 4) -> list[str]:
    """
    Discover the N most recent report dates from the FDIC API.

    Args:
        n: Number of report dates to return.

    Returns:
        List of report date strings (YYYYMMDD) in descending order.
    """
    result = fetch_financials_page(
        limit=1,
        sort_by="REPDTE",
        sort_order="DESC",
    )

    dates = set()
    # Get the latest date from first record
    for raw in result.get("data", []):
        data = raw.get("data", raw)
        repdte = data.get("REPDTE")
        if repdte:
            dates.add(str(repdte))

    if not dates:
        return []

    # Get a broader sample to find multiple dates
    result = fetch_financials_page(
        limit=100,
        sort_by="REPDTE",
        sort_order="DESC",
    )
    for raw in result.get("data", []):
        data = raw.get("data", raw)
        repdte = data.get("REPDTE")
        if repdte:
            dates.add(str(repdte))

    return sorted(dates, reverse=True)[:n]


# ---------------------------------------------------------------------------
# Asset Tier Classification
# ---------------------------------------------------------------------------

def classify_asset_tier(total_assets_thousands: Optional[float]) -> str:
    """
    Classify an institution by asset size tier.

    Asset thresholds (in thousands as reported by FDIC):
    - G-SIB: >= $250B ($250,000,000 thousands)
    - Large: >= $10B ($10,000,000 thousands)
    - Regional: >= $1B ($1,000,000 thousands)
    - Community: < $1B

    Args:
        total_assets_thousands: Total assets in thousands (FDIC reporting unit).

    Returns:
        Asset tier string: 'gsib', 'large', 'regional', or 'community'.
    """
    if total_assets_thousands is None:
        return "unknown"

    if total_assets_thousands >= 250_000_000:
        return "gsib"
    elif total_assets_thousands >= 10_000_000:
        return "large"
    elif total_assets_thousands >= 1_000_000:
        return "regional"
    else:
        return "community"


# ---------------------------------------------------------------------------
# Pipeline Integration
# ---------------------------------------------------------------------------

def run_financials_pipeline(
    db_conn,
    quarters: int = 4,
    limit: Optional[int] = None,
) -> int:
    """
    Run the full FDIC financials download-and-store pipeline.

    Downloads the most recent N quarters of financial data for all
    institutions, then stores them in the database.

    Args:
        db_conn: Active SQLite database connection.
        quarters: Number of quarterly periods to download.
        limit: Max records to download per quarter. None for all.

    Returns:
        Total number of financial records stored.
    """
    from src.storage.database import store_financials_batch, start_pipeline_run, complete_pipeline_run

    run_id = start_pipeline_run(db_conn, "fdic_financials")
    total_stored = 0

    try:
        # Discover latest report dates
        console.print("  Discovering latest report dates...")
        report_dates = get_latest_report_dates(quarters)

        if not report_dates:
            console.print("  [yellow]No report dates found. Downloading latest available data.[/yellow]")
            records = download_all_financials_bulk(limit=limit)
            if records:
                total_stored = store_financials_batch(db_conn, records)
        else:
            console.print(f"  Found {len(report_dates)} report dates: {', '.join(report_dates)}")

            for report_date in report_dates:
                console.print(f"\n  [bold]Downloading financials for {report_date}...[/bold]")
                records = download_all_financials_bulk(
                    report_date=report_date,
                    limit=limit,
                )
                if records:
                    stored = store_financials_batch(db_conn, records)
                    total_stored += stored
                    console.print(f"  Stored {stored:,} records for {report_date}")

                time.sleep(REQUEST_DELAY)

        complete_pipeline_run(db_conn, run_id, total_stored)
        console.print(f"\n  [green]Financial data pipeline complete: {total_stored:,} records stored[/green]")
        return total_stored

    except Exception as e:
        complete_pipeline_run(db_conn, run_id, total_stored, status="failed", notes=str(e))
        raise
