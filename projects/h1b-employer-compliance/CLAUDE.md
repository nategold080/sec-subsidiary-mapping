# H-1B Employer Compliance Tracker — Project Documentation

## Overview
Cross-linked database of H-1B employer data from three federal sources: DOL LCA filings (480K+), USCIS petition outcomes (209K), and DOL enforcement actions (11). Includes 54,858 employer compliance profiles with composite scores.

## Architecture

### Data Pipeline
```
DOL LCA Excel → parse_lca() → score_lca() → upsert_lca()
USCIS CSV → parse_uscis_csv() → score_uscis() → upsert_uscis()
DOL WHD HTML → parse_debarment_html() → upsert_debarments()
→ build_cross_links() → build_employer_profiles() → export_all()
```

### Database Schema (SQLite, WAL mode)
- `lca_applications` — 480K+ records, PK: case_number
- `uscis_employers` — 209K records, PK: employer_key (name|state|year)
- `whd_violations` — PK: case_id (currently empty, needs WHD API key)
- `debarments` — 11 records, PK: debar_id
- `employer_profiles` — 54K+ records, PK: profile_id
- `cross_links` — 131K+ records, links between all tables

### Key Modules
- `src/scrapers/lca.py` — DOL OFLC Excel download and parsing (openpyxl, read-only mode)
- `src/scrapers/uscis.py` — USCIS CSV download and parsing
- `src/scrapers/whd.py` — Debarment/willful violator HTML scraping
- `src/normalization/employers.py` — Name normalization, EIN formatting, fuzzy matching, wage annualization
- `src/normalization/cross_linker.py` — Cross-linking engine and profile builder
- `src/validation/quality.py` — Quality scoring (per-record) and compliance scoring (per-employer)
- `src/storage/database.py` — SQLite schema, upsert functions, stats
- `src/export/exporter.py` — CSV, JSON, Markdown exports
- `src/cli.py` — Click CLI with pipeline, scrape, crosslink, export, stats, dashboard commands

### Technical Notes
- LCA column names vary between fiscal years — handled via `_field_aliases()` mapping
- USCIS URL pattern: `h1b_datahubexport-{YEAR}.csv` (confirmed working FY2020-2023)
- DOL CDN uses Varnish with intermittent rate limiting (HTTP 405) — use 3-5s delays
- Cross-linking uses O(N) exact normalized name matching — fuzzy matching removed for performance
- CORP_SUFFIXES reduced to legal entity designations only (was over-stripping descriptive words)
- Employer profiles use batch INSERT for performance (~15s for 54K profiles)

### Compliance Score Formula
```
wage_component = min(avg_wage_ratio / 1.5, 1.0) × 0.40
approval_component = (approval_rate / 100) × 0.25
enforcement_component = inverse_violations × 0.25
debarment_component = (0 if debarred, 1 otherwise) × 0.10
score = sum(components) / sum(active_weights)
```

## CLI Commands
```bash
python3 -m src.cli init          # Initialize database
python3 -m src.cli scrape-lca    # Download LCA data
python3 -m src.cli scrape-uscis  # Download USCIS data
python3 -m src.cli scrape-whd    # Download enforcement data
python3 -m src.cli crosslink     # Build cross-links and profiles
python3 -m src.cli export        # Generate exports
python3 -m src.cli stats         # Show statistics
python3 -m src.cli pipeline      # Run everything
python3 -m src.cli dashboard     # Launch Streamlit
```

## Data Source URLs
- LCA: `https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/LCA_Disclosure_Data_FY{YEAR}_Q{QUARTER}.xlsx`
- USCIS: `https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-{YEAR}.csv`
- Debarments: `https://www.dol.gov/agencies/whd/immigration/h1b/debarment`
- Willful Violators: `https://www.dol.gov/agencies/whd/immigration/h1b/willful-violator-list`
- WHD API (needs key): `https://apiprod.dol.gov/v4/get/WHD/enforcement/json`
