"""Download and parse DOL WHD compliance action data via v4 API."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "whd"
CACHE_FILE = CACHE_DIR / "whd_all.json"

WHD_API_URL = "https://apiprod.dol.gov/v4/get/WHD/enforcement/json"
PAGE_SIZE = 1500
REQUEST_DELAY = 2.0

HEADERS = {
    "User-Agent": "DataFactory/1.0 (EmployerLaborCompliance; research; nathanmauricegoldberg@gmail.com)",
}


def _get_api_key() -> str:
    """Get DOL API key from environment or .env file."""
    key = os.environ.get("DOL_API_KEY")
    if key:
        return key

    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("DOL_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")

    raise RuntimeError(
        "DOL API key not found. Set DOL_API_KEY environment variable or "
        "create projects/employer-labor-compliance/.env with DOL_API_KEY=your_key"
    )


def download_whd_data(force: bool = False) -> Path:
    """Download WHD compliance data via DOL v4 API with pagination.

    Caches each page as a separate JSON file for resumability.
    On completion, writes a combined whd_all.json.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        return CACHE_FILE

    api_key = _get_api_key()
    all_records: list[dict] = []
    offset = 0

    with httpx.Client(timeout=120, headers=HEADERS) as client:
        while True:
            # Check if this page is already cached (resumable)
            page_file = CACHE_DIR / f"page_{offset:06d}.json"
            if page_file.exists() and not force:
                records = json.loads(page_file.read_text())
            else:
                for attempt in range(12):
                    try:
                        response = client.get(
                            WHD_API_URL,
                            params={"limit": PAGE_SIZE, "offset": offset, "X-API-KEY": api_key},
                        )
                    except httpx.ReadTimeout:
                        wait = min(REQUEST_DELAY * (2 ** (attempt + 1)), 300)
                        print(f"  Timeout at offset {offset}, retry {attempt+1}/12, waiting {wait:.0f}s")
                        time.sleep(wait)
                        continue
                    if response.status_code in (429, 502, 503, 504):
                        wait = min(REQUEST_DELAY * (2 ** (attempt + 1)), 300)
                        print(f"  {response.status_code} at offset {offset}, retry {attempt+1}/12, waiting {wait:.0f}s")
                        time.sleep(wait)
                        continue
                    response.raise_for_status()
                    break
                else:
                    raise RuntimeError(
                        f"Failed after 12 retries at offset {offset}"
                    )
                data = response.json()
                records = data.get("data", [])
                page_file.write_text(json.dumps(records))
                time.sleep(REQUEST_DELAY)

            if not records:
                break

            all_records.extend(records)
            offset += PAGE_SIZE

            if len(records) < PAGE_SIZE:
                break

    CACHE_FILE.write_text(json.dumps(all_records))
    return CACHE_FILE


def parse_whd_data(file_path: Path | None = None, min_year: int = 2015) -> list[dict]:
    """Parse WHD JSON data into structured records."""
    path = file_path or CACHE_FILE
    if not path.exists():
        raise FileNotFoundError(f"WHD data not found at {path}. Run download first.")

    raw = json.loads(path.read_text())
    records = []

    for row in raw:
        start_date = _normalize_api_date(row.get("findings_start_date"))
        if start_date and min_year:
            try:
                year = int(start_date[:4])
                if year < min_year:
                    continue
            except (ValueError, IndexError):
                pass

        case_id = row.get("case_id")
        if case_id is None:
            continue

        rec = {
            "case_id": str(case_id).strip(),
            "trade_name": (row.get("trade_nm") or "").strip(),
            "legal_name": (row.get("legal_name") or "").strip(),
            "street_address": (row.get("street_addr_1_txt") or "").strip(),
            "city": (row.get("cty_nm") or "").strip(),
            "state": (row.get("st_cd") or "").strip(),
            "zip_code": (row.get("zip_cd") or "").strip(),
            "naics_code": (row.get("naic_cd") or "").strip(),
            "naics_description": (row.get("naics_code_description") or "").strip(),
            "findings_start_date": start_date,
            "findings_end_date": _normalize_api_date(row.get("findings_end_date")),
            "back_wages_owed": _safe_float(row.get("bw_atp_amt", 0)),
            "civil_penalties": _safe_float(row.get("cmp_assd", 0)),
            "employees_affected": _safe_int(row.get("ee_atp_cnt", 0)),
            "flsa_violated": 1 if _safe_int(row.get("flsa_violtn_cnt", 0)) > 0 else 0,
            "mspa_violated": 1 if _safe_int(row.get("mspa_violtn_cnt", 0)) > 0 else 0,
            "h1b_violated": 1 if _safe_int(row.get("h1b_violtn_cnt", 0)) > 0 else 0,
            "fmla_violated": 1 if _safe_int(row.get("fmla_violtn_cnt", 0)) > 0 else 0,
            "sca_violated": 1 if _safe_int(row.get("sca_violtn_cnt", 0)) > 0 else 0,
            "dba_violated": 1 if _safe_int(row.get("dbra_violtn_cnt", 0)) > 0 else 0,
            "employer_normalized": "",
            "quality_score": 0.0,
        }

        if rec["case_id"]:
            records.append(rec)

    return records


# Keep old name as alias for backward compatibility with tests
parse_whd_csv = parse_whd_data


def _normalize_api_date(val) -> str:
    """Normalize API date (ISO like 2013-03-20T00:00:00) to YYYY-MM-DD."""
    if not val:
        return ""
    val = str(val).strip()
    if "T" in val:
        return val.split("T")[0]
    return val[:10] if len(val) >= 10 else val


def _safe_float(val) -> float:
    """Safely convert API value to float."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val) -> int:
    """Safely convert API value to int."""
    if val is None:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0
