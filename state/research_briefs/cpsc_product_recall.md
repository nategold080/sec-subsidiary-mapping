# CPSC Product Safety & Recall Tracker
## Research Brief — 2026-03-03

### Concept
Cross-linked database of CPSC consumer product recalls, SaferProducts.gov incident reports, CPSC injury surveillance data (NEISS), and import safety data. The unique value: connecting product recalls to the injury reports that triggered them, tracking manufacturer/importer recall histories, and linking recall patterns to import country of origin. Answers: "Which manufacturers have the worst safety records, what products cause the most injuries, and where are they imported from?"

### Data Gap Analysis
CPSC provides a Recalls API (JSON, since 1973) and SaferProducts.gov incident report API (OData). However, these are **separate systems** with no cross-linked product. CPSC's NEISS injury data is available through their query tool but not linked to recalls. No free product connects recalls -> incident reports -> injury data -> manufacturer history -> import origin in a unified database.

### Data Sources (All Verified Working)
1. **CPSC Recalls API** — cpsc.gov API, JSON format. Decades of recalls from 1973-present. Tested: returns recall number, products, hazards, manufacturers, importers, images, injury reports.
2. **SaferProducts.gov API** — OData protocol. Consumer incident reports with product, manufacturer, injury details.
3. **CPSC NEISS (National Electronic Injury Surveillance System)** — Statistical estimates of product-related injuries from ~100 ER sample hospitals. Query tool available.
4. **CBP Import Data** — Trade.gov provides import statistics by HTS code cross-linkable to product categories.

### Cross-Linking Value (MODERATE-HIGH)
- **Recall -> Incident reports**: Connect recall campaigns to triggering SaferProducts.gov reports
- **Manufacturer tracking**: Build manufacturer safety profiles across multiple recalls and incident categories
- **Importer identification**: Track which importers have products recalled and injury patterns by import origin
- **Product category analysis**: Aggregate recalls and injuries by CPSC product taxonomy
- **Timeline analysis**: Track time from first incident report to recall issuance

### Scale
- Recalls: ~5,000+ recalls (1973-present, ~400/year recently)
- SaferProducts.gov: Tens of thousands of incident reports
- NEISS: ~400,000 cases/year from ER surveillance (statistical sample)
- Combined: 50,000+ direct records, 400K+ injury estimates

### Named Buyers
1. **Product liability law firms** (Motley Rice, Burg Simpson, Simmons Hanly Conroy) — Litigation support
2. **Retail compliance teams** (Amazon, Walmart, Target) — Supplier safety screening
3. **Consumer product testing** (UL Solutions, Intertek, Bureau Veritas) — Market surveillance
4. **Insurance companies** (product liability underwriting)
5. **Import/trade compliance** (customs brokers, trade law firms)

### Score: 22/30
| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Data Gap Reality | 3 | CPSC APIs exist and are well-structured. Cross-linking adds value but individual datasets are reasonably accessible. |
| Buyer Clarity | 4 | Product liability firms, retailers, testing labs have clear use cases. |
| Technical Feasibility | 5 | Both APIs tested and working. JSON and OData formats. No auth needed. |
| Cross-Linking Value | 3 | Manufacturer name is the main key. Less structured cross-linking than NHTSA (no shared IDs). |
| Scale Demonstration | 4 | 50K+ direct recall/incident records. NEISS adds 400K+ injury estimates but is statistical sample. |
| Credibility Signal | 3 | Consumer product safety resonates with media and policy. |
