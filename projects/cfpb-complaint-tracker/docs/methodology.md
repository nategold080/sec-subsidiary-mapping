# Methodology — CFPB Consumer Complaint Cross-Linked Analysis

## What This Dataset Is

A cross-linked structured database connecting CFPB consumer complaints to FDIC-insured financial institutions and their full regulatory context: Community Reinvestment Act ratings, enforcement actions from four federal agencies, quarterly financial performance from Call Reports, and mortgage lending patterns from HMDA disclosures.

The core insight is that the CFPB complaint database names companies in free text (e.g., "Wells Fargo Bank, N.A.") while all other regulatory datasets key on FDIC certificate numbers. No existing public tool resolves these company names to certificate numbers at scale. This project does that resolution deterministically, enabling analysis that spans the CFPB, OCC, Federal Reserve, FDIC, and FFIEC datasets simultaneously.

## Data Collection

### CFPB Consumer Complaints
**Source:** Consumer Financial Protection Bureau public data portal
**URL:** https://files.consumerfinance.gov/ccdb/complaints.csv.zip
**Method:** HTTP streaming download of a ZIP archive (~600MB compressed, ~2GB extracted). The CSV is parsed in a streaming fashion to avoid loading the full file into memory. Records are inserted into SQLite in batches of 1,000.
**Fields collected:** complaint ID, date received, product, sub-product, issue, sub-issue, company name, state, ZIP code, consumer narrative (when consent provided), company public response, company response to consumer, timely response flag, consumer disputed flag, submission channel, date sent to company, tags, consumer consent status.
**Coverage:** All complaints submitted to the CFPB since 2011 that are publicly available. Typically 600,000+ records.

### FDIC Financial Institutions
**Source:** FDIC BankFind Suite REST API
**URL:** https://api.fdic.gov/banks/institutions
**Method:** Paginated REST API calls (10,000 records per page, 0.5-second delay between pages). Retrieves all FDIC-insured institutions including both active and inactive.
**Fields collected:** institution name, FDIC certificate number (primary key), RSSD ID (Federal Reserve cross-reference), city, state, ZIP code, total assets (in thousands), institution class, primary federal regulator, active status, established date, website URL.

### FFIEC CRA Ratings
**Source:** Federal Financial Institutions Examination Council
**URL:** https://www.ffiec.gov/cra/craflatfiles.htm
**Method:** The FFIEC blocks automated downloads. CRA data must be manually downloaded and placed in `data/raw/`. The parser auto-detects pipe-delimited or comma-delimited format.
**Fields collected:** FDIC certificate number, institution name, exam date, CRA rating (Outstanding/Satisfactory/Needs to Improve/Substantial Noncompliance), assessment area, regulating agency.

### CFPB Enforcement Actions
**Source:** Consumer Financial Protection Bureau enforcement actions listing
**URL:** https://www.consumerfinance.gov/enforcement/actions/
**Method:** HTML scraping of up to 20 paginated listing pages. Each page is parsed with regex to extract respondent name, action date, action type, description text, URL, and penalty amount. Penalty amounts are extracted only when found in penalty-specific contexts (pay, fine, penalty, relief, restitution) to avoid capturing non-penalty dollar figures.
**Fields collected:** agency (CFPB), respondent name, action date, action type (Consent Order/Complaint/Order/Lawsuit/Settlement), penalty amount, description, source URL.

### OCC Enforcement Actions
**Source:** Office of the Comptroller of the Currency
**URL:** https://www.occ.gov/topics/laws-and-regulations/enforcement-actions/
**Method:** HTML scraping of the OCC enforcement actions list. Stable action IDs are generated via MD5 hash of (agency, name, date, action type) to support idempotent inserts into the unified `regulatory_enforcement` table.

### Federal Reserve Enforcement Actions
**Source:** Board of Governors of the Federal Reserve System
**URL:** https://www.federalreserve.gov/supervisionreg/enforcementactions.htm
**Method:** HTML scraping with 1.5-second delay between requests and up to 3 retries on failure.

### FDIC Enforcement Orders
**Source:** FDIC enforcement actions database
**URL:** https://www.fdic.gov/bank/individual/enforcement/
**Method:** HTML scraping. Records are inserted into the unified `regulatory_enforcement` table.

### FDIC Quarterly Financial Data
**Source:** FDIC Statistics on Depository Institutions (SDI) / Call Reports
**URL:** https://banks.data.fdic.gov/api/financials
**Method:** Paginated REST API (10,000 records per page, 0.3-second delay). Retrieves the most recent quarterly snapshot per institution.
**Fields collected:** total assets, total deposits, net loans, net income, net interest margin, risk-based capital ratio, Tier 1 risk-based capital ratio, leverage ratio, ROA, ROE, noncurrent loans to loans ratio, efficiency ratio, number of offices, number of employees.

### HMDA Mortgage Lending Data
**Source:** FFIEC Home Mortgage Disclosure Act data publication
**URL:** https://ffiec.cfpb.gov/v2/data-browser-api
**Method:** REST API calls for institution-level aggregate summaries. Returns origination counts, denial counts, average loan amounts, and average interest rates by institution and year.
**Fields collected:** LEI (Legal Entity Identifier, cross-referenced to FDIC cert number), institution name, report year, total applications, total originations, total denials, denial rate, average loan amount, average interest rate, total loan volume, states active in.

## Normalization and Cross-Linking

The central technical contribution of this project is resolving CFPB complaint company names to FDIC certificate numbers. This is done through a three-stage pipeline in `src/normalization/institutions.py`:

**Stage 1 — Exact match (confidence 1.0)**
The complaint company name is uppercased and compared directly against all institution names in `financial_institutions`. This catches cases where the CFPB and FDIC use identical names.

**Stage 2 — Normalized match (confidence 0.95)**
Legal suffixes are stripped from both the complaint company name and the institution name before comparison. Suffixes include: "National Association", "N.A.", "FSB", "SSB", "Inc.", "LLC", "Corp.", "Corporation", "Company", "Bank", "Trust", "& Trust", "a division of", and others (ordered longest-first to prevent partial matches). Punctuation is removed and whitespace is collapsed. Example: "Wells Fargo Bank, N.A." and "Wells Fargo" both normalize to "WELLS FARGO".

**Stage 3 — Fuzzy match (confidence = score/100)**
For names that do not match exactly or normalized, `thefuzz.fuzz.token_sort_ratio` is applied against all normalized institution names. Token sort ratio handles word order differences. The default acceptance threshold is 85/100. This catches variations like "JPMorgan Chase" vs. "JPMORGAN CHASE BANK".

Cross-links are stored in the `institution_complaints` table with `complaint_id`, `cert_number`, `match_confidence`, and `match_method`. Each complaint is linked to at most one institution. If no match is found above the threshold, the complaint remains unlinked.

Multi-agency enforcement actions (OCC, Federal Reserve, FDIC, CFPB) are consolidated into the unified `regulatory_enforcement` table. CFPB actions from the legacy `enforcement_actions` table are migrated into `regulatory_enforcement` with stable prefixed IDs.

## Quality Scoring

Each institution in `financial_institutions` receives a quality score (0.0-1.0) based on data completeness across all linked tables:

| Component | Weight | Condition |
|-----------|--------|-----------|
| Institution name present | 0.10 | Non-empty institution_name |
| Location present | 0.10 | Both city and state populated |
| Financial data present | 0.10 | Record exists in institution_financials |
| Complaints linked | 0.20 | At least one row in institution_complaints |
| CRA rating present | 0.15 | At least one row in cra_ratings |
| Enforcement history | 0.15 | Record in enforcement_actions or regulatory_enforcement |
| Regulator identified | 0.10 | Non-empty regulator field |
| FDIC cert number | 0.10 | cert_number is not null |

The minimum acceptable threshold is 0.40. Scores are recomputed via a single bulk SQL UPDATE statement across all institutions.

## Risk Profiling

Each institution receives a composite risk score (0.0-1.0, where higher = lower risk) combining six dimensions. The overall score is a weighted average:

| Dimension | Weight | Scoring Logic |
|-----------|--------|---------------|
| Complaint volume (normalized by assets) | 25% | Complaints per $1B total assets. Scores from 1.0 (none) through 0.9 (<50/B), 0.7 (<200/B), 0.5 (<500/B), 0.3 (<1000/B), to 0.1 (>=1000/B). Falls back to absolute complaint count if no asset data. |
| Complaint resolution | 10% | 70% weight on fraction of complaints with timely response + 30% weight on (1 - dispute rate). Default 0.5 if no data. |
| Enforcement severity | 20% | Combines penalty severity (60% weight: 0.0 if >$1B, 0.1 if >$100M, 0.3 if >$10M, 0.5 if >$1M, 0.7 otherwise) and action count (40% weight: 0.1 if >=10 actions, 0.3 if >=5, 0.5 if >=3, 0.7 if >=1, 1.0 if none). |
| Financial health | 15% | Average of three sub-scores from Call Report data: Tier 1 capital ratio (well-capitalized >= 8%), ROA (healthy >= 1%), noncurrent loan rate (lower is better). Default 0.5 if no financial data. |
| Lending fairness | 15% | HMDA denial rate: 1.0 if <=5%, 0.8 if <=10%, 0.6 if <=20%, 0.4 if <=30%, 0.2 if <=50%, 0.1 if >50%. Default 0.5 if no HMDA data. |
| CRA rating | 15% | Outstanding=1.0, Satisfactory=0.7, Needs to Improve=0.3, Substantial Noncompliance=0.0. Default 0.5 if no rating. |

Risk tiers: LOW (score >= 0.8), MEDIUM (>= 0.5), HIGH (>= 0.3), CRITICAL (< 0.3).

## Known Limitations

**CRA ratings:** The FFIEC blocks automated downloads of CRA flat files. This means the `cra_ratings` table requires a manual download step. Without it, all institutions have no CRA rating and receive a default 0.5 CRA component score in risk profiling.

**Company name ambiguity:** Some complaint company names refer to non-bank entities (debt collectors, credit bureaus, payday lenders) that are not FDIC-insured and therefore cannot be matched. These complaints remain unlinked and are excluded from institution-level analysis.

**Fuzzy matching false positives:** At threshold 85, similar institution names in the same geography may produce incorrect cross-links. Confidence scores are stored on each cross-link to allow downstream filtering.

**HMDA coverage:** HMDA covers mortgage lending only. Complaints about credit cards, student loans, or other products are not captured in the lending fairness dimension.

**Financial data lag:** FDIC Call Report data lags by one quarter. The most recent quarterly snapshot is used for all financial metrics.

**Enforcement data completeness:** The OCC, Federal Reserve, and FDIC scrapers extract enforcement actions from public HTML listings that may not include all historical actions. CFPB enforcement is more complete as it comes from a structured listing.

**Database size:** The full enriched database is expected to exceed 10GB, which creates deployment challenges on platforms with storage limits. See PROBLEMS.md P2.

## All Scoring is Deterministic

All extraction, normalization, quality scoring, and risk scoring is deterministic and rule-based. There is zero LLM dependency in the core pipeline. This ensures reproducible results across pipeline runs.

---

Built by Nathan Goldberg · nathanmauricegoldberg@gmail.com · [LinkedIn](https://www.linkedin.com/in/nathanmauricegoldberg/)
