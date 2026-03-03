"""Download and parse DOL WHD compliance action data."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw"
CACHE_FILE = CACHE_DIR / "whd_data.csv"

# DOL enforcedata bulk CSV
WHD_CSV_URL = "https://enforcementdata.dol.gov/views/data_catalogs/completewhd.csv.zip"
# Fallback: DOL developer API
WHD_API_URL = "https://data.dol.gov/get/whisard/limit/1000/offset/{offset}"

HEADERS = {
    "User-Agent": "DataFactory/1.0 (EmployerLaborCompliance; research; nathanmauricegoldberg@gmail.com)",
}


def download_whd_data(force: bool = False) -> Path:
    """Download WHD compliance action data as CSV."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        return CACHE_FILE

    # Try bulk ZIP download first
    zip_path = CACHE_DIR / "whd_data.zip"
    try:
        with httpx.Client(timeout=300, headers=HEADERS, follow_redirects=True) as client:
            with client.stream("GET", WHD_CSV_URL) as response:
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


def parse_whd_csv(file_path: Path | None = None, min_year: int = 2015) -> list[dict]:
    """Parse WHD CSV into structured records."""
    path = file_path or CACHE_FILE
    if not path.exists():
        raise FileNotFoundError(f"WHD data not found at {path}. Run download first.")

    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter by year
            start_date = row.get("findings_start_date", "")
            if start_date and min_year:
                try:
                    year = int(start_date[:4])
                    if year < min_year:
                        continue
                except (ValueError, IndexError):
                    pass

            rec = {
                "case_id": row.get("case_id", "").strip(),
                "trade_name": row.get("trade_nm", "").strip(),
                "legal_name": row.get("legal_name", "").strip(),
                "street_address": row.get("street_addr_1_txt", "").strip(),
                "city": row.get("cty_nm", "").strip(),
                "state": row.get("st_cd", "").strip(),
                "zip_code": row.get("zip_cd", "").strip(),
                "naics_code": row.get("naic_cd", "").strip(),
                "naics_description": row.get("naics_code_description", "").strip(),
                "findings_start_date": _normalize_date(row.get("findings_start_date", "")),
                "findings_end_date": _normalize_date(row.get("findings_end_date", "")),
                "back_wages_owed": _safe_float(row.get("bw_atp_amt", "0")),
                "civil_penalties": _safe_float(row.get("cmp_assd_cnt", "0")),
                "employees_affected": _safe_int(row.get("ee_atp_cnt", "0")),
                "flsa_violated": 1 if row.get("flsa_violtn_cnt", "0") not in ("0", "") else 0,
                "mspa_violated": 1 if row.get("mspa_violtn_cnt", "0") not in ("0", "") else 0,
                "h1b_violated": 1 if row.get("h1b_violtn_cnt", "0") not in ("0", "") else 0,
                "fmla_violated": 1 if row.get("fmla_violtn_cnt", "0") not in ("0", "") else 0,
                "sca_violated": 1 if row.get("sca_violtn_cnt", "0") not in ("0", "") else 0,
                "dba_violated": 1 if row.get("dba_violtn_cnt", "0") not in ("0", "") else 0,
                "employer_normalized": "",
                "quality_score": 0.0,
            }

            if rec["case_id"]:
                records.append(rec)

    return records


def _normalize_date(val: str) -> str:
    """Normalize date string to ISO format."""
    if not val:
        return ""
    val = val.strip()
    # MM/DD/YYYY -> YYYY-MM-DD
    if "/" in val:
        parts = val.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
    return val


def _safe_float(val: str) -> float:
    """Safely convert to float."""
    try:
        return float(val.replace(",", "").strip()) if val and val.strip() else 0.0
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val: str) -> int:
    """Safely convert to int."""
    try:
        return int(float(val.replace(",", "").strip())) if val and val.strip() else 0
    except (ValueError, TypeError):
        return 0
