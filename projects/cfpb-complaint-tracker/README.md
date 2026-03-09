# CFPB Consumer Complaint Cross-Linked Analysis

The first structured database cross-linking CFPB consumer complaints with FDIC institution data, CRA ratings, multi-agency enforcement actions, HMDA lending data, and quarterly financial performance — enabling institution-level risk profiling that no single government source provides.

## Key Numbers

| Metric | Value |
|--------|-------|
| CFPB Complaints | pending pipeline execution |
| FDIC Institutions | pending pipeline execution |
| CRA Rating Records | pending pipeline execution |
| CFPB Enforcement Actions | pending pipeline execution |
| OCC Enforcement Actions | pending pipeline execution |
| Fed Enforcement Actions | pending pipeline execution |
| FDIC Enforcement Orders | pending pipeline execution |
| HMDA Institution Summaries | pending pipeline execution |
| FDIC Financial Records | pending pipeline execution |
| Cross-Links (complaints to institutions) | pending pipeline execution |
| Institution Risk Profiles | pending pipeline execution |
| Tests | 164 passing |

## Data Sources

| Source | URL | Notes |
|--------|-----|-------|
| CFPB Complaints | files.consumerfinance.gov/ccdb/complaints.csv.zip | ~600MB bulk CSV ZIP, streaming parse |
| FDIC Institutions | api.fdic.gov/banks/institutions | REST API, paginated, all FDIC-insured banks and thrifts |
| FFIEC CRA Ratings | ffiec.gov/cra/craflatfiles.htm | Pipe-delimited flat file; FFIEC blocks automated download |
| CFPB Enforcement | consumerfinance.gov/enforcement/actions/ | HTML scrape, up to 20 pages |
| OCC Enforcement | occ.gov/topics/laws-and-regulations/enforcement-actions/ | HTML scrape |
| Federal Reserve Enforcement | federalreserve.gov/supervisionreg/enforcementactions.htm | HTML scrape |
| FDIC Enforcement | fdic.gov/bank/individual/enforcement/ | HTML scrape |
| FDIC Financials | banks.data.fdic.gov/api/financials | REST API, quarterly Call Report metrics |
| HMDA | ffiec.cfpb.gov/v2/data-browser-api | REST API, institution-level mortgage summaries |

## Installation

```bash
pip install -r requirements.txt
```

## Running the Pipeline

### Full Pipeline (recommended for first run)

```bash
python -m src.cli pipeline --full --enriched
```

This runs all 12 stages in sequence: FDIC institutions, CFPB complaints, CFPB enforcement, CRA ratings, entity resolution, quality scoring, FDIC financials, multi-agency enforcement (OCC/Fed/FDIC), HMDA lending, risk profiles, final quality scoring, and CSV/JSON/Excel exports.

### Step-by-Step

```bash
# Scrape all sources including enrichment
python -m src.cli scrape --source all-enriched

# Link complaint company names to FDIC institution records
python -m src.cli normalize

# Recompute quality scores
python -m src.cli validate

# Compute composite institution risk profiles
python -m src.cli risk-profiles

# Export to CSV, JSON, Excel, and Markdown
python -m src.cli export --format all
```

### Individual Source Scraping

```bash
python -m src.cli scrape --source fdic               # FDIC institutions
python -m src.cli scrape --source cfpb               # CFPB complaints (~600MB)
python -m src.cli scrape --source enforcement        # CFPB enforcement actions
python -m src.cli scrape --source cra                # CRA ratings
python -m src.cli scrape --source financials         # FDIC quarterly financials
python -m src.cli scrape --source occ                # OCC enforcement actions
python -m src.cli scrape --source fed                # Federal Reserve enforcement
python -m src.cli scrape --source fdic-enforcement   # FDIC enforcement orders
python -m src.cli scrape --source hmda               # HMDA lending summaries
```

### Dashboard

```bash
python -m src.cli dashboard
# or equivalently:
streamlit run src/dashboard/app.py
```

### Statistics

```bash
python -m src.cli stats
```

## Dashboard Sections

The dashboard has 11 interactive sections:

1. **National Overview** — KPI cards (complaint count, institution count, enforcement actions, cross-links), complaint volume over time, top companies by complaint volume
2. **Institution Explorer** — Search and compare individual institutions; linked complaint counts, CRA rating, enforcement history, quality score, and drilldown detail view
3. **Complaint Analysis** — Product and issue breakdowns, company response analysis, submission channel distribution, consumer dispute rates
4. **Enforcement Timeline** — CFPB enforcement actions by type, chronological chart, penalty detail table
5. **Geographic Analysis** — Choropleth complaint density map, top/bottom 15 states by volume, full state comparison table
6. **CRA vs. Complaints** — CRA rating distribution, scatter plot of CRA rating vs. complaint volume per institution, outlier analysis
7. **Trends & Patterns** — Year-over-year complaint trends by product, monthly and weekly patterns, response timeliness trends, fastest-growing issues, top company complaint timelines
8. **Financial Health** — Institution assets, Tier 1 capital ratio, leverage ratio, ROA, ROE, noncurrent loan rates, efficiency ratios, quarterly trend charts per institution (from FDIC Call Reports)
9. **Multi-Agency Enforcement** — Unified enforcement timeline across CFPB, OCC, Federal Reserve, and FDIC; penalty totals by agency
10. **Institution Risk Profiles** — Composite risk scores and risk tiers (LOW/MEDIUM/HIGH/CRITICAL) for each institution, peer comparison scatter plot, asset-tier breakdown
11. **Fair Lending Analysis** — HMDA mortgage origination counts, denial rates, average loan amounts, multi-year lending trends

## Exports

All exports are written to `data/exports/`:

| File | Description |
|------|-------------|
| institutions.csv | All institutions with aggregated complaint counts, CRA ratings, enforcement history, and quality scores |
| complaints.csv | All CFPB complaint records |
| enforcement_actions.csv | CFPB enforcement actions |
| regulatory_enforcement.csv | Unified multi-agency enforcement table |
| institution_risk_profiles.csv | Composite risk profiles with risk tier classifications |
| cfpb_data.json | Full dataset in JSON format |
| cfpb_data.xlsx | Styled Excel workbook |
| summary.md | Markdown summary statistics |

## Architecture

- **Python 3.12+**, SQLite with WAL mode, Click CLI, Streamlit + Plotly dark theme
- Zero LLM dependency — all extraction is rule-based and deterministic
- Quality scoring on every institution record (weighted formula, 0.0-1.0, passing threshold 0.40)
- Entity resolution via three-stage pipeline: exact match (confidence 1.0), normalized match after suffix stripping (0.95), fuzzy match via thefuzz token_sort_ratio (default threshold 85)
- Risk profiling combines six weighted dimensions: complaint volume normalized by assets (25%), complaint resolution quality (10%), enforcement severity (20%), financial health from Call Reports (15%), lending fairness from HMDA (15%), CRA rating (15%)

## Tests

```bash
python -m pytest tests/ -v   # 164 tests
```

## Deployment

Railway-ready. Set the `CFPB_DB_PATH` environment variable to point at the database file. The dashboard also checks for `data/cfpb_tracker_deploy.db` as a deploy-specific path before falling back to `data/cfpb_tracker.db`.

---

Built by **Nathan Goldberg** · nathanmauricegoldberg@gmail.com · [LinkedIn](https://www.linkedin.com/in/nathanmauricegoldberg/)
