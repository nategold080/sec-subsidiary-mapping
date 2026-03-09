"""
CFPB Consumer Complaint bulk data downloader.

Downloads the full complaints CSV from the CFPB public data portal,
extracts from ZIP, and parses records in a streaming fashion to
handle the 600MB+ file without excessive memory use.

Data source: https://files.consumerfinance.gov/ccdb/complaints.csv.zip
API docs: https://www.consumerfinance.gov/data-research/consumer-complaints/

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import csv
import io
import os
import zipfile
from pathlib import Path
from typing import Generator, Optional

import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CFPB_COMPLAINTS_URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
ZIP_FILENAME = "complaints.csv.zip"
CSV_FILENAME = "complaints.csv"

# Mapping from CSV column headers to database field names
CSV_FIELD_MAP = {
    "Complaint ID": "complaint_id",
    "Date received": "date_received",
    "Product": "product",
    "Sub-product": "sub_product",
    "Issue": "issue",
    "Sub-issue": "sub_issue",
    "Consumer complaint narrative": "consumer_narrative",
    "Company public response": "company_public_response",
    "Company": "company",
    "State": "state",
    "ZIP code": "zip_code",
    "Tags": "tags",
    "Consumer consent provided?": "consumer_consent_provided",
    "Submitted via": "submitted_via",
    "Date sent to company": "date_sent_to_company",
    "Company response to consumer": "company_response",
    "Timely response?": "timely_response",
    "Consumer disputed?": "consumer_disputed",
}

USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_complaints(
    url: str = CFPB_COMPLAINTS_URL,
    cache_dir: Optional[Path] = None,
    force_download: bool = False,
) -> Path:
    """
    Download the CFPB complaints bulk CSV ZIP file.

    Uses streaming download to handle the large file size (~600MB).
    Caches the ZIP file locally to avoid re-downloading.

    Args:
        url: URL of the ZIP file to download.
        cache_dir: Directory to store the downloaded ZIP. Defaults to data/cache/.
        force_download: If True, re-download even if cached file exists.

    Returns:
        Path to the downloaded ZIP file.

    Raises:
        requests.HTTPError: If the download fails.
        IOError: If the file cannot be written.
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR

    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / ZIP_FILENAME

    if zip_path.exists() and not force_download:
        console.print(f"  Using cached file: {zip_path}")
        return zip_path

    console.print(f"  Downloading from {url}...")

    import time as _time

    max_retries = 5
    for attempt in range(max_retries):
        headers = {"User-Agent": USER_AGENT}
        # Resume partial download if possible
        downloaded = 0
        mode = "wb"
        partial_path = zip_path.with_suffix(".zip.partial")
        if partial_path.exists() and attempt > 0:
            downloaded = partial_path.stat().st_size
            headers["Range"] = f"bytes={downloaded}-"
            mode = "ab"
            console.print(f"  Resuming from {downloaded // (1024*1024)} MB (attempt {attempt+1})...")

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()

            if response.status_code == 206:
                # Partial content — resuming
                total_size = downloaded + int(response.headers.get("content-length", 0))
            else:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                mode = "wb"

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total} MB"),
            ) as progress:
                task = progress.add_task(
                    "Downloading complaints...",
                    total=total_size // (1024 * 1024) if total_size else None,
                )
                progress.update(task, completed=downloaded // (1024 * 1024))
                with open(partial_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, completed=downloaded // (1024 * 1024))

            # Download complete — rename to final path
            partial_path.rename(zip_path)
            file_size_mb = zip_path.stat().st_size / (1024 * 1024)
            console.print(f"  Downloaded {file_size_mb:.1f} MB to {zip_path}")
            return zip_path

        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                console.print(f"  [yellow]Download interrupted: {e}. Retrying in {wait}s...[/yellow]")
                _time.sleep(wait)
            else:
                raise

    return zip_path


def extract_csv_from_zip(
    zip_path: Path,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Extract the complaints CSV from the downloaded ZIP file.

    Args:
        zip_path: Path to the ZIP file.
        output_dir: Directory to extract the CSV to. Defaults to data/raw/.

    Returns:
        Path to the extracted CSV file.

    Raises:
        zipfile.BadZipFile: If the ZIP file is corrupted.
        FileNotFoundError: If the ZIP file does not exist.
    """
    if output_dir is None:
        output_dir = RAW_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / CSV_FILENAME

    if csv_path.exists():
        console.print(f"  CSV already extracted: {csv_path}")
        return csv_path

    console.print(f"  Extracting {zip_path}...")

    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError("No CSV file found in ZIP archive")
        zf.extract(csv_names[0], output_dir)
        extracted = output_dir / csv_names[0]
        if extracted != csv_path:
            extracted.rename(csv_path)

    file_size_mb = csv_path.stat().st_size / (1024 * 1024)
    console.print(f"  Extracted CSV: {file_size_mb:.1f} MB")
    return csv_path


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

def parse_complaints_csv(
    csv_path: Path,
    limit: Optional[int] = None,
) -> Generator[dict, None, None]:
    """
    Parse the CFPB complaints CSV file in a streaming fashion.

    Yields complaint dictionaries one at a time to avoid loading
    the entire 2GB+ file into memory.

    Args:
        csv_path: Path to the extracted CSV file.
        limit: Maximum number of records to yield. None for all records.

    Yields:
        dict: A complaint record with keys matching the database schema.
              Keys are normalized via CSV_FIELD_MAP.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        csv.Error: If the CSV cannot be parsed.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    console.print(f"  Parsing complaints from {csv_path}...")
    count = 0

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {}
            for csv_col, db_col in CSV_FIELD_MAP.items():
                val = row.get(csv_col, "")
                record[db_col] = val.strip() if val and val.strip() else None
            # Convert complaint_id to integer
            if record.get("complaint_id"):
                try:
                    record["complaint_id"] = int(record["complaint_id"])
                except (ValueError, TypeError):
                    continue  # Skip rows with invalid complaint IDs
            else:
                continue  # Skip rows without complaint ID
            yield record
            count += 1
            if count % 100000 == 0:
                console.print(f"  Parsed {count:,} complaints...")
            if limit and count >= limit:
                break

    console.print(f"  [green]Parsed {count:,} complaints total[/green]")


# ---------------------------------------------------------------------------
# Pipeline Integration
# ---------------------------------------------------------------------------

def run_cfpb_pipeline(
    db_conn,
    force_download: bool = False,
    limit: Optional[int] = None,
    batch_size: int = 1000,
) -> int:
    """
    Run the full CFPB download-and-store pipeline.

    1. Download ZIP (or use cache)
    2. Extract CSV
    3. Parse CSV in streaming fashion
    4. Store to SQLite in batches

    Args:
        db_conn: Active SQLite database connection.
        force_download: Force re-download of the ZIP file.
        limit: Maximum records to process (for testing).
        batch_size: Number of records per database batch insert.

    Returns:
        Total number of records stored.
    """
    from src.storage.database import store_complaints_batch, start_pipeline_run, complete_pipeline_run

    run_id = start_pipeline_run(db_conn, "cfpb_complaints")
    try:
        zip_path = download_complaints(force_download=force_download)
        csv_path = extract_csv_from_zip(zip_path)
        batch = []
        total = 0
        for complaint in parse_complaints_csv(csv_path, limit=limit):
            batch.append(complaint)
            if len(batch) >= batch_size:
                store_complaints_batch(db_conn, batch)
                total += len(batch)
                batch = []
                if total % 100000 == 0:
                    console.print(f"  Stored {total:,} complaints...")
        if batch:
            store_complaints_batch(db_conn, batch)
            total += len(batch)
        complete_pipeline_run(db_conn, run_id, total)
        console.print(f"  [green]Stored {total:,} complaints in database[/green]")
        return total
    except Exception as e:
        complete_pipeline_run(db_conn, run_id, 0, status="failed", notes=str(e))
        raise
