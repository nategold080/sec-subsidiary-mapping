# CFPB Consumer Complaint Cross-Linked Analysis

## Research Date: 2026-03-02

## Concept
Build the first free structured database that cross-links CFPB consumer complaints (2M+ records) with FDIC institution data (4,600+ banks), FFIEC CRA ratings, and CFPB/OCC/FDIC enforcement actions. The core value: for any financial institution, instantly see complaint volume/trends, regulatory ratings, enforcement history, and financial health metrics in one unified view. No free tool does this today.

## Data Gap Assessment: 4/5
The CFPB complaint database exists as a free bulk download (CSV/JSON, API available). FDIC BankFind API provides institution data freely. CRA ratings are published by FFIEC quarterly. Enforcement actions are listed on agency websites but NOT in structured/downloadable form. The gap is NOT in any single dataset — it's that nobody has cross-linked them. The CFPB complaints identify companies by name but don't include FDIC certificate numbers, RSSD IDs, or CRA ratings. Ncontracts has an "Enforcement Action Tracker" but it's a commercial product behind a paywall. PerformLine published infographics cross-linking complaints with enforcement but not a structured database. Consumer Finance Insights tracks enforcement actions editorially. No free, open, structured cross-linked database exists.

## Source Accessibility (Tested)
1. **CFPB Complaint Database** - Bulk CSV/JSON download + REST API. Confirmed accessible. 2M+ complaints with company name, product, issue, state, date, narrative text.
2. **FDIC BankFind API** - REST API tested and working (`api.fdic.gov/banks/institutions`). Returns JSON with INSTNAME, CERT, CITY, STNAME, ASSET, etc. 4,600+ active institutions.
3. **FFIEC CRA Ratings** - Published at ffiec.gov/craratings/. FDIC CRAPES flat files available. Updated quarterly. Cloudflare-protected (403 on curl) but data files may be directly downloadable.
4. **CFPB Enforcement Actions** - Listed at consumerfinance.gov/enforcement/actions/. HTML page, scrapeable. ~300+ actions since 2012 with company names, penalty amounts, dates.
5. **County Health Rankings** (bonus cross-link) - 12.8MB CSV confirmed downloadable. Health outcomes by county to overlay with complaint geographic concentration.

## Cross-Linking Value: 5/5
This is where the unique value lives:
- Match CFPB complaint company names to FDIC institution records (fuzzy matching needed — "Bank of America" vs "Bank of America, National Association")
- Link FDIC CERT numbers to CRA ratings (FFIEC uses CERT/RSSD as keys)
- Match enforcement action company names to both CFPB complaints and FDIC records
- Enable analysis: "Which banks with 'Outstanding' CRA ratings have the highest complaint rates per asset dollar?"
- Enable analysis: "Do enforcement actions correlate with complaint spikes? How long between complaint surge and enforcement?"
- Geographic overlay: complaint hotspots vs county health/income data

## Scale: 5/5
- CFPB complaints: 2,000,000+ records
- FDIC institutions: 4,600+ active banks
- CRA ratings: 4,600+ ratings (multiple years)
- Enforcement actions: 300+ (CFPB) + OCC + FDIC actions
- Combined cross-linked records: easily 50,000+ meaningful linkages

## Specific Buyers

### Potential Clients
1. **Ncontracts** (Nashville, TN) - Already sells an enforcement action tracker. Our free cross-linked data could be a competitive threat or partnership opportunity. Contact: VP of Product.
2. **Wolters Kluwer Compliance Solutions** - Sells regulatory compliance tools to banks. Would benefit from complaint-to-enforcement linkage. Enterprise sales.
3. **Cornerstone Advisors** - Bank consulting firm that advises on compliance. Would use data for client advisory work.
4. **S&P Global Market Intelligence** - Sells bank data products. Cross-linked complaint data fills a gap in their offering.
5. **Klaros Group** - Fintech compliance advisory. Founded by former OCC leaders.

### Research Collaborators
1. **Consumer Financial Protection Bureau researchers** (before/after political changes)
2. **Brookings Institution** - Financial regulation scholars
3. **National Consumer Law Center (NCLC)** - Already publishes CFPB enforcement summaries

### Media/Credibility
1. **American Banker** reporters covering regulatory enforcement
2. **Consumer Federation of America** - Published 2021-2025 CFPB enforcement legacy report

## Technical Feasibility: 4/5
- CFPB API and bulk downloads: straightforward (5/5)
- FDIC API: working, tested (5/5)
- CRA ratings: Cloudflare protection on FFIEC site needs browser-like headers, but flat files likely accessible (3/5)
- Enforcement actions: HTML scraping needed, pages are JavaScript-rendered (3/5)
- Entity resolution (company name matching): moderate difficulty — need fuzzy matching between CFPB company names, FDIC institution names, and enforcement action respondent names (3/5)
- Overall: 4/5

## Credibility Signal: 4/5
Strong. Consumer financial protection is politically salient. Cross-linking complaints with enforcement creates a "accountability gap" narrative. Academic interest from law schools, economics departments. Media interest from consumer finance reporters. The CFPB has been politically contested (Trump vs. Chopra era), making data transparency especially valuable.

## Score Summary
| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 4 | Individual datasets exist; cross-linkage does not |
| Buyer Clarity | 4 | Named companies and roles identified |
| Technical Feasibility | 4 | APIs + HTML scraping + entity resolution |
| Cross-Linking Value | 5 | Cross-linking IS the value proposition |
| Scale | 5 | 2M+ complaints, 4,600+ institutions |
| Credibility Signal | 4 | High political/academic/media relevance |
| **TOTAL** | **26** | **ACCEPT** |
