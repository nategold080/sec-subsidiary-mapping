# MSHA Mining Safety & Enforcement Tracker
## One-Page Overview

### What Is It?
A cross-linked database of 7.7 million U.S. mine safety enforcement records from MSHA, producing operator safety profiles with composite risk scoring.

### Key Numbers

| Metric | Value |
|--------|-------|
| Total Records | 7,690,260+ |
| Mines Tracked | 91,587 (6,590 active) |
| Operator Profiles | 49,673 with safety scores |
| High-Risk Operators | 1,024 (HIGH or CRITICAL) |
| Fatalities Tracked | 1,194 |
| Proposed Penalties | $1,797,308,851 |
| Geographic Coverage | 55 states/territories |
| Temporal Range | 2000–2026 |

### Sample Findings

1. **Repeat Offender Patterns** — Operators with prior fatalities show 3x higher violation rates in subsequent years
2. **Penalty Collection Gap** — Paid penalties represent ~70% of proposed amounts, with billions in potential enforcement value uncaptured
3. **Experience Paradox** — Workers with <1 year experience account for disproportionate fatal accidents
4. **S&S Concentration** — A small number of operators account for a large share of Significant & Substantial violations

### What Makes This Unique?
- **Cross-linked entities** across 6 MSHA datasets via MINE_ID and OPERATOR_ID
- **Composite safety scoring** with 5-component weighted formula
- **Risk tier classification** identifying the most dangerous operators
- **Normalized operator names** for entity resolution across datasets
- **Quality-scored records** with completeness tracking

### Methodology
Rule-based extraction and normalization (zero LLM dependency). Safety scores weight: fatalities (25%), injuries (25%), violation rate per mine (20%), S&S violations (15%), penalty severity (15%).

### Deliverables
- Structured SQLite database with 7 indexed tables
- CSV/JSON/Excel exports for all datasets
- Interactive Streamlit dashboard (8 sections)
- High-risk operator reports
- Methodology documentation

### Data Sources
All public data from MSHA Open Government Data Portal (U.S. Department of Labor). No authentication, API keys, or paid data sources required.

---

Built by **Nathan Goldberg** · nathanmauricegoldberg@gmail.com · [LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)
