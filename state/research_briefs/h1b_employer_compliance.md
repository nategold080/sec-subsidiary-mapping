# H-1B Employer Compliance Tracker
## Research Brief — 2026-03-03

### Concept
Cross-linked database of H-1B sponsor employers combining DOL LCA disclosure data (4.8M+ records), USCIS Employer Data Hub (approval/denial rates), DOL WHD wage violation enforcement actions, and DOL willful violator lists. The unique value: a unified employer compliance view that answers "Is this H-1B sponsor paying fair wages, getting petitions approved, and staying out of enforcement trouble?" Extremely timely given DOL's "Project Firewall" (launched Sept 2025) — the first-ever Secretary-certified investigation authority for H-1B program abuse, with 175+ active investigations and $15M in back wages assessed.

### Data Gap Analysis
**h1bdata.info** and **h1bgrader.com** index LCA data (salaries, sponsors) but do NOT cross-link with enforcement actions, denial rates, or willful violator status. **USCIS Employer Data Hub** provides approval/denial rates but no wage data or enforcement history. **DOL enforcedata.dol.gov** has WHD cases but doesn't flag which are H-1B related. **No product combines LCA wages + USCIS outcomes + WHD violations + willful violator status into a unified employer compliance view.**

### Data Sources
1. **DOL OFLC LCA Disclosure Files** — dol.gov/agencies/eta/foreign-labor/performance — CSV/Excel, FY2012-present. ~800K+ LCAs/year. Includes employer name, EIN, job title, wage, worksite, SOC code.
2. **USCIS H-1B Employer Data Hub** — uscis.gov — CSV download, FY2009-2026Q1. Approval/denial/RFE rates by employer, state, NAICS.
3. **DOL WHD Compliance Action Data** — data.gov — All concluded WHD actions since FY2005. Employer name, back wages, penalties, employees affected.
4. **DOL H-1B Willful Violator List** — Published by WHD. Employers barred from H-1B program.
5. **DOL OFLC Debarment List** — Employers debarred from foreign labor certification programs.

### Cross-Linking Value (VERY HIGH)
- **LCA employer -> USCIS outcomes**: Match employer LCA filings with petition approval/denial rates
- **LCA employer -> WHD violations**: Flag sponsors with wage theft enforcement actions
- **Willful violator/debarment tracking**: Comprehensive debarment database
- **Wage analysis**: Compare LCA-promised wages to prevailing wages and WHD findings
- **Industry/geography patterns**: Which industries and MSAs have worst compliance
- **Project Firewall risk scoring**: Composite score based on all enforcement signals

### Scale
- LCA records: 4.8M+ (FY2013-2025)
- USCIS employer records: 100K+ unique employers
- WHD cases: ~400K+ total (filter by H-1B relevance or keep all)
- Combined: 5M+ records from 4+ sources

### Named Buyers
1. **Immigration law firms** (Fragomen, BAL, Berry Appleman, Ogletree Deakins) — Employer risk assessment under Project Firewall; $15M+ back wages already assessed
2. **HR/compliance platforms** (Deel, Envoy Global, LegalPad, Bridge US) — Integrate compliance data into employer dashboards
3. **Institutional investors** (ESG labor screening) — Flag portfolio companies with H-1B violations
4. **Journalism** (Bloomberg Law, The Information, Wired) — Tech industry H-1B abuse investigations
5. **Policy researchers** (EPI, Migration Policy Institute, Brookings) — Immigration policy analysis

### Why NOW Is the Perfect Moment
- **Project Firewall** (Sept 2025): DOL's most aggressive H-1B enforcement initiative ever
- **EEOC partnership** (Dec 2025): EEOC now coordinates with DOL on H-1B national origin discrimination
- **175+ active investigations** with $15M in back wages assessed
- **Immigration is the top political issue** of 2025-2026
- Every immigration law firm in America needs this data to advise clients

### Score: 23/30
| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Data Gap Reality | 3 | h1bdata.info and h1bgrader.com cover LCA data. The cross-link with enforcement is the gap, not the base data. |
| Buyer Clarity | 5 | Immigration law firms have urgent Project Firewall compliance needs. Extremely timely. |
| Technical Feasibility | 4 | All CSV/Excel downloads from DOL and USCIS. No scraping. Entity resolution across agencies is the challenge. |
| Cross-Linking Value | 5 | Employer name/EIN links across LCA, USCIS, WHD, violator lists. Composite scoring creates unique value. |
| Scale Demonstration | 4 | 5M+ LCA records. 400K+ WHD cases. Meets threshold easily. |
| Credibility Signal | 2 | Immigration policy is politically charged — could be controversial. |
