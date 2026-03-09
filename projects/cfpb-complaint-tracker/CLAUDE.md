# CFPB Consumer Complaint Cross-Linked Analysis

## Overview

Cross-links CFPB consumer complaints with FDIC institution data, FFIEC CRA ratings, multi-agency enforcement actions (CFPB, OCC, Federal Reserve, FDIC), HMDA mortgage lending summaries, and FDIC quarterly financial data. Produces institution-level risk profiles that combine complaint patterns, enforcement history, financial health, and lending fairness into a single composite score.

The core value is cross-linkage: the CFPB complaint dataset names companies in free text. This project resolves those names to FDIC certificate numbers via a three-stage entity resolution pipeline, enabling every complaint to be attributed to a regulated institution with full regulatory context attached.

## Data Sources

| Source | Module | URL |
|--------|--------|-----|
| CFPB Complaints | `src/scrapers/cfpb_downloader.py` | files.consumerfinance.gov/ccdb/complaints.csv.zip |
| FDIC Institutions | `src/scrapers/fdic_downloader.py` | api.fdic.gov/banks/institutions |
| CRA Ratings | `src/scrapers/cra_downloader.py` | ffiec.gov/cra/craflatfiles.htm (manual download) |
| CFPB Enforcement | `src/scrapers/enforcement_scraper.py` | consumerfinance.gov/enforcement/actions/ |
| OCC Enforcement | `src/scrapers/occ_enforcement.py` | occ.gov/topics/laws-and-regulations/enforcement-actions/ |
| Federal Reserve Enforcement | `src/scrapers/fed_enforcement.py` | federalreserve.gov/supervisionreg/enforcementactions.htm |
| FDIC Enforcement | `src/scrapers/fdic_enforcement.py` | fdic.gov/bank/individual/enforcement/ |
| FDIC Financials | `src/scrapers/fdic_financials.py` | banks.data.fdic.gov/api/financials |
| HMDA | `src/scrapers/hmda_downloader.py` | ffiec.cfpb.gov/v2/data-browser-api |

## Architecture

```
src/
├── cli.py                          # Click CLI: scrape, normalize, validate, export,
│                                   #   pipeline, stats, dashboard, risk-profiles
├── scrapers/
│   ├── cfpb_downloader.py          # Streaming ZIP/CSV download (600MB), batch insert
│   ├── fdic_downloader.py          # FDIC BankFind REST API, paginated 10K/page
│   ├── cra_downloader.py           # FFIEC flat file parser (pipe or comma delimited)
│   ├── enforcement_scraper.py      # CFPB enforcement HTML scraper, regex extraction
│   ├── occ_enforcement.py          # OCC enforcement HTML scraper
│   ├── fed_enforcement.py          # Federal Reserve enforcement HTML scraper
│   ├── fdic_enforcement.py         # FDIC enforcement HTML scraper
│   ├── fdic_financials.py          # FDIC financials REST API, quarterly Call Report data
│   └── hmda_downloader.py          # FFIEC HMDA API, institution-level summaries
├── normalization/
│   └── institutions.py             # Three-stage entity resolution: exact → normalized → fuzzy
├── validation/
│   ├── quality.py                  # Quality scoring for institution records (0.0-1.0)
│   └── risk_scoring.py             # Composite risk profile computation
├── storage/
│   └── database.py                 # SQLite schema (10 tables), CRUD, migrations, stats
├── export/
│   └── exporter.py                 # CSV, JSON, Excel, Markdown exports
└── dashboard/
    └── app.py                      # Streamlit dashboard, 11 sections, dark theme
```

## Database Schema

Database file: `data/cfpb_tracker.db` (WAL mode, foreign keys enabled)

| Table | Primary Key | Description |
|-------|-------------|-------------|
| `cfpb_complaints` | `complaint_id` | All CFPB consumer complaint records |
| `financial_institutions` | `cert_number` | All FDIC-insured banks and thrifts |
| `cra_ratings` | `id` (autoincrement) | FFIEC CRA exam ratings per institution |
| `enforcement_actions` | `action_id` (autoincrement) | CFPB enforcement actions (legacy table) |
| `institution_complaints` | `(complaint_id, cert_number)` | Cross-link: complaints matched to institutions |
| `pipeline_runs` | `id` (autoincrement) | Pipeline execution tracking |
| `institution_financials` | `(cert_number, report_date)` | Quarterly Call Report financial data |
| `regulatory_enforcement` | `action_id` (text) | Unified multi-agency enforcement (CFPB/OCC/Fed/FDIC) |
| `institution_risk_profiles` | `cert_number` | Composite risk scores and tier classifications |
| `hmda_institution_summary` | `(lei, report_year)` | HMDA mortgage lending summaries |

Key indexes: `cfpb_complaints(company)`, `cfpb_complaints(state)`, `cfpb_complaints(date_received)`, `financial_institutions(canonical_name)`, `institution_complaints(cert_number)`, `regulatory_enforcement(agency)`, `institution_risk_profiles(risk_tier)`, `hmda_institution_summary(cert_number)`

## CLI Commands

```bash
# Scrape sources
python -m src.cli scrape --source [cfpb|fdic|cra|enforcement|financials|occ|fed|fdic-enforcement|hmda|all|all-enriched]
python -m src.cli scrape --source all-enriched --no-cache   # force re-download

# Entity resolution
python -m src.cli normalize --strategy [exact|normalized|fuzzy|all] --threshold 85

# Quality scoring
python -m src.cli validate --update-scores

# Risk profiles
python -m src.cli risk-profiles

# Export
python -m src.cli export --format [csv|json|excel|markdown|all] --output data/exports/ --min-quality 0.0

# Full pipeline
python -m src.cli pipeline --full --enriched

# Statistics (rich table in terminal)
python -m src.cli stats

# Dashboard
python -m src.cli dashboard --port 8501
```

## Pipeline Execution Order

The `pipeline --full --enriched` command runs these stages:

1. FDIC institutions (base entities for all cross-linking)
2. CFPB complaints (primary dataset, ~600MB download)
3. CFPB enforcement actions (HTML scrape)
4. CRA ratings (requires manual FFIEC file download)
5. Entity resolution (links complaint company names to FDIC cert numbers)
6. Quality scoring
7. FDIC financials (enrichment 1: quarterly Call Report data)
8. Multi-agency enforcement: OCC, Federal Reserve, FDIC (enrichment 2)
9. Migrate CFPB enforcement into unified `regulatory_enforcement` table
10. HMDA lending data (enrichment 4)
11. Institution risk profiles (enrichment 3)
12. Final quality score update
13. Full export (CSV, JSON, Excel, Markdown)

## Entity Resolution

Implemented in `src/normalization/institutions.py`. Three-stage pipeline applied to each distinct company name in `cfpb_complaints`:

1. **Exact match** — uppercase comparison against `financial_institutions.institution_name`. Confidence: 1.0
2. **Normalized match** — strip known legal suffixes (N.A., FSB, SSB, National Association, Inc., LLC, Corp., Bank, Trust, etc.), remove punctuation, collapse whitespace, uppercase. Confidence: 0.95
3. **Fuzzy match** — `thefuzz.fuzz.token_sort_ratio` against all normalized institution names. Default threshold: 85. Confidence: score/100.0

Cross-links are inserted into `institution_complaints` via bulk `INSERT...SELECT` SQL rather than loading millions of records into Python memory.

## Quality Scoring Formula

Applied to `financial_institutions` records. Weights sum to 1.0:

| Component | Weight | Condition |
|-----------|--------|-----------|
| `has_institution_name` | 0.10 | Non-empty institution name |
| `has_location` | 0.10 | Both city and state present |
| `has_financial_data` | 0.10 | Record in `institution_financials` |
| `has_complaints_linked` | 0.20 | At least one linked complaint |
| `has_cra_rating` | 0.15 | At least one CRA rating on file |
| `has_enforcement_history` | 0.15 | Record in `enforcement_actions` or `regulatory_enforcement` |
| `has_regulator_info` | 0.10 | Non-empty regulator field |
| `has_cert_number` | 0.10 | FDIC cert number present |

Minimum passing threshold: **0.40**

## Risk Scoring Formula

Applied to `institution_risk_profiles`. Six weighted dimensions (higher score = lower risk):

| Dimension | Weight | Logic |
|-----------|--------|-------|
| Complaint volume (normalized by assets) | 0.25 | Complaints per $B assets; score 1.0 (none) to 0.1 (>1000/B) |
| Complaint resolution | 0.10 | Timely response rate (70%) + low dispute rate (30%) |
| Enforcement severity | 0.20 | Penalty amount and action count; score 1.0 (none) to 0.0 (>$1B) |
| Financial health | 0.15 | Avg of Tier 1 capital ratio, ROA, noncurrent loans pct |
| Lending fairness | 0.15 | HMDA denial rate; score 1.0 (<=5%) to 0.1 (>50%) |
| CRA rating | 0.15 | Outstanding=1.0, Satisfactory=0.7, Needs to Improve=0.3, Noncompliance=0.0 |

Risk tiers: LOW (>=0.8), MEDIUM (>=0.5), HIGH (>=0.3), CRITICAL (<0.3)

Asset tiers (from FDIC financials): Community (<$1B), Regional ($1B-$10B), Large ($10B-$100B), Megabank (>$100B)

## Dashboard Sections (11 total)

1. **National Overview** — KPI cards, complaint volume over time, top 10 companies by complaint count
2. **Institution Explorer** — Search bar, institution detail panel, linked complaints, CRA rating, enforcement count, quality score
3. **Complaint Analysis** — Product/sub-product breakdown, issue analysis, company response rates, submission channels
4. **Enforcement Timeline** — Actions by type (Consent Order, Complaint, Order, Lawsuit, Settlement), timeline chart, detail table
5. **Geographic Analysis** — US choropleth (complaint density), top/bottom 15 states, full state table
6. **CRA vs. Complaints** — CRA rating distribution bar chart, scatter plot (CRA rating vs. complaint count), outlier detection
7. **Trends & Patterns** — YoY product trends, monthly patterns, weekly day-of-week patterns, timeliness trends, emerging issues, top company timelines
8. **Financial Health** — Assets, Tier 1 capital, leverage ratio, ROA, ROE, noncurrent loans, efficiency ratio, quarterly trend charts
9. **Multi-Agency Enforcement** — Unified enforcement across CFPB/OCC/Fed/FDIC; agency breakdown, timeline, penalty rankings
10. **Institution Risk Profiles** — Risk tier distribution, sortable profile table, peer scatter (risk score vs. assets)
11. **Fair Lending Analysis** — HMDA denial rates, origination counts, average loan amounts, multi-year trends

## Dashboard Theme

```toml
[theme]
primaryColor = "#0984E3"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1B2A4A"
textColor = "#E2E8F0"
```

Plotly template: `plotly_dark` with transparent backgrounds.

DB path resolution order: `CFPB_DB_PATH` env var → `data/cfpb_tracker_deploy.db` → `data/cfpb_tracker.db`

## CRA Data Note

The FFIEC blocks automated downloads of CRA flat files. To populate CRA ratings:
1. Go to https://www.ffiec.gov/cra/craflatfiles.htm
2. Download the CRA disclosure flat file
3. Place the file in `data/raw/` (any filename containing "cra")
4. Run `python -m src.cli scrape --source cra`

Without this file, the CRA pipeline completes with zero records.

## Known Limitations

- CRA ratings require manual download (FFIEC blocks automation)
- CFPB complaint CSV is ~600MB compressed / ~2GB extracted; first run requires disk space
- Full database with all enrichment sources may reach 10GB+, which exceeds Railway/Heroku free tier limits (see PROBLEMS.md P2)
- Fuzzy matching at threshold 85 may produce false positive cross-links for institutions with similar names
- HMDA data only covers mortgage lending; other product types are not represented

## Testing

```bash
python -m pytest tests/ -v   # 164 tests
```

## Deployment

Railway-ready with Procfile (`web: streamlit run src/dashboard/app.py --server.port $PORT --server.headless true`). Set `CFPB_DB_PATH` environment variable to point at the database.
