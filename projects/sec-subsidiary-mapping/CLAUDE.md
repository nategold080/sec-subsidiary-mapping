# SEC Corporate Subsidiary & Ownership Mapping

## Project Overview
Structured database of corporate subsidiary relationships extracted from SEC EDGAR Exhibit 21 filings. Maps which public companies own which subsidiaries, in which jurisdictions, creating a corporate ownership graph from public 10-K annual report filings. Cross-linked with SEC company data (SIC codes, financials) and jurisdiction risk analysis.

## Core Value Proposition
- **sec-api.io** provides structured Exhibit 21 data but charges for meaningful usage (100 free calls, then paid)
- **Moody's/Bureau van Dijk (Orbis)** sells corporate ownership data for $50K+/year enterprise subscriptions
- **Dun & Bradstreet** charges for corporate hierarchy data
- **Nobody** provides a **free, open** structured database of SEC Exhibit 21 subsidiary data cross-linked with SEC financials, SIC industry codes, and jurisdiction analysis

## Data Sources

| Source | Type | Key Fields | URL |
|--------|------|------------|-----|
| SEC EDGAR Full-Text Search | REST API | Filing accession, CIK, company, date, exhibit links | efts.sec.gov/LATEST/search-index |
| SEC EDGAR Submissions | REST API | All filings per CIK, exhibit indices | data.sec.gov/submissions/ |
| SEC Exhibit 21 HTML/Text | HTML files | Subsidiary names, jurisdictions, ownership % | sec.gov/Archives/edgar/data/ |
| SEC Company Facts (XBRL) | REST API | Revenue, assets, employees, SIC code | data.sec.gov/api/xbrl/companyfacts/ |
| SEC Company Tickers | JSON file | CIK-to-ticker mapping, company name, exchange | sec.gov/files/company_tickers.json |

### Source-Specific Details

**SEC EDGAR Full-Text Search API:**
- Endpoint: `https://efts.sec.gov/LATEST/search-index?q=%22exhibit+21%22&dateRange=custom&startdt=YYYY-MM-DD&enddt=YYYY-MM-DD&forms=10-K`
- Returns JSON with hits containing accessionNo, fileDate, companyName, CIK
- Rate limit: 10 requests/second with identified User-Agent
- Pagination via `from` parameter

**SEC EDGAR Submissions API:**
- Endpoint: `https://data.sec.gov/submissions/CIK{cik_padded}.json`
- Returns all filings in JSON with accession numbers and exhibit lists
- CIK must be zero-padded to 10 digits

**Exhibit 21 HTML Files:**
- Access via: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{exhibit_filename}`
- Format varies significantly: HTML tables, `<pre>` text blocks, nested divs
- Column patterns: "Name of Subsidiary" / "Jurisdiction" / "% Owned"
- Some files are plain text (.txt), most are HTML (.htm)

**SEC Company Facts (XBRL):**
- Endpoint: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json`
- Contains financial facts: Revenue, Assets, NetIncome, CommonSharesOutstanding
- Free, no authentication required

## Technical Standards
- Python 3.12+, SQLite WAL mode, Click CLI, Streamlit + Plotly
- Zero LLM dependency for core extraction (regex + heuristic HTML parsing)
- Quality scoring on every record (weighted 0.0-1.0)
- Rate limit: 10 req/sec max to SEC EDGAR, polite User-Agent with contact email
- Cache all raw HTML/text files locally to avoid re-fetching
- Dark theme dashboard: primaryColor="#0984E3", backgroundColor="#0E1117"
- Footer: "Built by Nathan Goldberg" + nathanmauricegoldberg@gmail.com + LinkedIn

## Extraction Strategy

### Exhibit 21 HTML Parsing (Core Challenge)
The main technical challenge is parsing varied HTML formats. Strategy:

1. **Table-based extraction (most common):**
   - Find `<table>` elements containing subsidiary data
   - Identify header row by looking for keywords: "Name", "Subsidiary", "Entity", "Jurisdiction", "State", "Country", "Incorporation", "Organization", "% Owned", "Ownership"
   - Extract rows below header
   - Handle colspan, rowspan, nested tables

2. **Pre-formatted text extraction:**
   - Files using `<pre>` tags with column-aligned text
   - Use character position heuristics to split columns
   - Look for consistent spacing patterns

3. **Paragraph/div extraction:**
   - Some files list subsidiaries in paragraphs or divs
   - Pattern: "SubsidiaryName (Jurisdiction)" or "SubsidiaryName - Jurisdiction"
   - Regex extraction with parenthetical/dash patterns

4. **Fallback plain text:**
   - .txt files with tab or space-delimited columns
   - CSV-like parsing with flexible delimiters

### Jurisdiction Normalization
- Map state abbreviations and full names to standardized codes
- Normalize country names to ISO 3166-1 codes
- Handle common variations: "DE" vs "Delaware", "Cayman Islands" vs "Cayman Is." vs "CI"
- Flag tax haven jurisdictions (Cayman, BVI, Luxembourg, Ireland, Netherlands, Bermuda, etc.)

## Entity Resolution Strategy

### Parent Company Linking
- Primary key: SEC CIK (Central Index Key) — unique per filer
- Secondary: Ticker symbol from company_tickers.json
- Map CIK to SIC industry code for sector analysis

### Subsidiary Deduplication
- Same subsidiary may appear across multiple years of 10-K filings
- Track year-over-year changes: additions, removals, jurisdiction changes
- Fuzzy match subsidiary names across parent companies (shared subsidiaries)

## Quality Scoring Formula
Each subsidiary record scored 0.0-1.0:
- has_subsidiary_name: 0.20
- has_jurisdiction: 0.20
- has_parent_cik: 0.15
- has_filing_date: 0.10
- has_ownership_pct: 0.10
- jurisdiction_normalized: 0.10
- has_parent_financials: 0.10
- has_source_url: 0.05

Minimum threshold: 0.40 (must have name + jurisdiction + parent at minimum)

## SQLite Schema

### Tables
- **parents** — CIK, company_name, ticker, sic_code, sector, exchange, latest_filing_date
- **subsidiaries** — id, name, name_normalized, jurisdiction_raw, jurisdiction_code, jurisdiction_country, is_tax_haven
- **ownership_links** — parent_cik, subsidiary_id, filing_date, accession_number, ownership_pct, source_url
- **filings** — accession_number, cik, form_type, filing_date, exhibit_url, parse_status, record_count
- **financials** — cik, fiscal_year, revenue, total_assets, net_income, employees
- **quality_scores** — record_id, record_type, score, components_json

## Build Order
1. Config files (sources.yaml, jurisdictions.yaml, tax_havens.yaml)
2. Filing discovery scraper — Find 10-K filings with Exhibit 21 via EFTS API
3. Exhibit fetcher — Download raw HTML/text exhibit files with caching
4. HTML parser — Multi-strategy extraction (table, pre, paragraph, text)
5. Jurisdiction normalizer — State/country code standardization, tax haven flagging
6. Entity resolution — Parent CIK linking, subsidiary dedup, cross-parent matching
7. Financials enricher — Pull XBRL data for parent companies
8. Validation — Pydantic schemas, quality scoring, deduplication
9. Storage — SQLite schema, CRUD operations
10. Pipeline — Wire discovery -> fetch -> parse -> normalize -> validate -> store
11. Run pipeline — Start with S&P 500 companies, expand to full EDGAR
12. Exports — CSV, JSON, Excel, Markdown stats
13. Dashboard — 7+ interactive sections
14. Methodology doc — 1-page PDF
15. Tests — 50+ covering all stages

## Dashboard Sections (planned)
1. **Corporate Universe Overview** — KPI cards: total parent companies, subsidiaries, jurisdictions, filings parsed, tax haven entities
2. **Subsidiary Explorer** — Search/filter by parent company, jurisdiction, industry, tax haven status
3. **Company Deep Dive** — Individual parent: all subsidiaries, jurisdiction map, year-over-year changes, financials context
4. **Jurisdiction Analysis** — Where subsidiaries are incorporated: state/country breakdown, tax haven concentration by industry
5. **Tax Haven Dashboard** — Companies with highest tax haven subsidiary counts, by industry sector
6. **Ownership Network** — Visual graph of parent-subsidiary relationships (selected company)
7. **Year-over-Year Changes** — Subsidiary additions/removals tracked across annual filings
8. **Industry Comparison** — Subsidiary complexity by SIC sector, avg subsidiaries per company

## Target Audiences
- **KYC/AML compliance firms** (Moody's/BvD, D&B, Middesk, Dow Jones R&C, LexisNexis)
- **Tax policy researchers** (studying corporate structure and tax havens)
- **Corporate governance academics** (ownership complexity, subsidiary structures)
- **Fintech companies** doing KYB checks (Ramp, Brex, Mercury, Stripe)
- **Investigative journalists** (Bloomberg, WSJ, ICIJ, ProPublica)
- **Law firms** (corporate, tax, M&A — Wachtell, Skadden, Sullivan & Cromwell)
- **ESG/sustainability analysts** (subsidiary transparency scoring)
- **FinCEN/Treasury researchers** (beneficial ownership)
