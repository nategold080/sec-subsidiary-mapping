# Employer Labor Compliance Tracker
## Research Brief — 2026-03-03

### Concept
Cross-linked database of employer labor law violations across federal agencies: DOL Wage and Hour Division (WHD) back-wage actions, NLRB unfair labor practice charges, OSHA workplace safety citations, and EEOC discrimination charges. The unique value is entity-resolving employer names across these four siloed agency databases to build a comprehensive "employer compliance score" — like a credit score for labor law compliance. This is especially timely given DOL's "Project Firewall" initiative (launched Sept 2025) that explicitly calls for inter-agency coordination on H-1B employer enforcement.

### Data Gap Analysis
**Good Jobs First Violation Tracker** is the closest competitor — it aggregates 39 agency databases and tracks violations by company name. However: (a) it focuses on large corporations ($5K+ penalties), missing small/mid-size employer violations; (b) it does not resolve entities across agencies (same employer under different name variants); (c) it provides no composite scoring or compliance analytics; (d) it does not include NLRB unfair labor practice cases. **No free product cross-links WHD + NLRB + OSHA + EEOC into a unified employer compliance view.** The DOL's own enforcedata.dol.gov covers WHD and OSHA but not NLRB or EEOC.

### Data Sources
1. **DOL WHD Compliance Action Data** — Data.gov catalog, all concluded actions since FY2005. ~23,000-30,000 cases/year. Includes employer name, EIN, back wages, civil penalties, number of affected employees. Available via DOL data portal API.
2. **NLRB Case Data** — nlrb.gov Advanced Data Search allows export of up to 100K records. labordata/nlrb-data GitHub repo provides daily-refreshed data on representation and unfair labor cases since ~2010. 20,000-30,000 charges/year.
3. **OSHA Inspection Data** — DOL bulk CSV downloads. 3M+ inspections since 1970s. Employer name, SIC code, penalty amounts, violation types.
4. **EEOC Charge Statistics** — Annual charge data by basis and state. Detailed case-level data more limited but aggregate employer-level data available through FOIA.

### Cross-Linking Value (VERY HIGH)
- **Employer entity resolution** across WHD, NLRB, OSHA using name normalization, EIN matching, address matching
- **Composite compliance scoring**: Weight violations by severity, recency, frequency across agencies
- **Industry/geography patterns**: NAICS codes + state/county to show which industries and regions have worst compliance
- **Repeat offender identification**: Employers with violations across multiple agencies
- **Project Firewall connection**: H-1B sponsors cross-linked with WHD violations (DOL disclosure files have employer names)

### Scale
- WHD: ~400,000+ compliance actions (FY2005-present, ~23K-30K/year)
- NLRB: ~200,000+ ULP charges (2010-present, ~20K-30K/year)
- OSHA: 3M+ inspections (historical)
- Combined: 3.5M+ records from 3+ federal agencies
- H-1B LCA cross-link: 4.8M+ LCA records (optional enhancement)

### Named Buyers
1. **Immigration law firms** (Fragomen, Berry Appleman, BAL) — Need employer compliance data for H-1B risk assessment under Project Firewall
2. **Corporate compliance platforms** (Navex Global, SAI360, LRQA) — Integrate into compliance monitoring dashboards
3. **Institutional investors** (CalSTRS, NYC Comptroller, AFL-CIO pension) — ESG labor screening for portfolio companies
4. **Union organizing campaigns** (SEIU, Teamsters, UNITE HERE) — Research employer violation history before campaigns
5. **Employment law firms** (Littler Mendelson, Fisher Phillips, Seyfarth Shaw) — Client due diligence and litigation support

### Academic/Research Collaborators
- Dr. David Weil (Brandeis, former WHD Administrator)
- Dr. Janice Fine (Rutgers, workplace policy)
- Economic Policy Institute (EPI) labor standards program
- Brookings Institution (published on NLRB tracking in 2025)

### Score: 24/30
| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Data Gap Reality | 4 | Good Jobs First covers some ground but no entity-resolved cross-agency employer compliance product exists. |
| Buyer Clarity | 5 | Immigration firms (Project Firewall urgency), compliance platforms, unions, ESG investors, law firms. |
| Technical Feasibility | 3 | WHD/OSHA bulk downloads work. NLRB Advanced Search + GitHub repo available. EEOC case-level data may need FOIA. |
| Cross-Linking Value | 5 | 4 agency databases linked by employer name/EIN. Composite scoring creates unique analytical layer. |
| Scale Demonstration | 5 | 3.5M+ records from 3+ sources. Easily exceeds 1,000+ threshold. |
| Credibility Signal | 2 | Strong but labor compliance is niche; less mainstream visibility than environmental or consumer topics. |
