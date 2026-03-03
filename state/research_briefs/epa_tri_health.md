# EPA Toxic Release Inventory Cross-Linked with Health Outcomes

## Research Date: 2026-03-02

## Concept
Cross-link EPA's Toxic Release Inventory (TRI) data — facility-level toxic chemical releases from 80,000+ facilities — with County Health Rankings, Census demographic data, and EPA environmental justice screening (EJScreen) data. The unique product: a facility-level database showing not just what chemicals are released, but the health and demographic context of the surrounding communities. Enable analysis like "Which facilities release the most carcinogens in communities with the worst health outcomes and highest poverty rates?"

## Data Gap Assessment: 4/5
TRI data itself is well-structured (EPA provides CSV downloads from 1987-2024, tested and confirmed). County Health Rankings provides CSV downloads (confirmed, 12.8MB). Census demographic data is available via API. EJScreen provides screening data. HOWEVER: nobody has built a FREE, OPEN, cross-linked database that connects facility-level releases to community-level health and demographic outcomes at scale. EPA's own RSEI (Risk-Screening Environmental Indicators) does some of this but focuses on modeled risk scores, not actual health outcomes. Academic researchers have done individual studies but no persistent, searchable database exists. Environmental justice organizations need this data but lack the technical capacity to build it.

## Source Accessibility (Tested)
1. **EPA TRI Basic Data Files** - CSV downloads confirmed working. URL pattern: `data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/{year}_{state}/csv`. Data from 1987-2024. Includes facility name, address, lat/lon, SIC codes, chemical names, release quantities.
2. **County Health Rankings** - CSV download confirmed (HTTP 200, 12.8MB). Health outcomes, health behaviors, clinical care, social/economic factors, physical environment by county.
3. **Census ACS Data** - Available via Census API (api.census.gov). Demographics, income, poverty, education by county/tract.
4. **EPA EJScreen** - Environmental justice screening tool with downloadable data at block group level.

## Cross-Linking Value: 5/5
This is an extremely strong cross-linking opportunity:
- TRI facilities have FIPS county codes -> direct join to County Health Rankings
- TRI facilities have lat/lon -> spatial join to Census tract/block group demographics
- TRI chemical names -> EPA toxicity data (IRIS database) for hazard classification
- Facility SIC codes -> industry classification for sector-level analysis
- Year-over-year: track whether facilities in high-poverty/poor-health areas are increasing or decreasing releases
- Community-level composite score: chemical hazard x health vulnerability x demographic vulnerability

## Scale: 5/5
- TRI facilities: 80,000+ reporting per year
- TRI release records: 4-5 million (multi-year)
- Counties: 3,143 US counties with health data
- Census tracts: 74,000+ with demographic data
- Cross-linked records: easily 100,000+ facility-county-year observations

## Specific Buyers

### Potential Clients
1. **Earthjustice** - Largest environmental law nonprofit. Needs facility-level data for litigation.
2. **Environmental Defense Fund (EDF)** - Uses data-driven approaches to environmental advocacy.
3. **WE ACT for Environmental Justice** - NYC-based EJ organization; needs data for community-level advocacy.
4. **Bloomberg Philanthropies Environment Program** - Funds data-driven environmental work.
5. **RTI International** - Research institute that does environmental health consulting.

### Research Collaborators
1. **Dr. Robert Bullard** (Texas Southern University) - "Father of environmental justice." Would be an extraordinary collaboration partner.
2. **Dr. Sacoby Wilson** (University of Maryland) - Environmental justice and health disparities researcher.
3. **Harvard T.H. Chan School of Public Health** - Environmental health research group.
4. **EPA Office of Environmental Justice** (depending on administration)

### Media/Credibility
1. **ProPublica** - Has done major TRI-related reporting (Sacrifice Zones project)
2. **The Guardian** - Regular environmental justice reporting
3. **Inside Climate News** - Environmental journalism outlet

## Technical Feasibility: 5/5
All sources are government CSV downloads or APIs. No scraping needed. No CAPTCHA, no authentication. The main technical challenge is the geographic join (facility lat/lon to Census tract), which is a well-solved problem with `geopandas` and Census TIGER shapefiles. This is by far the most technically feasible of all ideas evaluated.

## Credibility Signal: 5/5
Environmental justice is one of the most politically and academically active areas right now. This project could:
- Lead to collaboration with Dr. Robert Bullard or similar high-profile EJ researchers
- Generate media coverage (ProPublica, Guardian) given current EJ policy debates
- Be cited in EPA regulatory proceedings or Congressional testimony
- Position Nathan as a data provider in a space where advocates desperately need technical capacity
- Align with Nathan's AAAI publication background (data aggregation for social good)

## Score Summary
| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 4 | Individual datasets exist; cross-linkage does not |
| Buyer Clarity | 4 | Named EJ orgs, research collaborators, media |
| Technical Feasibility | 5 | All government CSV/API sources, no scraping |
| Cross-Linking Value | 5 | Facility-to-community health/demographics is the core value |
| Scale | 5 | 80,000+ facilities, 3,143 counties, millions of records |
| Credibility Signal | 5 | Top-tier academic/media/policy relevance |
| **TOTAL** | **28** | **STRONG ACCEPT** |

## Risks and Concerns
- Environmental justice is politically polarized; need to present data neutrally
- EPA data quality has known issues (self-reported by facilities, under-reporting documented)
- Health outcomes are county-level, not facility-level — ecological fallacy risk in analysis
- Need clear methodology documentation about correlation vs. causation
- Target audience (EJ orgs, academics) may have limited budgets — but credibility/collaboration value is extremely high
