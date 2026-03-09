"""
FFIEC CRA Ratings downloader.

Downloads and parses Community Reinvestment Act (CRA) ratings from the
FFIEC flat files. Since the FFIEC website blocks automated access, this
module supports loading from a pre-downloaded file or using the FDIC
BankFind API as a fallback data source.

Data source: https://www.ffiec.gov/cra/craflatfiles.htm
Alternative: FDIC BankFind Suite API

Built by Nathan Goldberg | nathanmauricegoldberg@gmail.com
"""

import csv
import os
from pathlib import Path
from typing import Generator, Optional

import requests
from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

# Known CRA rating values
VALID_CRA_RATINGS = {
    "Outstanding",
    "Satisfactory",
    "Needs to Improve",
    "Substantial Noncompliance",
}

# FDIC API for supplemental institution data
FDIC_API_BASE = "https://api.fdic.gov/banks/institutions"
USER_AGENT = (
    "CFPB-Complaint-Tracker/0.1 "
    "(Research project by Nathan Goldberg; nathanmauricegoldberg@gmail.com)"
)


# ---------------------------------------------------------------------------
# Flat File Parsing (if manually downloaded)
# ---------------------------------------------------------------------------

def parse_cra_flat_file(
    file_path: Path,
    limit: Optional[int] = None,
) -> Generator[dict, None, None]:
    """
    Parse a CRA ratings flat file (pipe-delimited or CSV).

    The FFIEC provides CRA data in flat files. Supports both pipe-delimited
    and comma-delimited formats.

    Args:
        file_path: Path to the downloaded CRA file.
        limit: Maximum records to yield.

    Yields:
        dict: CRA rating records matching the database schema.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"CRA file not found: {file_path}")

    # Detect delimiter
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
        delimiter = "|" if "|" in first_line else ","

    console.print(f"  Parsing CRA file: {file_path} (delimiter: '{delimiter}')")

    count = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            # Map common field names to our schema
            cert = None
            for key in ("CERT", "Cert", "cert_number", "Certificate"):
                if key in row and row[key]:
                    try:
                        cert = int(row[key].strip())
                        break
                    except ValueError:
                        continue

            if cert is None:
                continue

            rating = None
            for key in ("RATING", "CRA_RATING", "Rating", "cra_rating"):
                if key in row and row[key]:
                    rating = row[key].strip()
                    break

            name = None
            for key in ("INSTNAME", "NAME", "Institution", "institution_name"):
                if key in row and row[key]:
                    name = row[key].strip()
                    break

            exam_date = None
            for key in ("EXAMDATE", "EXAM_DATE", "ExamDate", "exam_date"):
                if key in row and row[key]:
                    exam_date = row[key].strip()
                    break

            regulator = None
            for key in ("REGAGENT", "REGAGNT", "Regulator", "regulator"):
                if key in row and row[key]:
                    regulator = row[key].strip()
                    break

            record = {
                "cert_number": cert,
                "institution_name": name,
                "exam_date": exam_date,
                "cra_rating": rating,
                "assessment_area": row.get("AREA", row.get("assessment_area")),
                "regulator": regulator,
            }

            yield record
            count += 1
            if limit and count >= limit:
                break

    console.print(f"  [green]Parsed {count} CRA records[/green]")


# ---------------------------------------------------------------------------
# Generate Synthetic CRA Data from FDIC
# ---------------------------------------------------------------------------

def generate_cra_ratings_from_fdic(
    db_conn,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Generate placeholder CRA rating records for FDIC institutions.

    Since the FFIEC blocks automated access, this creates CRA records
    for institutions that have known regulatory oversight. The actual
    CRA ratings are NOT available via API, so this creates records
    with cra_rating=None to indicate data needs manual enrichment.

    This at least establishes the cert_number linkage so the cross-link
    infrastructure works correctly.

    Args:
        db_conn: Active database connection.
        limit: Maximum records to generate.

    Returns:
        List of CRA rating dicts.
    """
    cursor = db_conn.execute(
        """
        SELECT cert_number, institution_name, regulator
        FROM financial_institutions
        WHERE active = 1
        ORDER BY total_assets DESC
        """
    )
    rows = cursor.fetchall()

    records = []
    for row in rows:
        if limit and len(records) >= limit:
            break
        records.append({
            "cert_number": row["cert_number"],
            "institution_name": row["institution_name"],
            "exam_date": None,
            "cra_rating": None,  # Unknown - requires FFIEC data
            "assessment_area": None,
            "regulator": row["regulator"],
        })

    return records


# ---------------------------------------------------------------------------
# Pipeline Integration
# ---------------------------------------------------------------------------

def run_cra_pipeline(
    db_conn,
    file_path: Optional[Path] = None,
    batch_size: int = 1000,
) -> int:
    """
    Run the CRA ratings pipeline.

    If a CRA flat file is provided, parse and store it.
    Otherwise, note that FFIEC data requires manual download.

    Args:
        db_conn: Active database connection.
        file_path: Optional path to a manually downloaded CRA flat file.
        batch_size: Number of records per database batch insert.

    Returns:
        Total number of records stored.
    """
    from src.storage.database import (
        store_cra_ratings_batch,
        start_pipeline_run,
        complete_pipeline_run,
    )

    run_id = start_pipeline_run(db_conn, "cra_ratings")

    # Check for CRA files in the raw directory
    if file_path is None:
        for candidate in RAW_DIR.glob("*cra*"):
            file_path = candidate
            break

    try:
        if file_path and file_path.exists():
            console.print(f"  Loading CRA data from {file_path}")
            records = list(parse_cra_flat_file(file_path))
        else:
            console.print(
                "  [yellow]No CRA flat file found. FFIEC blocks automated downloads.[/yellow]"
            )
            console.print(
                "  [yellow]To add CRA data: download from ffiec.gov/cra/craflatfiles.htm[/yellow]"
            )
            console.print(
                "  [yellow]and place the file in data/raw/[/yellow]"
            )
            records = []

        total = 0
        if records:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                store_cra_ratings_batch(db_conn, batch)
                total += len(batch)

        complete_pipeline_run(db_conn, run_id, total)
        console.print(f"  [green]Stored {total} CRA records[/green]")
        return total
    except Exception as e:
        complete_pipeline_run(db_conn, run_id, 0, status="failed", notes=str(e))
        raise
