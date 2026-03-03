# NHTSA Vehicle Safety Defect Tracker

Cross-linked database of NHTSA vehicle owner complaints, defect investigations, and recall campaigns. Traces the full defect lifecycle: complaint clusters → investigation triggers → recall outcomes.

## Key Statistics

| Metric | Value |
|--------|-------|
| Complaints | 500,000 |
| Investigations | 5,326 |
| Recall Campaigns | 2,955 |
| Cross-Agency Links | 175,443 |
| Unique Vehicles | 6,576 make/model pairs |
| Crashes Reported | 26,615 |
| Deaths Reported | 2,064 |
| Fires Reported | 7,337 |
| Coverage | 2015-present, 33 major makes |

## Data Sources

- **NHTSA Complaints Flat File** — Daily-updated bulk file of all vehicle owner complaints
- **NHTSA Investigations Flat File** — Preliminary Evaluations, Engineering Analyses, Defect Petitions
- **NHTSA Recalls API** — All recall campaigns with affected units, remedy details, Park It advisories
- **NHTSA Products API** — Vehicle make/model index

## Cross-Linking Value

This project connects three datasets that NHTSA provides separately:

1. **Complaints → Recalls**: Which complaint patterns led to recalls? Match by make/model/year + component prefix overlap.
2. **Complaints → Investigations**: Which complaints triggered investigations? Match by make/model with year-in-range check.
3. **Recalls → Investigations**: Which investigations resulted in recalls? Match by make/model/year.

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline (download, parse, cross-link)
python -m src.cli pipeline --min-year 2015

# View statistics
python -m src.cli stats

# Export data (CSV, JSON, Excel, Markdown)
python -m src.cli export --format all

# Launch dashboard
python -m src.cli dashboard
```

## Dashboard

8-section interactive Streamlit dashboard:

1. **Overview** — KPI cards, top makes, top components
2. **Complaint Explorer** — Search/filter by make/model/crash/fire
3. **Recall Tracker** — Park It alerts, affected vehicles
4. **Investigation Monitor** — Status/type breakdown
5. **Vehicle Deep Dive** — Per-vehicle complaints + recalls + investigations
6. **Safety Trends** — Monthly complaint/crash/fire volumes
7. **Component Analysis** — Death rate per 10,000 complaints
8. **Data Quality** — Per-table quality metrics, cross-link coverage

## Technical Details

- Python 3.12, SQLite (WAL mode), Click CLI, Streamlit + Plotly
- Zero LLM dependency — all extraction is rule-based
- Quality scoring (0.0-1.0) on every record
- 88 automated tests
- Rate-limited API access with caching

## Built By

Nathan Goldberg — nathanmauricegoldberg@gmail.com
