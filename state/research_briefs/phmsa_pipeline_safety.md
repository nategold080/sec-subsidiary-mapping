# PHMSA Pipeline Safety Incident Tracker
## Research Brief — 2026-03-03

### Concept
Cross-linked database of PHMSA pipeline safety incidents, enforcement actions, and operator compliance data, linked with EPA environmental releases and community demographics. Traces the full pipeline from incident report -> enforcement action -> penalty outcome, mapped to affected communities. $6B+ in property damage over 20 years, 306 casualties.

### Data Gap Analysis
PHMSA provides extensive downloadable data (incidents, flagged files, operator reports, enforcement actions) but these are **separate CSV/ZIP files with no cross-linked product**. Pipeline Safety Trust (pstrust.org) provides a monthly incident dashboard with maps but is a simple visualization, not a structured cross-linked database. No product connects PHMSA incidents to EPA environmental releases or community impact data.

### Data Sources (All Public Downloads)
1. **PHMSA Incident Flagged Files** — ZIP downloads by pipeline type (gas transmission, gas distribution, hazardous liquid, LNG). 20+ years of data.
2. **PHMSA Source Data** — Operator annual reports, mileage, commodities.
3. **PHMSA Enforcement Data** — primis.phmsa.dot.gov/enforcement-data/ — NOPVs, corrective action orders, consent agreements.
4. **PHMSA Operator Data** — OpID system for operator identification.
5. **NRC (National Response Center)** — Hazmat spill reports cross-linkable by operator/location/date.
6. **Census ACS demographics** — Community demographics around incident locations.

### Cross-Linking Value (HIGH)
- **Operator ID -> Incidents + Enforcement**: Single operator view across all incidents and enforcement actions
- **Incident -> Environmental Release**: Match PHMSA spill data with NRC hazmat reports
- **Geographic -> Community Impact**: Overlay incidents on Census demographic data (environmental justice angle)
- **Repeat offender tracking**: Operators with multiple incidents and enforcement actions
- **Pipeline type analysis**: Compare safety records across gas transmission, distribution, hazardous liquid

### Scale
- PHMSA incidents: 20+ years of data across 4 pipeline types (~12,000+ significant incidents over 20 years)
- Enforcement actions: Thousands of NOPVs and corrective action orders
- Operators: 3,000+ pipeline operators reporting to PHMSA
- Combined: 20,000+ records from 4+ sources

### Named Buyers
1. **Environmental law firms** (Earthjustice, EarthRights International) — Pipeline litigation support
2. **Community advocacy groups** (Pipeline Safety Trust, Bold Alliance) — Community safety data
3. **Insurance/reinsurance** (Swiss Re, Munich Re, Hartford Steam Boiler) — Pipeline risk assessment
4. **Energy sector consultants** (Brattle Group, ICF, Black & Veatch) — Operator safety benchmarking
5. **ESG research firms** (Sustainalytics, MSCI ESG) — Energy infrastructure ESG screening

### Score: 22/30
| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Data Gap Reality | 4 | Data in silos; Pipeline Safety Trust has basic dashboard but no structured cross-linked product. |
| Buyer Clarity | 3 | Environmental law, insurance, ESG firms are plausible but more niche than other ideas. |
| Technical Feasibility | 4 | All data is public CSV/ZIP downloads. No API needed. May need some PDF parsing for enforcement. |
| Cross-Linking Value | 4 | Operator ID enables good cross-linking. Geographic overlay with demographics adds value. |
| Scale Demonstration | 4 | 20K+ records feasible but smaller than NHTSA or labor compliance datasets. |
| Credibility Signal | 3 | Energy infrastructure safety has growing policy relevance. Pipeline Safety Trust could be a collaborator. |
