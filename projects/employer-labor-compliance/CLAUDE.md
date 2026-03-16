# Employer Labor Compliance Tracker

## Overview
Cross-agency employer labor violation database linking WHD wage theft cases,
OSHA safety inspections, and NLRB labor relations cases to build employer
compliance profiles.

## Data Sources
1. **DOL WHD** — Wage & Hour Division compliance actions via v4 API (6,998 cases, $45.5M back wages)
2. **OSHA** — Workplace safety inspections (pending — download interrupted)
3. **NLRB** — National Labor Relations Board cases (233,011 cases)
   - Primary source: labordata/nlrb-data nightly SQLite release (5.9M records)

## Architecture
```
src/
├── cli.py                    — Click CLI: scrape, extract, pipeline, stats, export, dashboard
├── scrapers/
│   ├── whd.py               — DOL WHD v4 API download/parse (363K raw records)
│   ├── osha.py              — OSHA v4 API download/parse
│   └── nlrb.py              — NLRB SQLite DB download/parse (labordata/nlrb-data)
├── normalization/
│   ├── employers.py          — Name normalization, DBA extraction, state codes
│   └── cross_linker.py       — 3-stage cross-linking (exact, fuzzy by state, employer profiles)
├── validation/
│   └── quality.py            — Quality scoring (WHD/OSHA/NLRB) + composite compliance score
├── storage/
│   └── database.py           — SQLite schema (5 tables), upserts, stats
├── export/
│   └── exporter.py           — CSV, JSON, Excel, Markdown exports
└── dashboard/
    └── app.py                — 8-section Streamlit dashboard
```

## Key Technical Details
- **Employer normalization**: Uppercase → strip DBA → strip suffixes (3 passes) → handle initials → expand abbreviations → collapse whitespace
- **Cross-linking**: Stage 1 (exact name) → Stage 2 (fuzzy by state, 85% threshold) → Stage 3 (employer profile aggregation)
- **Compliance scoring**: Log-scaled penalty accumulation across case volume, multi-agency presence, financial severity, fatalities, willful violations
- **Quality scoring**: Weighted component formula per source (0.0-1.0)

## Known Issues
See PROBLEMS.md. DOL API key obtained, WHD data loaded (P1 DONE). OSHA download pending.

## Running
```bash
python -m src.cli scrape       # Download raw data
python -m src.cli pipeline     # Full ETL pipeline
python -m src.cli stats        # Show database statistics
python -m src.cli export       # Export CSV/JSON/Excel/Markdown
python -m src.cli dashboard    # Launch Streamlit dashboard
```

## Testing
```bash
python -m pytest tests/ -v     # 115 tests
```
