"""CSV Extractor — parses downloaded CMS CSV files into validated records.

Reads raw CSV files from data/raw/, maps column names to our schema fields,
validates each row through Pydantic models, and returns lists of clean dicts.
"""

import csv
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console

from src.validation.schemas import SOURCE_SCHEMAS

console = Console()
PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"


# CMS CSV column name → our schema field name
# CMS datasets have inconsistent naming; this normalizes them.
COLUMN_MAPS = {
    "provider_info": {
        "federal_provider_number": "federal_provider_number",
        "provider_name": "provider_name",
        "provider_address": "provider_address",
        "provider_city": "provider_city",
        "provider_state": "provider_state",
        "provider_zip_code": "provider_zip_code",
        "provider_county_name": "provider_county_name",
        "provider_phone_number": "provider_phone_number",
        "ownership_type": "ownership_type",
        "number_of_certified_beds": "number_of_certified_beds",
        "number_of_residents_in_certified_beds": "number_of_residents_in_certified_beds",
        "provider_type": "provider_type",
        "legal_business_name": "legal_business_name",
        "overall_rating": "overall_rating",
        "health_inspection_rating": "health_inspection_rating",
        "staffing_rating": "staffing_rating",
        "quality_measure_rating": "quality_measure_rating",
        "total_weighted_health_survey_score": "total_weighted_health_survey_score",
        "number_of_facility_reported_incidents": "number_of_facility_reported_incidents",
        "number_of_substantiated_complaints": "number_of_substantiated_complaints",
        "number_of_fines": "number_of_fines",
        "total_amount_of_fines_in_dollars": "total_amount_of_fines_in_dollars",
        "number_of_payment_denials": "number_of_payment_denials",
        "total_number_of_penalties": "total_number_of_penalties",
    },
    "health_deficiencies": {
        "federal_provider_number": "federal_provider_number",
        "provider_name": "provider_name",
        "provider_state": "provider_state",
        "survey_date": "survey_date",
        "survey_type": "survey_type",
        "deficiency_tag_number": "deficiency_tag_number",
        "deficiency_description": "deficiency_description",
        "scope_severity_code": "scope_severity_code",
        "deficiency_corrected": "deficiency_corrected",
        "correction_date": "correction_date",
        "inspection_cycle": "inspection_cycle",
    },
    "penalties": {
        "federal_provider_number": "federal_provider_number",
        "provider_name": "provider_name",
        "provider_state": "provider_state",
        "penalty_type": "penalty_type",
        "fine_amount": "fine_amount",
        "penalty_date": "penalty_date",
        "penalty_status": "penalty_status",
    },
    "ownership": {
        "federal_provider_number": "federal_provider_number",
        "provider_name": "provider_name",
        "provider_state": "provider_state",
        "owner_name": "owner_name",
        "owner_type": "owner_type",
        "owner_percentage": "owner_percentage",
        "role_description": "role_description",
        "association_date": "association_date",
    },
    "survey_summary": {
        "federal_provider_number": "federal_provider_number",
        "provider_name": "provider_name",
        "provider_state": "provider_state",
        "survey_date": "survey_date",
        "survey_type": "survey_type",
        "total_number_of_health_deficiencies": "total_number_of_health_deficiencies",
        "total_number_of_fire_safety_deficiencies": "total_number_of_fire_safety_deficiencies",
    },
    "quality_measures": {
        "federal_provider_number": "federal_provider_number",
        "provider_name": "provider_name",
        "provider_state": "provider_state",
        "measure_code": "measure_code",
        "measure_description": "measure_description",
        "measure_period": "measure_period",
        "score": "score",
        "footnote": "footnote",
        "used_in_quality_measure_five_star_rating": "used_in_quality_measure_five_star_rating",
    },
}


def _normalize_column_name(name: str) -> str:
    """Normalize a CMS column name to lowercase snake_case."""
    return (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("'", "")
    )


def _find_column_match(normalized_cols: dict, target_field: str) -> Optional[str]:
    """Find the best matching column for a target field name.

    CMS datasets sometimes use slightly different naming conventions.
    This fuzzy-matches against normalized column names.
    """
    # Exact match on normalized name
    if target_field in normalized_cols:
        return normalized_cols[target_field]

    # Try common CMS variations
    variations = [
        target_field.replace("_", ""),
        target_field.replace("number_of_", ""),
        target_field.replace("total_", ""),
        target_field.replace("provider_", ""),
    ]
    for var in variations:
        if var in normalized_cols:
            return normalized_cols[var]

    return None


def extract_source(source_key: str) -> list[dict]:
    """Extract records from a single CMS CSV file.

    Returns a list of validated dicts ready for storage.
    """
    csv_path = RAW_DIR / f"{source_key}.csv"
    if not csv_path.exists():
        console.print(f"  [red]✗[/red] {source_key}: CSV not found at {csv_path}")
        return []

    schema_class = SOURCE_SCHEMAS.get(source_key)
    column_map = COLUMN_MAPS.get(source_key, {})

    if not schema_class:
        console.print(f"  [red]✗[/red] {source_key}: No schema defined")
        return []

    console.print(f"  Parsing [cyan]{source_key}[/cyan]...")

    try:
        # Read with pandas for robust CSV handling
        df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    except Exception as e:
        console.print(f"  [red]✗[/red] {source_key}: Failed to read CSV: {e}")
        return []

    # Build column name mapping from CSV columns to our field names
    normalized_cols = {_normalize_column_name(col): col for col in df.columns}
    col_mapping = {}
    for csv_field, our_field in column_map.items():
        original_col = _find_column_match(normalized_cols, csv_field)
        if original_col:
            col_mapping[original_col] = our_field

    records = []
    errors = 0

    for _, row in df.iterrows():
        raw_dict = {}
        for csv_col, our_field in col_mapping.items():
            val = row.get(csv_col)
            if pd.isna(val):
                val = None
            raw_dict[our_field] = val

        # Skip rows without a provider number
        if not raw_dict.get("federal_provider_number"):
            errors += 1
            continue

        try:
            validated = schema_class.model_validate(raw_dict)
            records.append(validated.model_dump())
        except Exception:
            errors += 1

    console.print(
        f"  [green]✓[/green] {source_key}: {len(records):,} records extracted"
        + (f" ({errors:,} skipped)" if errors else "")
    )
    return records


def extract_all() -> dict[str, list[dict]]:
    """Extract records from all downloaded CMS CSV files.

    Returns dict of source_key -> list of validated record dicts.
    """
    results = {}
    console.print("\n[bold blue]Extracting CMS datasets...[/bold blue]\n")

    for source_key in SOURCE_SCHEMAS:
        records = extract_source(source_key)
        results[source_key] = records

    total = sum(len(v) for v in results.values())
    console.print(f"\n[bold]Extraction complete: {total:,} total records[/bold]")
    return results
