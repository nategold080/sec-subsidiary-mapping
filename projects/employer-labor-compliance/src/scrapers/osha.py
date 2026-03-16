"""Download and parse OSHA inspection data via DOL v4 API."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path

import httpx

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "osha"
CACHE_FILE = CACHE_DIR / "osha_inspections.json"
VIOLATIONS_CACHE = CACHE_DIR / "osha_violations.json"

OSHA_INSPECTION_URL = "https://apiprod.dol.gov/v4/get/OSHA/inspection/json"
OSHA_VIOLATION_URL = "https://apiprod.dol.gov/v4/get/OSHA/violation/json"
PAGE_SIZE = 4000
REQUEST_DELAY = 2.0

HEADERS = {
    "User-Agent": "DataFactory/1.0 (EmployerLaborCompliance; research; nathanmauricegoldberg@gmail.com)",
}

# OSHA violation type codes
VIOL_TYPES = {"S": "serious", "W": "willful", "R": "repeat", "O": "other", "U": "unclassified"}


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


def _paginate_api(client: httpx.Client, base_url: str, api_key: str,
                  cache_dir: Path, prefix: str, force: bool = False) -> list[dict]:
    """Generic paginated download from DOL v4 API."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    all_records: list[dict] = []
    offset = 0

    while True:
        page_file = cache_dir / f"{prefix}_{offset:07d}.json"
        if page_file.exists() and not force:
            records = json.loads(page_file.read_text())
        else:
            for attempt in range(12):
                try:
                    response = client.get(
                        base_url,
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

    return all_records


def download_osha_data(force: bool = False) -> Path:
    """Download OSHA inspection data via DOL v4 API with pagination."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists() and not force:
        return CACHE_FILE

    api_key = _get_api_key()

    with httpx.Client(timeout=120, headers=HEADERS) as client:
        records = _paginate_api(client, OSHA_INSPECTION_URL, api_key,
                                CACHE_DIR, "insp", force)

    CACHE_FILE.write_text(json.dumps(records))
    return CACHE_FILE


def download_osha_violations(force: bool = False) -> Path:
    """Download OSHA violation data and aggregate per inspection."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if VIOLATIONS_CACHE.exists() and not force:
        return VIOLATIONS_CACHE

    api_key = _get_api_key()

    with httpx.Client(timeout=120, headers=HEADERS) as client:
        raw_violations = _paginate_api(client, OSHA_VIOLATION_URL, api_key,
                                       CACHE_DIR, "viol", force)

    # Aggregate violations by activity_nr
    agg: dict[str, dict] = defaultdict(lambda: {
        "total_initial_penalty": 0.0,
        "total_current_penalty": 0.0,
        "num_violations": 0,
        "serious_violations": 0,
        "willful_violations": 0,
        "repeat_violations": 0,
    })

    for v in raw_violations:
        act_nr = str(v.get("activity_nr", ""))
        if not act_nr:
            continue
        a = agg[act_nr]
        a["total_initial_penalty"] += _safe_float(v.get("initial_penalty", 0))
        a["total_current_penalty"] += _safe_float(v.get("current_penalty", 0))
        a["num_violations"] += 1
        vtype = (v.get("viol_type") or "").strip().upper()
        if vtype == "S":
            a["serious_violations"] += 1
        elif vtype == "W":
            a["willful_violations"] += 1
        elif vtype == "R":
            a["repeat_violations"] += 1

    VIOLATIONS_CACHE.write_text(json.dumps(dict(agg)))
    return VIOLATIONS_CACHE


def parse_osha_data(file_path: Path | None = None, min_year: int = 2015) -> list[dict]:
    """Parse OSHA inspection JSON into structured records.

    If violation aggregates are available, merges penalty/violation counts.
    """
    path = file_path or CACHE_FILE
    if not path.exists():
        raise FileNotFoundError(f"OSHA data not found at {path}. Run download first.")

    raw = json.loads(path.read_text())

    # Load violation aggregates if available
    viol_agg: dict[str, dict] = {}
    if VIOLATIONS_CACHE.exists():
        viol_agg = json.loads(VIOLATIONS_CACHE.read_text())

    records = []

    for row in raw:
        open_date = _normalize_api_date(row.get("open_date"))
        if open_date and min_year:
            try:
                year = int(open_date[:4])
                if year < min_year:
                    continue
            except (ValueError, IndexError):
                pass

        act_nr = row.get("activity_nr")
        if act_nr is None:
            continue
        act_nr_str = str(act_nr).strip()

        # Get violation aggregates for this inspection
        va = viol_agg.get(act_nr_str, {})

        rec = {
            "activity_number": act_nr_str,
            "reporting_id": (row.get("reporting_id") or "").strip(),
            "establishment_name": (row.get("estab_name") or "").strip(),
            "site_address": (row.get("site_address") or "").strip(),
            "site_city": (row.get("site_city") or "").strip(),
            "site_state": (row.get("site_state") or "").strip(),
            "site_zip": (row.get("site_zip") or "").strip(),
            "naics_code": (row.get("naics_code") or "").strip(),
            "sic_code": (row.get("sic_code") or "").strip(),
            "inspection_type": (row.get("insp_type") or "").strip(),
            "open_date": open_date,
            "close_date": _normalize_api_date(row.get("close_case_date")),
            "total_initial_penalty": _safe_float(va.get("total_initial_penalty", 0)),
            "total_current_penalty": _safe_float(va.get("total_current_penalty", 0)),
            "num_violations": _safe_int(va.get("num_violations", 0)),
            "serious_violations": _safe_int(va.get("serious_violations", 0)),
            "willful_violations": _safe_int(va.get("willful_violations", 0)),
            "repeat_violations": _safe_int(va.get("repeat_violations", 0)),
            "fatalities": 0,  # Not in v4 inspection endpoint
            "hospitalized": 0,  # Not in v4 inspection endpoint
            "employer_normalized": "",
            "quality_score": 0.0,
        }

        if rec["activity_number"]:
            records.append(rec)

    return records


# Keep old name as alias for backward compatibility with tests
parse_osha_csv = parse_osha_data


def _normalize_api_date(val) -> str:
    """Normalize API date (ISO like 2014-07-24T00:00:00) to YYYY-MM-DD."""
    if not val:
        return ""
    val = str(val).strip()
    if "T" in val:
        return val.split("T")[0]
    return val[:10] if len(val) >= 10 else val


def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val) -> int:
    if val is None:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0
