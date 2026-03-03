"""Download and parse MSHA Open Government bulk datasets."""

import csv
import io
import os
import subprocess
import zipfile

BASE_URL = "https://arlweb.msha.gov/OpenGovernmentData/DataSets"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")

DATASETS = {
    "mines": "Mines.zip",
    "accidents": "Accidents.zip",
    "inspections": "Inspections.zip",
    "violations": "Violations.zip",
    "assessed_violations": "AssessedViolations.zip",
    "penalties": "CivilPenaltyDocketsDecisions.zip",
    "employment_yearly": "MinesProdYearly.zip",
    "controller_history": "ControllerOperatorHistory.zip",
    "orders_issued": "OrdersIssued.zip",
}


def download_dataset(name: str, force: bool = False) -> str:
    """Download a dataset ZIP file and return the path to the extracted text file."""
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset: {name}. Available: {list(DATASETS.keys())}")

    os.makedirs(RAW_DIR, exist_ok=True)
    zip_filename = DATASETS[name]
    zip_path = os.path.join(RAW_DIR, zip_filename)

    # Download if not cached (use curl — MSHA blocks Python HTTP libraries)
    if not os.path.exists(zip_path) or force:
        url = f"{BASE_URL}/{zip_filename}"
        print(f"  Downloading {url}...")
        result = subprocess.run(
            ["curl", "-sL", "-o", zip_path, url],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        size = os.path.getsize(zip_path)
        print(f"  Saved {zip_path} ({size:,} bytes)")
    else:
        print(f"  Using cached {zip_path}")

    # Extract
    with zipfile.ZipFile(zip_path, "r") as zf:
        txt_files = [n for n in zf.namelist() if n.lower().endswith(".txt")]
        if not txt_files:
            raise ValueError(f"No .txt files found in {zip_path}")
        txt_name = txt_files[0]
        txt_path = os.path.join(RAW_DIR, txt_name)
        zf.extract(txt_name, RAW_DIR)
        print(f"  Extracted {txt_path}")
        return txt_path


def _clean_val(val: str) -> str:
    """Strip quotes and whitespace from a pipe-delimited value."""
    return val.strip().strip('"').strip()


def _parse_int(val: str) -> int | None:
    """Parse an integer, return None for empty/invalid."""
    val = _clean_val(val)
    if not val or val == "?":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_float(val: str) -> float | None:
    """Parse a float, return None for empty/invalid."""
    val = _clean_val(val)
    if not val or val == "?":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_pipe_delimited(file_path: str) -> list[dict]:
    """Parse a pipe-delimited text file into a list of dicts."""
    records = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            cleaned = {}
            for k, v in row.items():
                if k is None:
                    continue
                cleaned[k.strip()] = _clean_val(v) if v else ""
            records.append(cleaned)
    return records


def parse_mines(file_path: str) -> list[dict]:
    """Parse mines dataset into database-ready dicts."""
    raw = parse_pipe_delimited(file_path)
    results = []
    for r in raw:
        results.append({
            "mine_id": r.get("MINE_ID", ""),
            "mine_name": r.get("CURRENT_MINE_NAME", ""),
            "coal_metal_ind": r.get("COAL_METAL_IND", ""),
            "mine_type": r.get("CURRENT_MINE_TYPE", ""),
            "mine_status": r.get("CURRENT_MINE_STATUS", ""),
            "status_date": r.get("CURRENT_STATUS_DT", ""),
            "controller_id": r.get("CURRENT_CONTROLLER_ID", ""),
            "controller_name": r.get("CURRENT_CONTROLLER_NAME", ""),
            "operator_id": r.get("CURRENT_OPERATOR_ID", ""),
            "operator_name": r.get("CURRENT_OPERATOR_NAME", ""),
            "state": r.get("STATE", ""),
            "fips_cnty_cd": r.get("FIPS_CNTY_CD", ""),
            "fips_cnty_nm": r.get("FIPS_CNTY_NM", ""),
            "company_type": r.get("COMPANY_TYPE", ""),
            "district": r.get("DISTRICT", ""),
            "primary_sic": r.get("PRIMARY_SIC", ""),
            "primary_sic_cd": r.get("PRIMARY_SIC_CD", ""),
            "secondary_sic": r.get("SECONDARY_SIC", ""),
            "latitude": r.get("LATITUDE", ""),
            "longitude": r.get("LONGITUDE", ""),
            "no_employees": _parse_int(r.get("NO_EMPLOYEES", "")),
            "days_per_week": _parse_int(r.get("DAYS_PER_WEEK", "")),
            "hours_per_shift": _parse_int(r.get("HOURS_PER_SHIFT", "")),
            "nearest_town": r.get("NEAREST_TOWN", ""),
            "quality_score": None,
        })
    return results


def parse_accidents(file_path: str) -> list[dict]:
    """Parse accidents dataset into database-ready dicts."""
    raw = parse_pipe_delimited(file_path)
    results = []
    for r in raw:
        results.append({
            "document_no": r.get("DOCUMENT_NO", ""),
            "mine_id": r.get("MINE_ID", ""),
            "controller_id": r.get("CONTROLLER_ID", ""),
            "controller_name": r.get("CONTROLLER_NAME", ""),
            "operator_id": r.get("OPERATOR_ID", ""),
            "operator_name": r.get("OPERATOR_NAME", ""),
            "contractor_id": r.get("CONTRACTOR_ID", ""),
            "subunit": r.get("SUBUNIT", ""),
            "accident_dt": r.get("ACCIDENT_DT", ""),
            "cal_yr": _parse_int(r.get("CAL_YR", "")),
            "degree_injury_cd": r.get("DEGREE_INJURY_CD", ""),
            "degree_injury": r.get("DEGREE_INJURY", ""),
            "fips_state_cd": r.get("FIPS_STATE_CD", ""),
            "ug_location": r.get("UG_LOCATION", ""),
            "mining_equip": r.get("MINING_EQUIP", ""),
            "equip_mfr_name": r.get("EQUIP_MFR_NAME", ""),
            "classification": r.get("CLASSIFICATION", ""),
            "accident_type": r.get("ACCIDENT_TYPE", ""),
            "no_injuries": _parse_int(r.get("NO_INJURIES", "")),
            "tot_exper": _parse_float(r.get("TOT_EXPER", "")),
            "mine_exper": _parse_float(r.get("MINE_EXPER", "")),
            "job_exper": _parse_float(r.get("JOB_EXPER", "")),
            "occupation": r.get("OCCUPATION", ""),
            "activity": r.get("ACTIVITY", ""),
            "injury_source": r.get("INJURY_SOURCE", ""),
            "nature_injury": r.get("NATURE_INJURY", ""),
            "inj_body_part": r.get("INJ_BODY_PART", ""),
            "schedule_charge": _parse_int(r.get("SCHEDULE_CHARGE", "")),
            "days_restrict": _parse_int(r.get("DAYS_RESTRICT", "")),
            "days_lost": _parse_int(r.get("DAYS_LOST", "")),
            "immed_notify": r.get("IMMED_NOTIFY", ""),
            "narrative": r.get("NARRATIVE", ""),
            "coal_metal_ind": r.get("COAL_METAL_IND", ""),
            "quality_score": None,
        })
    return results


def parse_inspections(file_path: str) -> list[dict]:
    """Parse inspections dataset into database-ready dicts."""
    raw = parse_pipe_delimited(file_path)
    results = []
    for r in raw:
        results.append({
            "event_no": r.get("EVENT_NO", ""),
            "mine_id": r.get("MINE_ID", ""),
            "inspection_begin_dt": r.get("INSPECTION_BEGIN_DT", ""),
            "inspection_end_dt": r.get("INSPECTION_END_DT", ""),
            "controller_id": r.get("CONTROLLER_ID", ""),
            "controller_name": r.get("CONTROLLER_NAME", ""),
            "operator_id": r.get("OPERATOR_ID", ""),
            "operator_name": r.get("OPERATOR_NAME", ""),
            "cal_yr": _parse_int(r.get("CAL_YR", "")),
            "activity_code": r.get("ACTIVITY_CODE", ""),
            "activity": r.get("ACTIVITY", ""),
            "coal_metal_ind": r.get("COAL_METAL_IND", ""),
            "quality_score": None,
        })
    return results


def parse_violations(file_path: str) -> list[dict]:
    """Parse violations dataset into database-ready dicts."""
    raw = parse_pipe_delimited(file_path)
    results = []
    for r in raw:
        results.append({
            "event_no": r.get("EVENT_NO", ""),
            "violation_no": r.get("VIOLATION_NO", ""),
            "mine_id": r.get("MINE_ID", ""),
            "controller_id": r.get("CONTROLLER_ID", ""),
            "controller_name": r.get("CONTROLLER_NAME", ""),
            "violator_id": r.get("VIOLATOR_ID", ""),
            "violator_name": r.get("VIOLATOR_NAME", ""),
            "violator_type": r.get("VIOLATOR_TYPE_CD", "") or r.get("VIOLATOR_TYPE", ""),
            "mine_name": r.get("MINE_NAME", ""),
            "mine_type": r.get("MINE_TYPE", ""),
            "coal_metal_ind": r.get("COAL_METAL_IND", ""),
            "violation_issue_dt": r.get("VIOLATION_ISSUE_DT", ""),
            "cal_yr": _parse_int(r.get("CAL_YR", "")),
            "sig_sub": r.get("SIG_SUB", ""),
            "section_of_act": r.get("SECTION_OF_ACT", ""),
            "section_of_act_desc": r.get("SECTION_OF_ACT_DESC", ""),
            "part_section": r.get("PART_SECTION", ""),
            "part_section_desc": r.get("PART_SECTION_DESC", ""),
            "proposed_penalty": _parse_float(r.get("PROPOSED_PENALTY", "")),
            "amount_paid": _parse_float(r.get("AMOUNT_PAID", "")),
            "quality_score": None,
        })
    return results


def parse_assessed_violations(file_path: str) -> list[dict]:
    """Parse assessed violations dataset into database-ready dicts."""
    raw = parse_pipe_delimited(file_path)
    results = []
    for r in raw:
        results.append({
            "violation_no": r.get("VIOLATION_NO", ""),
            "assessed_id": r.get("ASSESSED_ID", "") or r.get("ASSESSMENT_NO", ""),
            "mine_id": r.get("MINE_ID", ""),
            "controller_id": r.get("CONTROLLER_ID", ""),
            "controller_name": r.get("CONTROLLER_NAME", ""),
            "operator_id": r.get("OPERATOR_ID", ""),
            "operator_name": r.get("OPERATOR_NAME", ""),
            "cal_yr": _parse_int(r.get("CAL_YR", "")),
            "violation_issue_dt": r.get("VIOLATION_ISSUE_DT", ""),
            "section_of_act": r.get("SECTION_OF_ACT", ""),
            "part_section": r.get("PART_SECTION", ""),
            "proposed_penalty_amt": _parse_float(r.get("PROPOSED_PENALTY_AMT", "")),
            "paid_proposed_penalty_amt": _parse_float(r.get("PAID_PROPOSED_PENALTY_AMT", "")),
            "penalty_points": _parse_int(r.get("PENALTY_POINTS", "")),
            "sig_sub": r.get("SIG_SUB", ""),
            "likely": r.get("LIKELY", ""),
            "injury_illness": r.get("INJURY_ILLNESS", ""),
            "negligence": r.get("NEGLIGENCE", ""),
            "gravity": r.get("GRAVITY", ""),
            "quality_score": None,
        })
    return results


def parse_penalties(file_path: str) -> list[dict]:
    """Parse civil penalty docket records into database-ready dicts."""
    raw = parse_pipe_delimited(file_path)
    results = []
    for r in raw:
        results.append({
            "docket_no": r.get("DOCKET_NO", "") or r.get("CASE_NO", ""),
            "mine_id": r.get("MINE_ID", ""),
            "controller_id": r.get("CONTROLLER_ID", ""),
            "controller_name": r.get("CONTROLLER_NAME", ""),
            "operator_id": r.get("OPERATOR_ID", ""),
            "operator_name": r.get("OPERATOR_NAME", ""),
            "case_status": r.get("CASE_STATUS", "") or r.get("STATUS", ""),
            "proposed_penalty": _parse_float(r.get("PROPOSED_PENALTY", "")),
            "amount_assessed": _parse_float(r.get("AMOUNT_ASSESSED", "") or r.get("ASSESSED_AMT", "")),
            "amount_paid": _parse_float(r.get("AMOUNT_PAID", "") or r.get("PAID_AMT", "")),
            "cal_yr": _parse_int(r.get("CAL_YR", "")),
            "quality_score": None,
        })
    return results
