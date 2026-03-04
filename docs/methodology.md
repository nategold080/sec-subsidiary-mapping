# SEC Corporate Subsidiary & Ownership Mapping — Methodology

**Author:** Nathan Goldberg | nathanmauricegoldberg@gmail.com
**Date:** March 2026
**Version:** 1.0

## Overview

This document describes the methodology for extracting, structuring, and analyzing corporate subsidiary data from SEC EDGAR Exhibit 21 filings. The project creates a free, open database mapping which public companies own which subsidiaries, in which jurisdictions, enabling analysis of corporate structure complexity, tax haven usage, and ownership changes over time.

## Data Sources

### Primary Source: SEC EDGAR Exhibit 21 Filings
- **Source:** U.S. Securities and Exchange Commission (SEC) Electronic Data Gathering, Analysis, and Retrieval (EDGAR) system
- **Requirement:** Item 601(b)(21) of Regulation S-K requires all 10-K annual report filers to disclose "a list of all subsidiaries of the registrant, the state or other jurisdiction of incorporation or organization, and the names under which such subsidiaries do business"
- **Coverage:** All public companies filing 10-K annual reports with the SEC
- **Update frequency:** Annually per company (fiscal year end)
- **Access method:** SEC EDGAR Full-Text Search API (EFTS) + direct file download

### Secondary Source: SEC Company Facts (XBRL)
- **Source:** SEC XBRL data via `data.sec.gov/api/xbrl/companyfacts/`
- **Data:** Revenue, total assets, net income, employees, SIC industry codes
- **Purpose:** Cross-linking subsidiary data with parent company financials

### Tertiary Source: SEC Company Tickers
- **Source:** `sec.gov/files/company_tickers.json`
- **Data:** CIK-to-ticker symbol mapping, exchange listings
- **Purpose:** Identifying companies by ticker symbol

## Extraction Pipeline

### Step 1: Filing Discovery
- Query SEC EFTS API for "exhibit 21" within 10-K filings
- Extract accession number, CIK, company name, ticker, filing date from search results
- Deduplicate by accession number
- Rate limit: 10 requests/second per SEC guidelines

### Step 2: Exhibit Download
- Download raw HTML/text Exhibit 21 files from SEC Archives
- Cache all files locally to prevent re-fetching
- Track download success/failure per filing

### Step 3: HTML Parsing (Core Extraction)
The parser uses a multi-strategy approach to handle the wide variety of Exhibit 21 formats:

**Strategy A: Table Extraction (most common)**
1. Find `<table>` elements in HTML
2. Identify header row by keyword matching ("Name of Subsidiary", "Jurisdiction of Incorporation", etc.)
3. Determine column indices for name, jurisdiction, and optional ownership percentage
4. Extract data from all rows below the header
5. Handle colspan, font tags, and Wdesk-generated styling

**Strategy B: Heuristic Table Extraction**
- For tables without explicit headers
- Validate 2+ column structure where column 1 looks like a company name and column 2 looks like a jurisdiction
- Use jurisdiction validation to confirm correct column assignment

**Strategy C: Pre-formatted Text Extraction**
- For filings using `<pre>` tags with column-aligned text
- Split on 3+ consecutive spaces to identify column boundaries
- Validate jurisdiction column

**Strategy D: Text/Paragraph Extraction**
- For non-tabular formats
- Match patterns: "Company Name (Jurisdiction)" and "Company Name - Jurisdiction"

### Step 4: Jurisdiction Normalization
- Map US state names and abbreviations to 2-letter codes
- Map country names and variations to ISO 3166-1 alpha-2 codes
- Handle common patterns: "Delaware, U.S.", "Cayman Islands", "Hong Kong"
- Flag tax haven jurisdictions (25 recognized jurisdictions)

### Step 5: Quality Scoring
Each subsidiary record scored 0.0-1.0:
| Component | Weight |
|-----------|--------|
| Subsidiary name present | 0.20 |
| Jurisdiction present | 0.20 |
| Parent company CIK linked | 0.15 |
| Filing date present | 0.10 |
| Ownership percentage | 0.10 |
| Jurisdiction normalized | 0.10 |
| Parent financials linked | 0.10 |
| Source URL present | 0.05 |

Minimum quality threshold: 0.40

### Step 6: Storage
- SQLite database with WAL mode for concurrent read access
- Tables: parents, filings, subsidiaries, ownership_links, financials
- Subsidiary deduplication by normalized name + jurisdiction code
- All records linked via foreign keys

## Tax Haven Classification

Tax haven jurisdictions are flagged based on academic consensus and OECD/EU lists:
- Caribbean: Cayman Islands, British Virgin Islands, Bermuda, Bahamas, Barbados
- Europe: Luxembourg, Ireland, Netherlands, Switzerland, Jersey, Guernsey, Isle of Man, Liechtenstein, Monaco, Gibraltar
- Asia-Pacific: Singapore, Hong Kong
- Other: Mauritius, Panama, Seychelles, Belize, Vanuatu

Note: Ireland and Netherlands are included as they are commonly used for holding company structures, though they are EU member states with substantial real economic activity.

## Limitations

1. **Exhibit 21 format variation:** HTML format varies significantly across filers. Some filings use non-standard layouts that the parser cannot handle (approximately 15-20% parse failure rate).
2. **Regulation S-K materiality exemption:** Companies may omit subsidiaries that "considered in the aggregate, would not constitute a significant subsidiary." This means smaller subsidiaries are systematically underreported.
3. **Annual frequency:** Data is updated once per year per company (at fiscal year end). Intra-year subsidiary changes are not captured.
4. **No ownership hierarchy:** Most Exhibit 21 filings list subsidiaries flat (no parent-subsidiary-grandsubsidiary hierarchy). Intermediate holding company relationships are generally not extracted.
5. **SEC filers only:** Only covers companies that file with the SEC. Private companies, foreign private issuers using Form 20-F, and investment companies using Form N-CEN are not included.

## Quality Assurance

- All extraction is rule-based (zero LLM dependency)
- Automated test suite with 70+ tests covering parser, normalizer, quality scoring, and database operations
- Parse success rate tracked per filing
- Jurisdiction normalization rate tracked
- Quality scoring with component-level breakdown

## Output Format

Available exports:
- **CSV:** Flat file with all subsidiary-parent-jurisdiction mappings
- **JSON:** Structured JSON with nested records
- **Excel:** Styled workbook with header formatting
- **Markdown:** Summary statistics document
- **SQLite:** Full relational database
- **Streamlit Dashboard:** Interactive web application with 8 sections

## Reproducibility

All source code is available. The pipeline can be re-run from scratch:
```bash
python -m src.cli pipeline --start-date 2023-01-01 --end-date 2025-12-31
```
