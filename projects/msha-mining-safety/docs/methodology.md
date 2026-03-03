# MSHA Mining Safety & Enforcement Tracker — Methodology

## Data Sources

All data originates from the **Mine Safety and Health Administration (MSHA) Open Government Data Portal**, a public dataset maintained by the U.S. Department of Labor. MSHA publishes bulk downloads of mine safety data as pipe-delimited text files within ZIP archives.

### Datasets Used

| Dataset | Source File | Records | Description |
|---------|-----------|---------|-------------|
| Mines | Mines.zip | 91,587 | Master registry of all U.S. mines with location, operator, status |
| Accidents/Injuries | Accidents.zip | 271,621 | Reported mine accidents and injuries (2000–2026) |
| Inspections | Inspections.zip | 1,137,928 | MSHA mine inspection events |
| Violations | Violations.zip | 3,055,890 | Citations and orders issued during inspections |
| Assessed Violations | AssessedViolations.zip | 2,989,669 | Penalty assessments with points, gravity, negligence |
| Civil Penalties | CivilPenaltyDocketsDecisions.zip | 93,565 | Docket-level penalty decisions |

## Data Processing Pipeline

### 1. Download & Extraction
Raw ZIP files are downloaded from `arlweb.msha.gov/OpenGovernmentData/DataSets/` using curl (MSHA's server blocks standard Python HTTP libraries). ZIP files contain pipe-delimited text files with quoted values.

### 2. Parsing
A generic pipe-delimited parser handles all files. Type-specific parsers (parse_mines, parse_accidents, etc.) map MSHA column names to normalized field names and convert numeric fields.

### 3. Quality Scoring
Every record receives a quality score (0.0–1.0) based on field completeness. Each record type has its own weighted formula — for example, a mine record is scored across 9 components: mine_id, mine_name, operator_name, state, mine_type, mine_status, primary_sic, lat/long, and employee count.

### 4. Operator Name Normalization
Operator names are normalized for entity resolution:
- Uppercase conversion
- DBA/FKA/AKA clause removal
- Parenthetical content removal
- Legal suffix stripping (LLC, Inc, Corp, etc., including international variants)
- Abbreviation expansion (Intl → International, Mfg → Manufacturing, etc.)
- Punctuation normalization (preserving hyphens)

### 5. Operator Safety Profiling
Each operator receives a composite safety profile aggregating data across all tables:
- Mine counts (total and active)
- Total employees
- Accident/injury/fatality counts
- Inspection counts
- Violation counts (total and Significant & Substantial)
- Penalty amounts (proposed and paid)
- Days lost

### 6. Safety Score Computation
A composite safety score (0.0–1.0, higher = safer) is calculated from 5 weighted components:

| Component | Weight | Scoring |
|-----------|--------|---------|
| Fatalities | 25% | 0 = 1.0, 1 = 0.3, 2+ = 0.05 |
| Injuries | 25% | 0 = 1.0, 1–5 = 0.7, 6–20 = 0.4, 21–50 = 0.2, 51+ = 0.05 |
| Violations/Mine | 20% | 0 = 1.0, <10 = 0.7, <50 = 0.4, <100 = 0.2, 100+ = 0.05 |
| S&S Violations | 15% | 0 = 1.0, 1–5 = 0.7, 6–20 = 0.4, 21–50 = 0.2, 51+ = 0.05 |
| Penalty Severity | 15% | $0 = 1.0, <$10K = 0.7, <$100K = 0.4, <$1M = 0.2, $1M+ = 0.05 |

### 7. Risk Tier Assignment
- **LOW**: Score >= 0.8
- **MEDIUM**: Score >= 0.5
- **HIGH**: Score >= 0.3
- **CRITICAL**: Score < 0.3

## Cross-Linking Strategy
**MINE_ID** serves as the universal foreign key across all six datasets. **OPERATOR_ID** and **CONTROLLER_ID** link operators to their complete enforcement history. Normalized operator names enable fuzzy matching across different name spellings.

## Coverage & Limitations
- **Temporal coverage**: Accidents from 2000–2026; mines and violations are cumulative
- **Geographic coverage**: All 50 states + DC + territories (55 jurisdictions)
- **Completeness**: MSHA data is comprehensive for regulated mines. Small operations below regulatory thresholds are not included.
- **Penalty amounts**: Proposed penalties may differ from final assessed amounts. Collection rates vary.

## Key Findings
- **$1.8 billion** in proposed penalties across all assessed violations
- **1,194 fatalities** and **2,456 permanent disabilities** since 2000
- **1,024 operators** classified as HIGH or CRITICAL risk
- **49,673 unique operators** profiled with safety scores

---

Built by **Nathan Goldberg** · nathanmauricegoldberg@gmail.com · [LinkedIn](https://linkedin.com/in/nathanmauricegoldberg)
