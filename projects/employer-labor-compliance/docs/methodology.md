# Employer Labor Compliance Tracker — Methodology

**Author:** Nathan Goldberg | nathanmauricegoldberg@gmail.com
**Date:** March 2026
**Version:** 1.0

## Overview

This document describes the methodology for building a cross-agency employer labor violation database linking NLRB labor relations cases, DOL Wage & Hour Division (WHD) compliance actions, and OSHA workplace safety inspections into unified employer compliance profiles.

## Data Sources

### Primary Source: NLRB Case Data (Phase 1 — Live)
- **Source:** National Labor Relations Board via labordata/nlrb-data (nightly GitHub release)
- **Database:** SQLite with 12 tables, ~5.9 million records total
- **Tables used:** filing (case metadata), allegation (unfair labor practice charges)
- **Coverage:** 2015–present (233,011 cases after filtering)
- **Fields:** Case number, case name, case type (C/CA/CB/CC/CD/CE/CG/CP/R/RC/RD/RM/UC/UD), date filed, date closed, status, city, state, eligible voters, allegations
- **Access:** Public, no authentication required

### Secondary Source: DOL WHD (Live)
- **Source:** Department of Labor, Wage & Hour Division via v4 API (`apiprod.dol.gov/v4/get/WHD/enforcement/json`)
- **Raw records:** 363,365 (all years); 6,998 unique cases after filtering to 2015+ and deduplicating by case_id
- **Fields:** case_id, trade_nm, legal_name, address, violations by statute (FLSA, FMLA, SCA, MSPA, H1B, DBA), back wages, civil penalties, employees affected
- **Access:** Free API key from DOL data portal

### Tertiary Source: OSHA Inspections (Pending)
- **Source:** Department of Labor, Occupational Safety & Health Administration
- **Status:** OSHA Inspection dataset (ID 10313) available on DOL v4 API; download was started but interrupted
- **Expected fields:** Employer, site address, inspection type, violations (serious/willful/repeat), penalties, fatalities
- **Resolution:** Re-run OSHA download to completion when ready

## Extraction Pipeline

### Step 1: Data Download
- NLRB: Download nightly SQLite release (nlrb.db.zip, ~171 MB compressed → 951 MB) from GitHub
- WHD: Paginated download via DOL v4 API (1,500 records/page, 2s delay between requests, resumable with page-level caching)
- OSHA: Same DOL v4 API (pending download completion)
- All raw data cached locally to prevent re-downloading

### Step 2: NLRB Parsing
- Query filing table joined with allegation table via case_number
- Filter to date_filed >= 2015-01-01 for relevance
- Aggregate multiple allegations per case using GROUP_CONCAT
- Extract case type from case number prefix (C = unfair labor practice charge, R = representation petition)
- Parse dates from MM/DD/YYYY and YYYY-MM-DD formats
- Extract employer name from case_name field

### Step 3: WHD/OSHA Parsing
- WHD: Parse employer name (trade_nm, legal_name), violations by act (FLSA, FMLA, SCA, MSPA, H1B, DBA), back wages, civil penalties, employees affected, NAICS code. Dates normalized from ISO format.
- OSHA: Parse establishment name, inspection type, violation types, penalties, fatality/injury/hospitalization counts (pending data download)

### Step 4: Employer Name Normalization
Multi-step pipeline for consistent employer matching:
1. **Uppercase** all names
2. **Extract DBA** ("doing business as") as separate field
3. **Strip legal suffixes** — LLC, INC, CORP, LTD, CO, LP, LLP, PC, PA, NA, FSB (3 passes for nested suffixes)
4. **Remove possessives** ('S)
5. **Handle initials** — remove trailing periods from single-letter words
6. **Remove punctuation** except hyphens and ampersands
7. **Expand abbreviations** — INTL→INTERNATIONAL, NATL→NATIONAL, etc.
8. **Collapse whitespace** and trim
9. **Remove leading "THE"**

### Step 5: Cross-Linking
Three-stage cross-linking engine:
1. **Exact match** — Identical normalized employer names across agencies
2. **Fuzzy match by state** — RapidFuzz token_sort_ratio ≥ 85% for employers in the same state
3. **Employer profile aggregation** — Build unified profiles with case counts, violation types, and financial metrics across all matched agencies

### Step 6: Quality Scoring
Each record receives a quality score (0.0–1.0) based on weighted component presence:

**NLRB records:**
- has_case_number (0.15), has_case_name (0.20), has_case_type (0.10)
- has_date_filed (0.15), has_state (0.10), has_city (0.05)
- has_status (0.10), has_allegations (0.15)

**WHD records:**
- has_employer (0.20), has_trade_name (0.05), has_address (0.10)
- has_violation_type (0.15), has_back_wages (0.15), has_penalty (0.10)
- has_findings (0.10), has_date (0.10), has_state (0.05)

**OSHA records:**
- has_employer (0.20), has_establishment (0.05), has_address (0.10)
- has_inspection_type (0.10), has_violations (0.15), has_penalty (0.15)
- has_date (0.10), has_state (0.05), has_sic (0.05), has_fatalities (0.05)

### Step 7: Compliance Scoring
Composite employer compliance risk score using log-scaled penalty accumulation:
- **Case volume** — Number of cases across agencies (max 0.30)
- **Multi-agency presence** — Violations in 2+ agencies (0.08–0.15)
- **Financial severity** — Total penalties/back wages, log-scaled (max 0.25)
- **Fatalities** — Any workplace deaths (max 0.20)
- **Willful violations** — Intentional OSHA violations (max 0.15)

### Step 8: Storage
- SQLite database with WAL mode
- Tables: nlrb_cases, whd_cases, osha_inspections, employers, cross_links
- Indexed by employer name, state, date, case type

## Current Coverage

| Metric | Value |
|--------|-------|
| NLRB Cases | 233,011 |
| WHD Wage & Hour Cases | 6,998 |
| Employer Profiles | 97,760 |
| Cross-Agency Links | 190,618 |
| Multi-Agency Offenders | 529 |
| Total Back Wages | $45,526,130 |
| Employees Affected | 46,002 |
| Avg Quality — NLRB | 0.981 |
| Avg Quality — WHD | 0.858 |
| Date Range | 2015–present |
| States | All 50 + DC + territories |

## Limitations

1. **OSHA data pending:** OSHA inspection data download was started but interrupted. Will be added when download completes.
2. **Employer name resolution:** Employer names come from case filings and may have inconsistencies. Normalization addresses common variations but cannot resolve all ambiguities.
3. **Case outcome gaps:** NLRB case outcomes (settled, withdrawn, dismissed) are tracked by status field but specific remedy details are not structured in the bulk data.
4. **Cross-agency matching depends on name normalization:** False negatives are possible when employers use different legal entity names across agencies.
5. **Federal employer concentration:** USPS, which is the largest federal employer and the largest NLRB respondent, may skew aggregate statistics.
6. **WHD case deduplication:** WHD raw data contains 363,365 records with 187,125 unique case IDs (multiple rows per case for different compliance findings). After filtering to 2015+ and upserting by case_id, 6,998 unique cases remain.

## Quality Assurance

- All extraction is rule-based (zero LLM dependency)
- 115 automated tests covering scrapers, normalization, quality scoring, cross-linking, database operations, and exports
- Quality scoring on every record with component-level breakdown
- Cross-link confidence scores tracked per link

## Output Format

Available exports: CSV, JSON, Excel (styled), Markdown summary, SQLite database, Streamlit dashboard (8 sections).

## Reproducibility

```bash
python -m src.cli pipeline
```
