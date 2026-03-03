"""Download and parse NLRB case data.

Primary source: labordata/nlrb-data nightly SQLite database (5.9M records).
Fallback: NLRB.gov CSV export or API pagination.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

HEADERS = {
    "User-Agent": "DataFactory/1.0 (EmployerLaborCompliance; research; nathanmauricegoldberg@gmail.com)",
}

# Primary: labordata nightly SQLite release
NLRB_DB_URL = "https://github.com/labordata/nlrb-data/releases/download/nightly/nlrb.db.zip"
NLRB_DB_FILE = CACHE_DIR / "nlrb.db"
# Fallback: scraped CSV
NLRB_CSV_FILE = CACHE_DIR / "nlrb_cases.csv"


def download_nlrb_data(force: bool = False) -> Path:
    """Download NLRB data from the labordata/nlrb-data nightly release.

    Downloads a 171MB ZIP containing a 951MB SQLite database with
    ~500K case filings, 720K allegations, and 1.9M participant records.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if NLRB_DB_FILE.exists() and not force:
        return NLRB_DB_FILE

    zip_path = CACHE_DIR / "nlrb.db.zip"
    try:
        with httpx.Client(timeout=600, headers=HEADERS, follow_redirects=True) as client:
            with client.stream("GET", NLRB_DB_URL) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)

        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            db_name = next((n for n in names if n.endswith(".db")), names[0])
            zf.extract(db_name, CACHE_DIR)
            extracted = CACHE_DIR / db_name
            if extracted != NLRB_DB_FILE:
                extracted.rename(NLRB_DB_FILE)

        zip_path.unlink(missing_ok=True)
        return NLRB_DB_FILE
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise


def parse_nlrb_db(db_path: Path | None = None, min_year: int = 2015) -> list[dict]:
    """Parse NLRB SQLite database from labordata/nlrb-data.

    The database has these key tables:
    - filing: 501K case filings (our primary table)
    - allegation: 720K allegations (joined for allegation text)
    - participant: 1.9M participants (joined for employer names)
    """
    path = db_path or NLRB_DB_FILE
    if not path.exists():
        raise FileNotFoundError(f"NLRB database not found at {path}. Run download first.")

    nlrb_conn = sqlite3.connect(str(path))
    nlrb_conn.row_factory = sqlite3.Row

    # Query filings with aggregated allegations
    query = """
        SELECT
            f.case_number,
            f.name AS case_name,
            f.case_type,
            f.date_filed,
            f.date_closed,
            f.status,
            f.city,
            f.state,
            f.number_of_eligible_voters,
            GROUP_CONCAT(a.allegation, '; ') AS allegations
        FROM filing f
        LEFT JOIN allegation a ON f.case_number = a.case_number
        WHERE 1=1
    """
    params = []
    if min_year:
        query += " AND f.date_filed >= ?"
        params.append(f"{min_year}-01-01")

    query += " GROUP BY f.case_number ORDER BY f.date_filed DESC"

    rows = nlrb_conn.execute(query, params).fetchall()

    records = []
    for row in rows:
        case_number = (row["case_number"] or "").strip()
        if not case_number:
            continue

        # Extract case type from case number if not in field
        case_type = (row["case_type"] or "").strip()
        if not case_type and case_number:
            parts = case_number.split("-")
            if len(parts) >= 2:
                case_type = parts[1][0] if parts[1] else ""

        rec = {
            "case_number": case_number,
            "case_name": (row["case_name"] or "").strip(),
            "date_filed": _normalize_date(row["date_filed"] or ""),
            "date_closed": _normalize_date(row["date_closed"] or ""),
            "status": (row["status"] or "").strip(),
            "case_type": case_type,
            "allegation": (row["allegations"] or "").strip()[:500],  # Truncate long aggregated text
            "city": (row["city"] or "").strip(),
            "state": (row["state"] or "").strip(),
            "num_employees": _safe_int(row["number_of_eligible_voters"]),
            "unit_description": "",
            "union_name": "",
            "employer_normalized": "",
            "quality_score": 0.0,
        }
        records.append(rec)

    nlrb_conn.close()
    return records


def parse_nlrb_jsonl(file_path: Path | None = None) -> list[dict]:
    """Parse NLRB JSON-lines file into structured records."""
    path = file_path or CACHE_DIR / "nlrb_cases.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"NLRB data not found at {path}. Run download first.")

    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            rec = _parse_nlrb_case(case)
            if rec and rec["case_number"]:
                records.append(rec)

    return records


def parse_nlrb_csv(file_path: Path | None = None, min_year: int = 2015) -> list[dict]:
    """Parse NLRB CSV file (manual download fallback)."""
    path = file_path or NLRB_CSV_FILE
    if not path.exists():
        raise FileNotFoundError(f"NLRB CSV not found at {path}.")

    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_filed = row.get("date_filed", row.get("Date Filed", ""))
            if date_filed and min_year:
                try:
                    year = int(date_filed[:4])
                    if year < min_year:
                        continue
                except (ValueError, IndexError):
                    pass

            rec = {
                "case_number": (row.get("case_number") or row.get("Case Number", "")).strip(),
                "case_name": (row.get("case_name") or row.get("Case Name", "")).strip(),
                "date_filed": _normalize_date(date_filed),
                "date_closed": _normalize_date(row.get("date_closed", row.get("Date Closed", ""))),
                "status": (row.get("status") or row.get("Status", "")).strip(),
                "case_type": (row.get("case_type") or row.get("Type", "")).strip(),
                "allegation": (row.get("allegation") or row.get("Allegation", "")).strip(),
                "city": (row.get("city") or row.get("City", "")).strip(),
                "state": (row.get("state") or row.get("State", "")).strip(),
                "num_employees": _safe_int(row.get("num_employees", row.get("Number of Employees", "0"))),
                "unit_description": (row.get("unit_description") or row.get("Unit Description", "")).strip(),
                "union_name": (row.get("union_name") or row.get("Labor Org", "")).strip(),
                "employer_normalized": "",
                "quality_score": 0.0,
            }

            if rec["case_number"]:
                records.append(rec)

    return records


def _parse_nlrb_case(case: dict) -> dict:
    """Parse a single NLRB API case into our schema."""
    # Handle various field name formats from the NLRB API
    case_number = (
        case.get("case_number")
        or case.get("caseNumber")
        or case.get("case_no")
        or ""
    ).strip()

    case_name = (
        case.get("case_name")
        or case.get("caseName")
        or case.get("employer_name")
        or case.get("name")
        or ""
    ).strip()

    # Extract case type from case number (e.g., "13-CA-123456" -> "C")
    case_type = case.get("case_type", case.get("caseType", ""))
    if not case_type and case_number:
        parts = case_number.split("-")
        if len(parts) >= 2:
            case_type = parts[1][0] if parts[1] else ""

    return {
        "case_number": case_number,
        "case_name": case_name,
        "date_filed": _normalize_date(case.get("date_filed", case.get("dateFiled", ""))),
        "date_closed": _normalize_date(case.get("date_closed", case.get("dateClosed", ""))),
        "status": (case.get("status", case.get("caseStatus", ""))).strip(),
        "case_type": case_type.strip(),
        "allegation": (case.get("allegation", case.get("allegations", ""))).strip(),
        "city": (case.get("city", "")).strip(),
        "state": (case.get("state", "")).strip(),
        "num_employees": _safe_int(case.get("num_employees", case.get("numEmployees", "0"))),
        "unit_description": (case.get("unit_description", case.get("bargainingUnit", ""))).strip(),
        "union_name": (case.get("union_name", case.get("laborOrg", ""))).strip(),
        "employer_normalized": "",
        "quality_score": 0.0,
    }


def _normalize_date(val: str) -> str:
    if not val:
        return ""
    val = str(val).strip()
    if "/" in val:
        parts = val.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
    # Handle ISO-8601 datetime
    if "T" in val:
        val = val.split("T")[0]
    return val


def _safe_int(val) -> int:
    try:
        return int(float(str(val).replace(",", "").strip())) if val else 0
    except (ValueError, TypeError):
        return 0
