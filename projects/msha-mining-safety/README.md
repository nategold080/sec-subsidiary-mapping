# MSHA Mining Safety & Enforcement Tracker

Comprehensive structured database of U.S. mine safety and enforcement data from the Mine Safety and Health Administration. Cross-links 7.7M+ records across mines, accidents, inspections, violations, and penalties to produce operator safety profiles with composite risk scoring.

## Key Numbers

| Metric | Value |
|--------|-------|
| Total Records | 7,690,260+ |
| Mines | 91,587 (6,590 active) |
| Accidents/Injuries | 271,621 |
| Fatalities | 1,194 |
| Inspections | 1,137,928 |
| Violations | 3,055,890 |
| Proposed Penalties | $1,797,308,851 |
| Operator Profiles | 49,673 |
| States/Territories | 55 |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run full pipeline (downloads ~360MB of data)
python3 -m src.cli pipeline

# Or run individual steps
python3 -m src.cli scrape-mines
python3 -m src.cli scrape-accidents
python3 -m src.cli scrape-inspections
python3 -m src.cli scrape-violations
python3 -m src.cli scrape-assessed
python3 -m src.cli scrape-penalties
python3 -m src.cli build-profiles
python3 -m src.cli export

# Launch dashboard
python3 -m src.cli dashboard

# Run tests
python3 -m pytest tests/ -v
```

## Dashboard

Interactive Streamlit dashboard with 8 sections:
- **Overview** — KPIs, trends, top operators/states
- **Accident Analysis** — Injury severity, classification, fatality trends
- **Operator Profiles** — Risk-tiered operator table with safety scores
- **Violation Explorer** — Top violated standards, S&S trends
- **Penalty Analysis** — Dollar amounts, collection rates, negligence matrix
- **Mine Search** — Full-text search with drill-down detail view
- **State Comparison** — Cross-state safety metrics
- **Data Quality** — Quality score distributions across all tables

## Data Sources

All data from the [MSHA Open Government Data Portal](https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp) (public, no authentication required).

## License

Data is public domain (U.S. government work product). Analysis and code by Nathan Goldberg.

---

Built by **Nathan Goldberg** · nathanmauricegoldberg@gmail.com · [LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)
