# Employer Labor Compliance Tracker

## Overview
Cross-agency employer labor violation database linking WHD wage theft cases,
OSHA safety inspections, and NLRB labor relations cases to build employer
compliance profiles.

## Data Sources
1. **DOL WHD** — Wage & Hour Division compliance actions (back wages, penalties, FLSA/FMLA violations)
2. **OSHA** — Workplace safety inspections (violations, penalties, fatalities)
3. **NLRB** — National Labor Relations Board cases (unfair labor practices, union elections)
   - Primary source: labordata/nlrb-data nightly SQLite release (5.9M records)

## Architecture
```
src/
├── cli.py                    — Click CLI: scrape, extract, pipeline, stats, export, dashboard
├── scrapers/
│   ├── whd.py               — DOL WHD bulk CSV download/parse
│   ├── osha.py              — OSHA inspection CSV download/parse
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
See PROBLEMS.md. Key blocker: DOL migrated from enforcedata.dol.gov → data.dol.gov,
breaking bulk CSV download URLs. NLRB data is fully accessible via GitHub bulk download.

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
python -m pytest tests/ -v     # 107 tests
```
