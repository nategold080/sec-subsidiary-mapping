# Corporate Subsidiary & Ownership Mapping from SEC Filings

## Research Date: 2026-03-02

## Concept
Extract and structure corporate subsidiary data from SEC 10-K Exhibit 21 filings on EDGAR. Build a free, open database mapping which companies own which subsidiaries, in which jurisdictions, creating a corporate ownership graph from public filings. Cross-link with SEC company data (SIC codes, filing history, financials) and potentially with OFAC sanctions lists and state corporate registries.

## Data Gap Assessment: 3/5
SEC-API.io already provides a structured Exhibit 21 database going back to 2003 with 100,000+ subsidiary lists, real-time updates, and ML-powered extraction. Their pricing starts at a free tier (100 calls) with paid plans beyond that. This is a SIGNIFICANT competitor. However: (a) sec-api.io is a paid service for any meaningful usage, (b) there is no FREE, OPEN equivalent, (c) their data is JSON but not cross-linked with other SEC datasets or external sanctions/beneficial ownership data. The raw data on EDGAR is public and free — the structuring is the value-add. Score reduced from potential 4 to 3 because of sec-api.io's existence.

## Source Accessibility (Tested)
1. **SEC EDGAR Full-Text Search API** - Tested and working. Query for "exhibit 21" filtered to 10-K forms returned 1,052 results for just the first half of 2024. API returns JSON with CIK, company name, filing date, accession number, and direct links to exhibit files.
2. **SEC EDGAR Submissions API** - Tested with Apple (CIK 320193). Returns all filings in JSON format. Can identify 10-K filings and their associated exhibits.
3. **Actual Exhibit 21 HTML files** - Tested Abbott Laboratories' Exhibit 21. HTML tables with subsidiary names and jurisdictions. Parseable with BeautifulSoup, though format varies significantly across filers.
4. **SEC Company Facts/Financials** - XBRL data available via `data.sec.gov/api/xbrl/companyfacts/`. Free JSON API.

## Cross-Linking Value: 4/5
- Link subsidiaries across parent companies (identify shared jurisdictions, common subsidiary structures)
- Cross-reference with SEC financial data (XBRL) to add revenue, assets context
- Cross-reference with OFAC sanctions lists to flag subsidiary jurisdiction risks
- Track ownership structure changes year-over-year (adding/dropping subsidiaries)
- Identify private equity portfolio company structures (PE firms' 10-K Exhibit 21s list portfolio companies)
- Connect to FinCEN beneficial ownership data when available
- Industry-level analysis (SIC codes) of subsidiary complexity

## Scale: 5/5
- ~7,000 new Exhibit 21 filings per year
- 100,000+ historical subsidiary lists (2003-present on EDGAR)
- Each list contains 10-500+ subsidiaries
- Estimated 2-5 million unique subsidiary records extractable
- 50+ jurisdiction codes per filing

## Specific Buyers

### Potential Clients
1. **Moody's / Bureau van Dijk (Orbis)** - Sells corporate ownership data for KYC/AML. Our free structured data could supplement or compete at the low end.
2. **Dun & Bradstreet** - Corporate hierarchy data is core to their business. SEC-sourced data validates/supplements.
3. **Middesk** - YC-backed startup doing business verification and corporate KYC. Would benefit from structured subsidiary data.
4. **Dow Jones Risk & Compliance** - Sells KYC and sanctions screening tools. Subsidiary-to-jurisdiction mapping is directly relevant.
5. **LexisNexis Risk Solutions** - Corporate due diligence data provider.

### Potential Employers
1. **Compliance.ai** - Regulatory intelligence startup
2. **Enigma Technologies** - Commercial data platform, previously SEC-focused
3. **Ramp/Brex/Mercury** - Fintech companies doing KYB (Know Your Business) checks

### Research Collaborators
1. **Tax policy researchers** (subsidiary structures in tax havens)
2. **Corporate governance academics** (ownership complexity studies)
3. **FinCEN/Treasury** beneficial ownership researchers

## Technical Feasibility: 3/5
This is the main challenge. Exhibit 21 HTML varies enormously across filers:
- Some use HTML tables, some use plain text in `<pre>` tags
- Column headers vary ("Name", "Subsidiary", "Entity", "Jurisdiction of Incorporation", "State/Country")
- Some list ownership percentages, some don't
- Some include intermediate holding company hierarchy, some flatten
- Need robust multi-format parser or train a set of regex patterns per filing style
- Rate limiting: SEC limits to 10 requests/second with User-Agent identification

Score: 3/5 (accessible but parsing is moderately complex)

## Credibility Signal: 4/5
Corporate transparency is a hot topic post-FinCEN beneficial ownership rule. Tax haven subsidiary structures are politically salient. Academic interest from law schools (corporate governance), business schools (organizational structure), and economics (tax policy). Journalists at Bloomberg, WSJ, and NYT frequently investigate corporate subsidiary structures.

## Score Summary
| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 3 | sec-api.io exists but is paid; no free open database |
| Buyer Clarity | 4 | Named KYC/compliance companies with clear need |
| Technical Feasibility | 3 | HTML parsing varies; moderate complexity |
| Cross-Linking Value | 4 | Subsidiary-to-jurisdiction-to-financials is valuable |
| Scale | 5 | Millions of subsidiary records on EDGAR |
| Credibility Signal | 4 | Corporate transparency is hot topic |
| **TOTAL** | **23** | **ACCEPT (conditional)** |

## Risks and Concerns
- sec-api.io is a direct competitor with years of head start and ML-powered extraction
- HTML format variation means building a robust parser requires significant effort
- Value proposition must emphasize cross-linking (not just extraction) to differentiate
- Consider starting with a focused subset: S&P 500 companies only, with year-over-year change tracking as differentiator
