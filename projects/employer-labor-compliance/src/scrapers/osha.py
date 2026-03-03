"""Download and parse OSHA inspection data."""

from __future__ import annotations

import csv
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
CACHE_FILE = CACHE_DIR / "osha_inspection.csv"

# OSHA inspection data bulk CSV
OSHA_CSV_URL = "https://enforcementdata.dol.gov/views/data_catalogs/osha_inspection.csv.zip"

HEADERS = {
    "User-Agent": "DataFactory/1.0 (EmployerLaborCompliance; research; nathanmauricegoldberg@gmail.com)",
}


def download_osha_data(force: bool = False) -> Path:
    """Download OSHA inspection data as CSV."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        return CACHE_FILE

    zip_path = CACHE_DIR / "osha_inspection.zip"
    try:
        with httpx.Client(timeout=300, headers=HEADERS, follow_redirects=True) as client:
            with client.stream("GET", OSHA_CSV_URL) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)

        import zipfile
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            csv_name = next((n for n in names if n.endswith(".csv")), names[0])
            zf.extract(csv_name, CACHE_DIR)
            extracted = CACHE_DIR / csv_name
            if extracted != CACHE_FILE:
                extracted.rename(CACHE_FILE)
        zip_path.unlink(missing_ok=True)
        return CACHE_FILE
    except Exception:
        zip_path.unlink(missing_ok=True)
        raise


def parse_osha_csv(file_path: Path | None = None, min_year: int = 2015) -> list[dict]:
    """Parse OSHA inspection CSV into structured records."""
    path = file_path or CACHE_FILE
    if not path.exists():
        raise FileNotFoundError(f"OSHA data not found at {path}. Run download first.")

    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            open_date = row.get("open_date", "")
            if open_date and min_year:
                try:
                    year = int(open_date[:4])
                    if year < min_year:
                        continue
                except (ValueError, IndexError):
                    pass

            rec = {
                "activity_number": row.get("activity_nr", "").strip(),
                "reporting_id": row.get("reporting_id", "").strip(),
                "establishment_name": row.get("estab_name", "").strip(),
                "site_address": row.get("site_address", "").strip(),
                "site_city": row.get("site_city", "").strip(),
                "site_state": row.get("site_state", "").strip(),
                "site_zip": row.get("site_zip", "").strip(),
                "naics_code": row.get("naics_code", "").strip(),
                "sic_code": row.get("sic_code", "").strip(),
                "inspection_type": row.get("insp_type", "").strip(),
                "open_date": _normalize_date(row.get("open_date", "")),
                "close_date": _normalize_date(row.get("close_case_date", "")),
                "total_initial_penalty": _safe_float(row.get("total_initial_penalty", "0")),
                "total_current_penalty": _safe_float(row.get("total_current_penalty", "0")),
                "num_violations": _safe_int(row.get("total_violations", "0")),
                "serious_violations": _safe_int(row.get("serious_violations", "0")),
                "willful_violations": _safe_int(row.get("willful_violations", "0")),
                "repeat_violations": _safe_int(row.get("repeat_violations", "0")),
                "fatalities": _safe_int(row.get("nr_in_state_fatality", "0")),
                "hospitalized": _safe_int(row.get("nr_in_state_inpatient", "0")),
                "employer_normalized": "",
                "quality_score": 0.0,
            }

            if rec["activity_number"]:
                records.append(rec)

    return records


def _normalize_date(val: str) -> str:
    if not val:
        return ""
    val = val.strip()
    if "/" in val:
        parts = val.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
    return val


def _safe_float(val: str) -> float:
    try:
        return float(val.replace(",", "").strip()) if val and val.strip() else 0.0
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val: str) -> int:
    try:
        return int(float(val.replace(",", "").strip())) if val and val.strip() else 0
    except (ValueError, TypeError):
        return 0
