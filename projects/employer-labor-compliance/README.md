# Employer Labor Compliance Tracker

Cross-agency employer labor violation database linking NLRB labor relations cases, DOL Wage & Hour Division compliance actions, and OSHA workplace safety inspections into unified employer compliance profiles.

## Key Statistics

| Metric | Value |
|--------|-------|
| NLRB Cases | 233,011 |
| WHD Wage & Hour Cases | 6,998 |
| Employer Profiles | 97,760 |
| Cross-Agency Links | 190,618 |
| Multi-Agency Offenders | 529 |
| Total Back Wages | $45,526,130 |
| Employees Affected | 46,002 |
| Coverage | 2015–present, all 50 states + DC |
| Tests | 115 passing |

## Data Sources

- **NLRB Case Data** — Nightly-updated bulk database from labordata/nlrb-data (filing + allegation tables)
- **DOL WHD Compliance Actions** — 6,998 wage theft cases via DOL v4 API (FLSA/FMLA/SCA violations, back wages, penalties)
- **OSHA Inspections** — Workplace safety inspections, violations, penalties, fatalities (pending — download interrupted)

## Cross-Linking Value

This project connects employer records across three federal agencies that enforce labor law independently:

1. **NLRB → WHD**: Do employers facing union organizing also have wage theft issues?
2. **NLRB → OSHA**: Do employers with unfair labor practice charges have worse safety records?
3. **WHD → OSHA**: Do wage violators also cut corners on workplace safety?

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline
python -m src.cli pipeline

# View statistics
python -m src.cli stats

# Export data (CSV, JSON, Excel, Markdown)
python -m src.cli export --format all

# Launch dashboard
python -m src.cli dashboard
```

## Dashboard

8-section interactive Streamlit dashboard:

1. **KPI Overview** — Total cases, employers, agency breakdown
2. **Geographic Distribution** — Choropleth map, state-level analysis
3. **Multi-Agency Offenders** — Employers with violations across agencies
4. **Industry Analysis** — Case distribution by sector
5. **Temporal Trends** — Monthly/yearly filing volumes
6. **Violation Analysis** — Case types, allegation categories
7. **Employer Search** — Search by name, state, case count
8. **Data Quality** — Per-table quality metrics

## Technical Details

- Python 3.12, SQLite (WAL mode), Click CLI, Streamlit + Plotly
- Zero LLM dependency — all extraction is rule-based
- Quality scoring (0.0-1.0) on every record
- 115 automated tests
- Employer name normalization with DBA extraction and fuzzy matching

## Built By

Nathan Goldberg — nathanmauricegoldberg@gmail.com
