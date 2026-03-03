# MSHA Mining Safety & Enforcement Tracker

## Overview
Comprehensive structured database of U.S. mine safety data from the Mine Safety and Health Administration (MSHA). Cross-links mines, operators, accidents, inspections, violations, and penalties to produce operator safety profiles with composite risk scoring.

## Key Statistics
- **7.7M+ records** across 7 tables
- **91,587 mines** (6,590 active) across 55 states/territories
- **271,621 accidents** including 1,194 fatalities and 2,456 permanent disabilities
- **3M+ violations** with $1.8B in proposed penalties
- **49,673 operator profiles** with safety scores and risk tiers
- **Accident data spanning 2000–2026**

## Data Sources
All data from MSHA Open Government Data Portal:
- `arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip`
- `arlweb.msha.gov/OpenGovernmentData/DataSets/Accidents.zip`
- `arlweb.msha.gov/OpenGovernmentData/DataSets/Inspections.zip`
- `arlweb.msha.gov/OpenGovernmentData/DataSets/Violations.zip`
- `arlweb.msha.gov/OpenGovernmentData/DataSets/AssessedViolations.zip`
- `arlweb.msha.gov/OpenGovernmentData/DataSets/CivilPenaltyDocketsDecisions.zip`

## Architecture
```
src/
├── cli.py                    # Click CLI (init, scrape-*, build-profiles, export, stats, dashboard)
├── scrapers/downloader.py    # Bulk ZIP download + pipe-delimited parsing (uses curl, not httpx)
├── normalization/operators.py # Name normalization, profile building, safety scoring
├── validation/quality.py     # Quality scoring for all 6 record types
├── storage/database.py       # SQLite schema (7 tables, 16+ indexes, WAL mode)
├── export/exporter.py        # CSV, JSON, Markdown exports
└── dashboard/app.py          # Streamlit dashboard (8 sections)
```

## Technical Notes
- **MSHA blocks Python HTTP libraries** — downloader uses `subprocess.run(["curl", ...])` instead of httpx/requests
- **Pipe-delimited format** — raw data is `|`-separated with quoted values, not standard CSV
- **MINE_ID** is the universal foreign key across all datasets
- **Operator profiles** built via 5 bulk SQL GROUP BY queries (not N+1 per-operator queries)
- **Safety score** is a 5-component weighted formula: fatalities (25%), injuries (25%), violations/mine (20%), S&S violations (15%), penalty severity (15%)
- **Risk tiers**: LOW (>=0.8), MEDIUM (>=0.5), HIGH (>=0.3), CRITICAL (<0.3)

## Running
```bash
python3 -m src.cli pipeline        # Full pipeline (download + import + profiles + export)
python3 -m src.cli pipeline --skip-violations  # Skip large violations datasets
python3 -m src.cli dashboard       # Launch Streamlit dashboard
python3 -m pytest tests/ -v        # Run tests
```

## Database Schema
| Table | PK | Records |
|-------|-----|---------|
| mines | mine_id | 91,587 |
| accidents | document_no | 271,621 |
| inspections | event_no | 1,137,928 |
| violations | (event_no, violation_no) | 3,055,890 |
| assessed_violations | violation_no | 2,989,669 |
| penalties | docket_no | 93,565 |
| operator_profiles | profile_id (UNIQUE operator_id) | 49,673 |
