# Employer Labor Compliance Tracker
### Cross-Agency Employer Violation Database

**Author:** Nathan Goldberg | nathanmauricegoldberg@gmail.com

---

## The Problem

Federal labor enforcement data is siloed across three agencies: the National Labor Relations Board (NLRB), OSHA, and the DOL Wage & Hour Division. An employer with active NLRB unfair labor practice charges, OSHA safety violations, and wage theft findings appears as three separate stories in three separate databases. Nobody has connected them into a single employer compliance profile.

## The Solution

A structured database that cross-links employer labor violations across federal agencies:

| Dataset | Records | Coverage |
|---------|---------|----------|
| NLRB Cases | 233,011 | 2015–present |
| Employer Profiles | 91,656 | All 50 states + DC |
| OSHA Inspections | *In progress* | — |
| WHD Compliance Actions | *In progress* | — |

## Key Findings

- **USPS** leads with 24,055 NLRB cases — more than the next 10 employers combined
- **UPS** (2,600+), **Starbucks** (2,200+), **AT&T** (958), **Amazon** (395) round out the top 5
- Multi-agency profiling reveals which employers face enforcement across labor relations, safety, and wages simultaneously
- Composite compliance risk scores quantify employer risk on a 0.0–1.0 scale

## What Makes This Different

- **Cross-agency linkage** — Employer name normalization and fuzzy matching connects records across NLRB/OSHA/WHD
- **Employer-centric view** — Unified compliance profiles, not agency-siloed searches
- **Rule-based extraction** — Zero LLM dependency, fully reproducible pipeline
- **Quality scoring** — Every record scored 0.0–1.0 with component-level breakdown
- **107 automated tests** — Production-grade data quality assurance

## Use Cases

- **Law firms:** Assess employer compliance risk for litigation support or M&A due diligence
- **ESG ratings:** Quantitative labor governance signals for institutional investors
- **Journalists:** Investigate multi-agency repeat offenders with structured, searchable data
- **Researchers:** Study cross-agency enforcement patterns and regulatory effectiveness
- **HR/compliance platforms:** Integrate violation data into employer compliance dashboards

## Technical Details

Python 3.12 | SQLite | 8-section Streamlit dashboard | CSV/JSON/Excel/Markdown exports | Methodology documentation included

## Access

Full dataset, interactive dashboard, and methodology docs available upon request.

Nathan Goldberg — nathanmauricegoldberg@gmail.com
