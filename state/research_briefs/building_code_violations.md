# Building Code Violation Tracker (Cross-City)

## Research Date: 2026-03-02

## Concept
Aggregate building code violations, inspection results, and complaint data from major city building departments into a single cross-city database. Cross-link with property ownership records, FEMA flood maps, and Census demographic data to enable analysis of code enforcement patterns across cities.

## Data Gap Assessment: 3/5
Several cities publish violations through open data portals:
- Chicago: Building Violations dataset on data.cityofchicago.org (2006-present)
- NYC: DOB Violations on NYC Open Data + HPD violations + ECB violations (multiple datasets)
- Other cities: Varying availability through Socrata/CKAN open data portals

However:
- No cross-city aggregated database exists
- ViolationWatch.nyc aggregates NYC-only data (not cross-city)
- DOBGuard serves NYC property managers (not cross-city)
- US City Open Data Census tracks which cities publish code enforcement data but doesn't aggregate it
- Each city uses different violation codes, severity classifications, and data schemas

Score: 3/5 because city-level data portals are already structured (just not aggregated/standardized cross-city).

## Source Accessibility
1. **Chicago** - Socrata API confirmed. Building Violations dataset has 800,000+ records.
2. **NYC** - Open Data portal. DOB Violations, HPD Violations, ECB Violations all available via API.
3. **Los Angeles** - Limited open data for building violations. LADBS provides online lookup but not bulk download.
4. **Philadelphia** - L&I violations available on OpenDataPhilly.
5. **Houston** - Limited open data availability.
6. **Other cities** - Highly variable. Many publish through Socrata but data schema differs enormously.

## Cross-Linking Value: 3/5
- Standardize violation types across cities (difficult — each city has its own code system)
- Cross-reference with property ownership (county assessor data)
- Overlay with Census demographics (gentrification/disinvestment analysis)
- FEMA flood map overlay (natural disaster vulnerability + code violations)
- Track landlord/owner entities across properties and cities

The cross-linking is secondary to the aggregation challenge. The primary value is standardization, not entity resolution.

## Scale: 4/5
- Chicago alone: 800,000+ violation records
- NYC: millions of records across DOB + HPD + ECB
- 10+ cities would easily yield 2M+ records
- BUT: the data is already structured at the city level — the Data Factory pattern works best with unstructured data

## Specific Buyers

### Potential Clients
1. **Rentlogic** - NYC building rating platform. Would benefit from cross-city data.
2. **Real estate investment firms** - Analyzing building condition for acquisition decisions.
3. **Insurance underwriters** - Building condition affects policy pricing.
4. **PropTech companies** - Building management and compliance platforms.

### Research Collaborators
1. **Urban Institute** researchers studying housing quality
2. **NYU Furman Center** for Real Estate and Urban Policy

### Media
1. **Injustice Watch** (Chicago) - Already published building violation analysis tools
2. **ProPublica** - Housing investigation team

## Technical Feasibility: 4/5
Most major cities use Socrata or similar open data platforms with APIs. Data is already structured (tabular). The challenge is schema harmonization across cities, not data extraction. However:
- Some cities (LA, Houston) have limited open data
- Schema standardization across 10+ different code systems is nontrivial
- Ongoing monitoring of city portal changes needed

## Credibility Signal: 3/5
Housing and building safety are important topics, especially post-COVID and with aging infrastructure. But this is more of a "useful utility" than a groundbreaking data product. Limited academic novelty. Media interest would be city-specific, not national.

## Score Summary
| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 3 | City data exists; cross-city aggregation doesn't |
| Buyer Clarity | 3 | PropTech/RE firms interested but no standout buyer |
| Technical Feasibility | 4 | Socrata APIs available for major cities |
| Cross-Linking Value | 3 | Standardization > entity resolution; secondary value |
| Scale | 4 | Millions of records across cities |
| Credibility Signal | 3 | Useful but not groundbreaking |
| **TOTAL** | **20** | **BORDERLINE — REJECT** |

## Rejection Reasoning
While technically feasible, this idea falls short on the key dimensions that make Data Factory projects valuable:
1. The data is already structured at the city level — we're doing aggregation/standardization, not structuring unstructured data
2. Cross-linking value (3/5) is weaker than other candidates — standardization across code systems is useful but not the "eureka" cross-linking that characterizes the best projects
3. Buyer clarity (3/5) is weaker — no standout organization that would clearly pay
4. Credibility signal (3/5) is limited — unlikely to generate academic collaboration or major media
5. At 20/30, this is exactly at the threshold but other candidates score higher

**Recommendation: REJECT in favor of higher-scoring alternatives.**
