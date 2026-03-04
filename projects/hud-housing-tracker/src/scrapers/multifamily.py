"""HUD Multifamily Properties scraper via ArcGIS FeatureServer.

Source: HUD Open Data - Multifamily Properties Assisted
URL: https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/
Format: ArcGIS REST API (JSON)
Records: ~34,000 properties with REAC inspection scores embedded
"""

import json
import time
from pathlib import Path

import httpx

# ArcGIS FeatureServer endpoints
MF_ASSISTED_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/"
    "Multifamily_Properties_Assisted/FeatureServer/0/query"
)
MF_INSURED_URL = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/"
    "HUD_Insured_Multifamily_Properties/FeatureServer/0/query"
)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

# Fields to request from the assisted properties endpoint
ASSISTED_FIELDS = [
    "PROPERTY_ID", "PROPERTY_NAME_TEXT", "STD_ADDR", "STD_CITY", "STD_ST",
    "STD_ZIP5", "CNTY2KX", "CONGRESSIONAL_DISTRICT_CODE",
    "CLIENT_GROUP_NAME", "CLIENT_GROUP_TYPE",
    "MGMT_AGENT_ORG_NAME", "PROGRAM_TYPE1", "PROGRAM_TYPE2",
    "TOTAL_UNIT_COUNT", "TOTAL_ASSISTED_UNIT_COUNT",
    "IS_SEC8_IND", "IS_202_811_IND", "IS_SUBSIDIZED_IND", "IS_INSURED_IND",
    "TAXCREDIT1", "TAXCREDIT2",
    "REAC_LAST_INSPECTION_SCORE", "REAC_LAST_INSPECTION_DATE",
    "REAC_LAST_INSPECTION_ID",
    "PCT_OCCUPIED", "RENT_PER_MONTH", "SPENDING_PER_MONTH",
    "ANNL_EXPNS_AMNT", "OPIIS_RISK_CATEGORY",
    "EXPIRATION_DATE1", "EXPIRATION_DATE2",
    "CONTRACT1", "CONTRACT2", "CONTRACT_COUNT",
    "FHA_NUM1", "FHA_NUM2",
    "LAT", "LON",
    "TROUBLED_CODE",
]

INSURED_FIELDS = [
    "PROPERTY_ID", "PROPERTY_NAME_TEXT", "ADDRESS_LINE1_TEXT",
    "PLACED_BASE_CITY_NAME_TEXT", "STD_ST", "STD_ZIP5",
    "CNTY_NM2KX", "CONGRESSIONAL_DISTRICT_CODE",
    "PRIMARY_FHA_NUMBER", "PRIMARY_FINANCING_TYPE",
    "PROPERTY_CATEGORY_NAME",
    "TOTAL_UNIT_COUNT", "MAXIMUM_CONTRACT_UNIT_COUNT",
    "IS_SEC8_IND", "IS_SUBSIDIZED_IND", "IS_INSURED_IND",
    "IS_202_811_IND", "IS_202_CAPITAL_ADVANCE_IND", "IS_811_CAPITAL_ADVANCE_IND",
    "REAC_LAST_INSPECTION_SCORE", "REAC_LAST_INSPECTION_DATE",
    "MGMT_AGENT_ORG_NAME",
    "HAS_ACTIVE_FINANCING_IND", "HAS_ACTIVE_ASSISTANCE_IND",
    "LOAN_MATURITY_DATE", "ORIGINAL_LOAN_AMOUNT",
    "LAT", "LON",
]

HEADERS = {
    "User-Agent": "HUD-Housing-Tracker/1.0 (nathanmauricegoldberg@gmail.com)"
}


def download_multifamily_assisted(force: bool = False) -> Path:
    """Download all multifamily assisted property records via ArcGIS pagination."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "multifamily_assisted.json"

    if cache_file.exists() and not force:
        return cache_file

    all_features = _paginate_arcgis(MF_ASSISTED_URL, ",".join(ASSISTED_FIELDS))
    cache_file.write_text(json.dumps(all_features, indent=2))
    return cache_file


def download_multifamily_insured(force: bool = False) -> Path:
    """Download all HUD-insured multifamily property records."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "multifamily_insured.json"

    if cache_file.exists() and not force:
        return cache_file

    all_features = _paginate_arcgis(MF_INSURED_URL, ",".join(INSURED_FIELDS))
    cache_file.write_text(json.dumps(all_features, indent=2))
    return cache_file


def _paginate_arcgis(base_url: str, fields: str, batch_size: int = 2000) -> list[dict]:
    """Paginate through ArcGIS FeatureServer results."""
    all_features = []
    offset = 0

    while True:
        params = {
            "where": "1=1",
            "outFields": fields,
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "f": "json",
        }
        resp = httpx.get(base_url, params=params, headers=HEADERS,
                         follow_redirects=True, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        offset += len(features)

        # Check if we've gotten all records
        if not data.get("exceededTransferLimit", False) and len(features) < batch_size:
            break

        time.sleep(1)  # Rate limit

    return all_features


def parse_multifamily_assisted(json_path: Path | None = None) -> list[dict]:
    """Parse multifamily assisted properties into normalized records."""
    path = json_path or (CACHE_DIR / "multifamily_assisted.json")
    if not path.exists():
        raise FileNotFoundError(f"Multifamily assisted data not found at {path}")

    features = json.loads(path.read_text())
    records = []
    for feat in features:
        attrs = feat.get("attributes", feat)
        rec = _parse_assisted_record(attrs)
        if rec:
            records.append(rec)

    return records


def parse_multifamily_insured(json_path: Path | None = None) -> list[dict]:
    """Parse HUD-insured multifamily properties into normalized records."""
    path = json_path or (CACHE_DIR / "multifamily_insured.json")
    if not path.exists():
        raise FileNotFoundError(f"Multifamily insured data not found at {path}")

    features = json.loads(path.read_text())
    records = []
    for feat in features:
        attrs = feat.get("attributes", feat)
        rec = _parse_insured_record(attrs)
        if rec:
            records.append(rec)

    return records


def _parse_assisted_record(attrs: dict) -> dict | None:
    """Parse a single multifamily assisted property record."""
    prop_id = str(attrs.get("PROPERTY_ID", "")).strip()
    if not prop_id:
        return None

    return {
        "property_id": prop_id,
        "property_name": _clean(attrs.get("PROPERTY_NAME_TEXT")),
        "address": _clean(attrs.get("STD_ADDR")),
        "city": _clean(attrs.get("STD_CITY")),
        "state": _clean(attrs.get("STD_ST")),
        "zip_code": _clean(attrs.get("STD_ZIP5")),
        "county_code": _clean(attrs.get("CNTY2KX")),
        "congress_dist": _clean(attrs.get("CONGRESSIONAL_DISTRICT_CODE")),
        "owner_name": _clean(attrs.get("MGMT_AGENT_ORG_NAME")),
        "mgmt_agent": _clean(attrs.get("MGMT_AGENT_ORG_NAME")),
        "program_type": _clean(attrs.get("PROGRAM_TYPE1")),
        "assisted_units": _safe_int(attrs.get("TOTAL_ASSISTED_UNIT_COUNT")),
        "total_units": _safe_int(attrs.get("TOTAL_UNIT_COUNT")),
        "has_section_8": 1 if attrs.get("IS_SEC8_IND") == "Y" else 0,
        "has_lihtc": 1 if attrs.get("TAXCREDIT1") or attrs.get("TAXCREDIT2") else 0,
        "has_section_202": 1 if attrs.get("IS_202_811_IND") == "Y" else 0,
        "has_section_811": 0,  # Separate from 202
        "property_category": _clean(attrs.get("CLIENT_GROUP_TYPE")),
        "occupancy_type": _normalize_occupancy_type(attrs.get("CLIENT_GROUP_NAME")),
        "pct_occupied": _safe_float(attrs.get("PCT_OCCUPIED")),
        "latitude": _safe_float(attrs.get("LAT")),
        "longitude": _safe_float(attrs.get("LON")),
        "source_file": "multifamily_assisted",
        # Extra fields for REAC extraction
        "_reac_score": _clean(attrs.get("REAC_LAST_INSPECTION_SCORE")),
        "_reac_date": attrs.get("REAC_LAST_INSPECTION_DATE"),
        "_reac_id": attrs.get("REAC_LAST_INSPECTION_ID"),
        "_pct_occupied": _safe_float(attrs.get("PCT_OCCUPIED")),
        "_rent_per_month": _safe_int(attrs.get("RENT_PER_MONTH")),
        "_annual_expense": _safe_float(attrs.get("ANNL_EXPNS_AMNT")),
        "_risk_category": _clean(attrs.get("OPIIS_RISK_CATEGORY")),
        "_troubled": _clean(attrs.get("TROUBLED_CODE")),
        "_contract1": _clean(attrs.get("CONTRACT1")),
        "_contract2": _clean(attrs.get("CONTRACT2")),
        "_contract_count": _safe_int(attrs.get("CONTRACT_COUNT")),
        "_program_type2": _clean(attrs.get("PROGRAM_TYPE2")),
        "_expiration1": attrs.get("EXPIRATION_DATE1"),
        "_expiration2": attrs.get("EXPIRATION_DATE2"),
        "_client_group_name": _clean(attrs.get("CLIENT_GROUP_NAME")),
    }


def _parse_insured_record(attrs: dict) -> dict | None:
    """Parse a single HUD-insured multifamily property record."""
    prop_id = str(attrs.get("PROPERTY_ID", "")).strip()
    if not prop_id:
        return None

    return {
        "property_id": prop_id,
        "property_name": _clean(attrs.get("PROPERTY_NAME_TEXT")),
        "address": _clean(attrs.get("ADDRESS_LINE1_TEXT")),
        "city": _clean(attrs.get("PLACED_BASE_CITY_NAME_TEXT")),
        "state": _clean(attrs.get("STD_ST")),
        "zip_code": _clean(attrs.get("STD_ZIP5")),
        "county_code": _clean(attrs.get("CNTY_NM2KX")),
        "congress_dist": _clean(attrs.get("CONGRESSIONAL_DISTRICT_CODE")),
        "owner_name": None,  # Not in insured dataset
        "mgmt_agent": _clean(attrs.get("MGMT_AGENT_ORG_NAME")),
        "program_type": _clean(attrs.get("PRIMARY_FINANCING_TYPE")),
        "assisted_units": _safe_int(attrs.get("MAXIMUM_CONTRACT_UNIT_COUNT")),
        "total_units": _safe_int(attrs.get("TOTAL_UNIT_COUNT")),
        "has_section_8": 1 if attrs.get("IS_SEC8_IND") == "Y" else 0,
        "has_lihtc": 0,
        "has_section_202": 1 if attrs.get("IS_202_CAPITAL_ADVANCE_IND") == "Y" else 0,
        "has_section_811": 1 if attrs.get("IS_811_CAPITAL_ADVANCE_IND") == "Y" else 0,
        "property_category": _clean(attrs.get("PROPERTY_CATEGORY_NAME")),
        "latitude": _safe_float(attrs.get("LAT")),
        "longitude": _safe_float(attrs.get("LON")),
        "source_file": "multifamily_insured",
        # Extra fields
        "_reac_score": _clean(attrs.get("REAC_LAST_INSPECTION_SCORE")),
        "_reac_date": attrs.get("REAC_LAST_INSPECTION_DATE"),
        "_fha_number": _clean(attrs.get("PRIMARY_FHA_NUMBER")),
        "_financing_type": _clean(attrs.get("PRIMARY_FINANCING_TYPE")),
        "_loan_amount": _safe_float(attrs.get("ORIGINAL_LOAN_AMOUNT")),
    }


def extract_reac_from_multifamily(mf_records: list[dict]) -> list[dict]:
    """Extract REAC inspection records embedded in multifamily data."""
    reac_records = []
    seen_ids = set()

    for rec in mf_records:
        reac_score = rec.get("_reac_score")
        reac_date = rec.get("_reac_date")
        reac_id = rec.get("_reac_id")

        if not reac_score or reac_score in ("", "None"):
            continue

        # Create a unique inspection ID
        if reac_id:
            insp_id = str(int(reac_id)) if isinstance(reac_id, float) else str(reac_id)
        else:
            insp_id = f"REAC-{rec['property_id']}"

        if insp_id in seen_ids:
            continue
        seen_ids.add(insp_id)

        # Convert epoch timestamp to date string
        date_str = ""
        if reac_date and isinstance(reac_date, (int, float)) and reac_date > 0:
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(reac_date / 1000, tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d")

        # Parse score (might be string like "97" or "97a")
        try:
            score_val = float(str(reac_score).rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ*"))
        except (ValueError, TypeError):
            score_val = None

        reac_records.append({
            "inspection_id": insp_id,
            "property_id": rec["property_id"],
            "property_name": rec.get("property_name", ""),
            "address": rec.get("address", ""),
            "city": rec.get("city", ""),
            "state": rec.get("state", ""),
            "zip_code": rec.get("zip_code", ""),
            "inspection_date": date_str,
            "inspection_score": score_val,
            "health_flag": 0,
            "smoke_detector_flag": 0,
            "property_type": rec.get("property_category", ""),
            "units": rec.get("total_units"),
            "rass_date": None,
            "source_file": rec.get("source_file", "multifamily_assisted"),
        })

    return reac_records


def extract_enforcement_from_multifamily(mf_records: list[dict]) -> list[dict]:
    """Extract enforcement-relevant records from multifamily data.

    Uses TROUBLED_CODE, OPIIS_RISK_CATEGORY, and failing REAC scores
    to create enforcement action records.
    """
    records = []
    seen = set()

    for rec in mf_records:
        prop_id = rec.get("property_id", "")
        if not prop_id:
            continue

        # Troubled properties
        troubled = rec.get("_troubled", "")
        if troubled and troubled not in ("", "None", "0"):
            key = f"troubled-{prop_id}"
            if key not in seen:
                seen.add(key)
                records.append({
                    "property_id": prop_id,
                    "owner_id": None,
                    "action_type": "troubled_designation",
                    "action_date": None,
                    "description": f"Property designated as troubled (code: {troubled})",
                    "financial_impact": None,
                    "resolution_status": "open",
                    "resolution_date": None,
                    "source": "multifamily_assisted",
                    "quality_score": 0.7,
                })

        # High-risk properties
        risk = rec.get("_risk_category", "")
        if risk and risk.lower() in ("high", "critical", "at risk", "at-risk"):
            key = f"risk-{prop_id}"
            if key not in seen:
                seen.add(key)
                records.append({
                    "property_id": prop_id,
                    "owner_id": None,
                    "action_type": "high_risk_designation",
                    "action_date": None,
                    "description": f"Property classified as {risk} risk (OPIIS)",
                    "financial_impact": None,
                    "resolution_status": "open",
                    "resolution_date": None,
                    "source": "multifamily_assisted",
                    "quality_score": 0.7,
                })

        # Failing REAC score (<60) = EH&S concern
        reac_score = rec.get("_reac_score", "")
        if reac_score and reac_score not in ("", "None"):
            try:
                score_val = float(str(reac_score).rstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ*"))
                if score_val < 60:
                    key = f"failing-{prop_id}"
                    if key not in seen:
                        seen.add(key)
                        reac_date = rec.get("_reac_date")
                        date_str = ""
                        if reac_date and isinstance(reac_date, (int, float)) and reac_date > 0:
                            from datetime import datetime, timezone
                            dt = datetime.fromtimestamp(reac_date / 1000, tz=timezone.utc)
                            date_str = dt.strftime("%Y-%m-%d")

                        records.append({
                            "property_id": prop_id,
                            "owner_id": None,
                            "action_type": "failing_inspection",
                            "action_date": date_str or None,
                            "description": f"REAC inspection score {score_val:.0f} (below 60 threshold)",
                            "financial_impact": None,
                            "resolution_status": "open",
                            "resolution_date": None,
                            "source": "REAC",
                            "quality_score": 0.8,
                        })
            except (ValueError, TypeError):
                pass

    return records


def extract_section8_from_multifamily(mf_records: list[dict]) -> list[dict]:
    """Extract Section 8 contract records embedded in multifamily assisted data.

    Each multifamily property can have up to 2 contracts (CONTRACT1/CONTRACT2).
    Each contract becomes a separate section8_contracts record.
    """
    from datetime import datetime, timezone, date

    today = date.today()
    three_years_days = 3 * 365
    records = []
    seen_contracts = set()

    for rec in mf_records:
        prop_id = rec.get("property_id", "")
        if not prop_id:
            continue

        # Process up to 2 contracts per property
        for idx, suffix in enumerate(["1", "2"], 1):
            contract_key = f"_contract{suffix}"
            exp_key = f"_expiration{suffix}"
            prog_key = "program_type" if suffix == "1" else "_program_type2"

            contract_num = rec.get(contract_key, "")
            if not contract_num:
                continue

            # Deduplicate
            if contract_num in seen_contracts:
                continue
            seen_contracts.add(contract_num)

            # Parse expiration date (epoch ms or string)
            exp_raw = rec.get(exp_key)
            exp_date_str = ""
            days_until = None
            is_expiring = 0

            if exp_raw is not None and exp_raw != "":
                exp_date_str = _parse_epoch_date(exp_raw)
                if exp_date_str:
                    try:
                        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
                        delta = (exp_date - today).days
                        days_until = delta
                        if 0 < delta <= three_years_days:
                            is_expiring = 1
                    except ValueError:
                        pass

            program_type = rec.get(prog_key, "")

            records.append({
                "contract_id": contract_num,
                "property_id": prop_id,
                "property_name": rec.get("property_name", ""),
                "address": rec.get("address", ""),
                "city": rec.get("city", ""),
                "state": rec.get("state", ""),
                "zip_code": rec.get("zip_code", ""),
                "county_code": rec.get("county_code", ""),
                "congress_dist": rec.get("congress_dist", ""),
                "owner_name": rec.get("owner_name", ""),
                "owner_type": "",
                "mgmt_agent": rec.get("mgmt_agent", ""),
                "program_type": program_type,
                "contract_term_months": None,
                "contract_start_date": None,
                "contract_end_date": exp_date_str,
                "assisted_units": rec.get("assisted_units"),
                "total_units": rec.get("total_units"),
                "annual_expense": rec.get("_annual_expense"),
                "rent_per_month": rec.get("_rent_per_month"),
                "is_expiring_soon": is_expiring,
                "days_until_expiration": days_until,
                "latitude": rec.get("latitude"),
                "longitude": rec.get("longitude"),
                "source_file": rec.get("source_file", "multifamily_assisted"),
            })

    return records


def _parse_epoch_date(val) -> str:
    """Convert an epoch millisecond timestamp or date string to YYYY-MM-DD."""
    from datetime import datetime, timezone

    if val is None:
        return ""

    # Try as epoch milliseconds (int or float)
    if isinstance(val, (int, float)):
        if val > 1e12:  # Epoch ms
            dt = datetime.fromtimestamp(val / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        elif val > 1e9:  # Epoch seconds
            dt = datetime.fromtimestamp(val, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        return ""

    # Try parsing string that looks like epoch
    s = str(val).strip()
    if not s:
        return ""
    try:
        num = float(s)
        if num > 1e12:
            dt = datetime.fromtimestamp(num / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        elif num > 1e9:
            dt = datetime.fromtimestamp(num, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        pass

    # Already a date string YYYY-MM-DD?
    if "-" in s and len(s) == 10 and s[4] == "-":
        return s

    # DD-MMM-YY format (e.g., "31-DEC-29", "31-AUG-26")
    if "-" in s and len(s) == 9:
        try:
            dt = datetime.strptime(s, "%d-%b-%y")
            # 2-digit year: Python uses 69 as pivot (00-68 → 2000s, 69-99 → 1900s)
            # For housing contracts, years like 26-50 should be 2026-2050
            # Python default handles this correctly for our range
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # DD-MMM-YYYY format
    if "-" in s:
        try:
            dt = datetime.strptime(s, "%d-%b-%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return ""


OCCUPANCY_TYPE_MAP = {
    # Elderly categories
    "elderly": "elderly",
    "wholly elderly housekeeping": "elderly",
    "wholly elderly congregate": "elderly",
    "wholly elderly - hskpg & congregat": "elderly",
    "partially elderly handicapped": "elderly",
    "partially elderly congregate": "elderly",
    "partially eld - hskpg & congregate": "elderly",
    # Family categories
    "family": "family",
    "families": "family",
    "families/individuals": "family",
    "individuals": "family",
    "indv. families - not eld/ handicap": "family",
    # Disabled categories
    "disabled": "disabled",
    "wholly developmentally disabled": "disabled",
    "wholly physically disabled": "disabled",
    "wholly physically handicapped": "disabled",
    "partially physically handicapped": "disabled",
    "chronically mentally ill": "disabled",
    # Mixed categories
    "mixed": "mixed",
    "family & elderly": "mixed",
    "elderly/disabled": "mixed",
    # Special needs / medical
    "special needs": "special_needs",
    "human acq. immunodeficiency virus": "special_needs",
    "assisted living care": "special_needs",
    "intermediate care facility": "special_needs",
    "skilled care facility": "special_needs",
    "general care": "special_needs",
}


def _normalize_occupancy_type(val) -> str | None:
    """Normalize CLIENT_GROUP_NAME to a standard occupancy type."""
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s:
        return None
    return OCCUPANCY_TYPE_MAP.get(s, s)


def _clean(val) -> str:
    """Clean a field value."""
    if val is None:
        return ""
    return str(val).strip()


def _safe_int(val) -> int | None:
    """Safely convert to int."""
    if val is None:
        return None
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    """Safely convert to float."""
    if val is None:
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None
