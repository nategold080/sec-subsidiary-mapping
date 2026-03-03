# State Cannabis License & Enforcement Tracker

## Research Date: 2026-03-02

## Concept
Aggregate cannabis business licenses, violations, and enforcement actions across all legalized states into a unified database. Cross-link operators across states and track license transfers, ownership changes, and compliance outcomes.

## Data Gap Assessment: 3/5
Several players are in this space:
- **Emerald Intel** publishes cannabis license leaderboards and tracks licensing across states
- **Dan K Reports** provides a real-time cannabis legislation tracker across 50 states
- **Husch Blackwell** maintains a Nationwide Cannabis Regulatory Map
- **NCSL** has a State Cannabis Policy Enactment Database
- Individual states (CA, MA, CO) publish license data through their own portals

However, none of these provide a unified STRUCTURED DATABASE of license-level data cross-linked with enforcement actions, ownership, and compliance outcomes. Emerald Intel comes closest but is primarily a reporting/newsletter service, not a structured data product.

California's Cannabis Unified License Search provides a searchable interface (tested — React SPA with API backend). Massachusetts publishes open data with datasets available for download.

## Technical Feasibility: 3/5
- California: React SPA with API backend — would need to reverse-engineer API endpoints
- Massachusetts: Open data portal with downloadable datasets (accessible)
- Colorado: MED data accessible but format varies
- Oregon: OLCC data available but being restructured
- Each state has different license types, categories, and enforcement frameworks
- Need to standardize across wildly different state regulatory structures

## Cross-Linking Value: 4/5
- Track multi-state operators (MSOs) across state license databases
- Cross-reference with corporate ownership data
- Link enforcement actions to license holders across states
- Track equity/social equity license programs and their outcomes
- Overlay with Census demographics for equity analysis

## Score Summary
| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 3 | Emerald Intel, Dan K Reports partially cover this |
| Buyer Clarity | 3 | Cannabis industry consultants, MSOs, investors |
| Technical Feasibility | 3 | State portals vary; some API-accessible |
| Cross-Linking Value | 4 | MSO tracking across states is valuable |
| Scale | 4 | 4,000+ new licenses/year; 30+ legalized states |
| Credibility Signal | 3 | Cannabis policy is hot but controversial |
| **TOTAL** | **20** | **BORDERLINE** |

## Decision: REJECT (borderline)
At exactly 20/30, this could go either way. Rejecting for the following reasons:
1. Cannabis remains federally illegal, creating reputational risk for Nathan's professional brand
2. Emerald Intel is a well-funded direct competitor in this exact space
3. Technical feasibility is moderate — each state requires custom work
4. Buyer universe is smaller and more niche than other candidates
5. Other candidates (CFPB, TRI, SEC Subsidiary) score higher and have better strategic alignment

If cannabis federal legalization advances, revisit this idea.
