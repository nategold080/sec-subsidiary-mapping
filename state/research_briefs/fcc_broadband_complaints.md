# FCC Broadband & Telecom Complaint Tracker
## Research Brief — 2026-03-03

### Concept
Cross-linked database of FCC consumer complaints (broadband, telephone, TV), Broadband Data Collection (BDC) deployment data, and ISP service quality metrics. The value: connecting consumer complaint patterns to broadband deployment claims and identifying ISPs with the worst complaint records relative to their service areas.

### Data Gap Analysis
FCC publishes consumer complaint data via API and open data portal. BDC data is downloadable. BroadbandNow and similar sites aggregate coverage data but do NOT cross-link with consumer complaints. However, the FCC's own consumer complaint data is already reasonably well-structured and accessible. The cross-linking adds moderate incremental value.

### Data Sources
1. **FCC Consumer Complaints API** — fcc.gov/consumer-help-center-api — Individual complaints since Oct 2014.
2. **FCC Consumer Complaints Open Data** — opendata.fcc.gov — Downloadable.
3. **FCC BDC Data** — broadbandmap.fcc.gov/data-download — ISP coverage claims by geography.

### Cross-Linking Value (MODERATE)
- **ISP complaint rates**: Normalize complaints by subscriber count or coverage area
- **Coverage claims vs complaints**: Compare BDC coverage claims to availability complaints
- **Geographic patterns**: Map complaint hotspots

### Named Buyers
1. **Consumer advocacy** (National Digital Inclusion Alliance, Free Press)
2. **Municipal broadband offices** (for competitive intelligence)
3. **Telecom analysts** (MoffettNathanson, New Street Research)

### Score: 19/30 (BELOW THRESHOLD — REJECTED)
| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Data Gap Reality | 2 | FCC complaint data is already structured and accessible. BroadbandNow covers coverage well. |
| Buyer Clarity | 3 | Consumer advocacy is budget-constrained. Telecom analysts use paid Bloomberg/S&P data. |
| Technical Feasibility | 5 | APIs and downloads work. |
| Cross-Linking Value | 3 | ISP name matching is straightforward but insights are limited. |
| Scale Demonstration | 3 | Complaint volume unknown but likely modest compared to other ideas. |
| Credibility Signal | 3 | Broadband access is a policy issue but crowded space. |

### Recommendation: REJECT
Below 20-point threshold. FCC data is too accessible to create meaningful differentiation. Other ideas score higher.
