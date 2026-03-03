# HUD Affordable Housing Compliance Tracker
## Research Brief — 2026-03-03

### Concept
Cross-linked database of affordable housing properties combining LIHTC project data (54,102 projects, 3.7M units), HUD REAC physical inspection scores, Section 8 contract data, and ownership records. The value proposition: a single view of property quality, compliance history, funding sources, and ownership for every federally-subsidized affordable housing property in America. Answers the question: "Which affordable housing properties are in the worst condition, who owns them, and are they complying with their obligations?"

### Data Gap Analysis
HUD acknowledges using "machine and manual matching techniques" to link LIHTC data to other federal housing data, but this cross-linked dataset is NOT publicly released. Each dataset is downloadable separately but nobody provides a unified, cross-linked product. **National Housing Preservation Database (NHPD)** by NLIHC is the closest competitor — it maps federally-assisted properties but does NOT include REAC inspection scores, does NOT have NSPIRE compliance data, and has limited ownership data. **Novogradac LIHTC Mapping Tool** visualizes LIHTC properties but doesn't cross-link with inspection scores. **PolicyMap** includes REAC scores as a layer but doesn't cross-link with LIHTC project details or ownership.

### Data Sources (All Public)
1. **HUD LIHTC Database** — huduser.gov — CSV/Access download. 54,102 projects, 3.7M units, 1987-2023. Includes project address, units, credit type, placed-in-service year, financing sources, Section 8 contract number.
2. **HUD REAC Physical Inspection Scores** — huduser.gov/portal/datasets/pis.html — Downloadable CSV. ~20,000 inspections/year. Properties scored 0-100 on site, building exterior, building systems, common areas, units.
3. **HUD Multifamily Section 8 Contracts** — data.hud.gov — Active and expired Section 8 contracts with property details.
4. **HUD Active Properties** — data.hud.gov — Multifamily assisted housing properties.
5. **Census ACS Demographics** — For neighborhood context (poverty rate, demographics, housing costs).

### Cross-Linking Value (HIGH)
- **LIHTC project -> REAC inspection score**: Link property-level LIHTC data with inspection outcomes
- **LIHTC -> Section 8 contract**: HUD form already collects Section 8 contract numbers on LIHTC properties
- **Property -> Ownership**: Track owners/developers across multiple properties
- **Geographic -> Demographics**: Overlay property data on Census demographic and poverty data
- **Expiring affordability**: Identify LIHTC properties nearing end of 15/30-year compliance periods
- **Failing properties**: Flag properties with low inspection scores and expiring subsidies

### Scale
- LIHTC: 54,102 projects / 3.7M units
- REAC inspections: ~300,000+ historical inspections
- Section 8 contracts: ~28,000 active
- HUD multifamily properties: ~35,000+
- Combined: 400,000+ records across 4+ sources

### Named Buyers
1. **Affordable housing developers** (Enterprise Community Partners, LISC, National Equity Fund) — Due diligence and portfolio monitoring
2. **State Housing Finance Agencies** (all 50 states) — Compliance monitoring tools
3. **Real estate investors** (LIHTC syndicators: Raymond James, National Partnership Investments, Boston Capital) — Property acquisition screening
4. **Policy research organizations** (NLIHC, Urban Institute, Brookings) — Housing policy analysis
5. **Journalism organizations** (ProPublica, The Marshall Project, local investigative teams) — "Slumlord" investigative reporting on worst-condition subsidized housing

### Academic/Research Collaborators
- Dr. Ingrid Gould Ellen (NYU Furman Center for Real Estate)
- Dr. Matthew Desmond (Princeton, author of Evicted)
- Joint Center for Housing Studies at Harvard

### Score: 24/30
| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Data Gap Reality | 4 | HUD does internal cross-linking but doesn't release it. NHPD exists but lacks inspection scores and ownership. |
| Buyer Clarity | 4 | HFAs, syndicators, developers, policy researchers, journalists all need this. |
| Technical Feasibility | 4 | All CSV downloads from HUD. No scraping needed. Address matching is the main technical challenge. |
| Cross-Linking Value | 5 | Property address/contract number enable direct matching. HUD data already designed to interoperate. |
| Scale Demonstration | 5 | 400K+ records from 4+ sources. 54K projects covering 3.7M housing units. |
| Credibility Signal | 2 | Housing policy is important but less commercially exciting than automotive or finance. |
