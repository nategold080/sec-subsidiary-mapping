# FDA MAUDE Medical Device Adverse Event Tracker — Research Brief

**Date:** 2026-03-02
**Status:** Researched — REJECTED (upholds prior rejection)
**Final Score:** 19/30

---

## 1. What Is MAUDE?

The Manufacturer and User Facility Device Experience (MAUDE) database is the FDA's repository of Medical Device Reports (MDRs) — reports of serious injuries, deaths, malfunctions, and other adverse events associated with medical devices. Mandatory reporters include manufacturers, importers, and device user facilities; voluntary reporters include healthcare professionals, patients, and consumers. The database contains over 17 million reports dating back to 1991, with detailed structured data available from approximately 2000 forward.

MAUDE consists of 135 fields across six file types:
- **Master Event**: Core adverse event details, reporting source info
- **Device**: Manufacturer, product name, model number, product codes
- **Patient**: Treatment and outcome information
- **Text**: Free-text narrative descriptions from MedWatch forms
- **Device Problems**: Links reports to standardized problem codes
- **Problem Code Descriptions**: Maps codes to text descriptions

All records are linked via MDR REPORT KEY, with additional keys (DEVICE SEQUENCE NO, PATIENT SEQUENCE NUMBER) for multi-device/multi-patient reports.

---

## 2. Scoring Breakdown

### Data Gap Reality: 2/5

**This is the fatal weakness.** The data is already structured and freely available through multiple channels:

- **openFDA API** (https://open.fda.gov/apis/device/event/) provides the full MAUDE dataset as a free JSON API with bulk downloads, updated weekly. Supports search, filtering, counting, and aggregation out of the box.
- **openFDA also provides separate APIs** for 510(k) clearances, PMA approvals, device classifications, recall enforcement reports, device recalls, UDI identifiers, and registrations/listings — all as free JSON endpoints with bulk downloads.
- **FDA's own MAUDE search interface** (accessdata.fda.gov) provides web-based search, though limited to the last 10 years.
- **Bulk CSV/SAS/Stata downloads** are available from the FDA directly and from data.gov.

The raw data is thoroughly structured by the FDA itself. The openFDA API is well-documented, has an active developer community, and is maintained by a dedicated FDA engineering team with an open-source pipeline on GitHub (github.com/FDA/openfda).

This is fundamentally different from the reference projects (AG enforcement, school board votes, pension fund data) where the core data was truly unstructured or scattered across dozens of independent sources requiring custom scrapers. Here, the FDA has already done the aggregation work.

### Buyer Clarity: 3/5

Several buyer categories exist, but the market is already served by well-funded competitors:

**Potential buyers:**
1. **Medical device litigation law firms** (Troutman Pepper, Greenberg Traurig, Cohen Placitella & Roth) — use MAUDE data for case building, but typically have internal research teams or use existing tools
2. **Hedge funds / investment firms** — use adverse event spikes as trading signals against device manufacturers (Point72 is known to FOIA adverse event data)
3. **Medical device manufacturers** — need postmarket surveillance benchmarking against competitors
4. **Hospital systems and GPOs** — evaluate device safety before procurement decisions
5. **Patient advocacy organizations** — track specific device issues

**The problem:** These buyers are already served by established competitors (see below). The marginal value of another MAUDE aggregator is low.

### Technical Feasibility: 5/5

Extremely high feasibility, which is actually a negative signal for this project:

- openFDA provides free, well-documented JSON APIs for all relevant device databases
- Bulk downloads available for every endpoint
- No authentication required (API keys optional, only for higher rate limits)
- No scraping needed — it is all API-based
- Data is already structured in JSON with consistent schemas

This is the easiest possible data to access. But high feasibility here indicates low defensibility — anyone can do this in a weekend with the openFDA API.

### Cross-Linking Value: 4/5

This is the strongest dimension. The openFDA ecosystem has 9+ device-related endpoints that could be cross-linked:

1. **MAUDE adverse events** + **510(k) clearances** = Which regulatory pathway correlates with more adverse events?
2. **MAUDE adverse events** + **Device recalls** = Do adverse event spikes predict recalls? What is the lag time?
3. **MAUDE adverse events** + **Warning letters** = Do manufacturers with warning letters have higher adverse event rates?
4. **MAUDE adverse events** + **UDI data** = Device-level tracking when UDI is available
5. **MAUDE adverse events** + **Device classification** = Risk profiles by device class (I, II, III)
6. **MAUDE adverse events** + **PMA approvals** = Safety profiles of PMA vs 510(k) devices
7. **Manufacturer entity resolution** across all databases — the same manufacturer appears under different name variants across MAUDE, 510(k), recalls, and UDI databases

**Key data quality challenges that create cross-linking value:**
- MAUDE manufacturer names are not standardized (e.g., "Boston Scientific" vs "BOSTON SCIENTIFIC CORPORATION" vs "Boston Scientific Corp.")
- Product codes are sometimes incorrectly assigned
- ~8% of records share EVENT KEYs across multiple MDR REPORT KEYs (duplicate/related reports from different submitters)
- Patient outcome fields contain concatenated multi-patient data that requires careful parsing
- ~25% of device problem codes lack informative descriptions

However, Redica Systems has already built exactly this kind of linked data model as their core product.

### Scale Demonstration: 5/5

Trivially achievable. MAUDE alone contains 17+ million reports. Even a focused slice (e.g., Class III devices from 2020-2026) would yield hundreds of thousands of records. Combined with 510(k) clearances (~250,000+), recalls (~30,000+), and other databases, scale is not a constraint whatsoever.

### Credibility Signal: 2/5 (revised down from prior score of 3)

- Medical device safety is an important domain, but this project would not be novel enough to generate significant attention
- Academic researchers already use MAUDE extensively — a 2024 scoping review found 13% of postmarket surveillance studies used MAUDE data directly
- Researchers who need MAUDE data can already access it through openFDA or bulk downloads
- The project would not open doors to notable collaborations because the data access problem is already solved
- Contrast with school board votes (literally the first structured database) or pension fund tracking (novel PE cross-referencing) — those had genuine novelty

---

## 3. Existing Competitors (Critical Issue)

### DeviceEvents (deviceevents.com)
- Cloud-based platform for MAUDE analytics
- Searches all 17.4+ million reports (vs FDA's 10-year web search limit)
- Provides trend visualization, keyword metrics, Excel exports
- Monthly notification alerts for tracked devices
- Serves hospitals, law firms, financial institutions, manufacturers, patient advocacy groups
- Custom research reports available
- Enterprise pricing (not publicly disclosed)

### Redica Systems (redica.com)
- Founded 2010, 200+ customers
- "World's first Quality and Regulatory Intelligence platform"
- Cross-links inspections, adverse events, recalls, warning letters
- Advanced visualization dashboards, real-time monitoring
- Entity resolution across FDA databases (using Zingg.ai)
- Serves pharma, biotech, medtech, medical device companies
- Enterprise pricing (not publicly disclosed, likely $10K-$50K+/year)
- Raised venture funding, has dedicated engineering team

### Complizen (complizen.ai)
- AI-enabled FDA compliance platform
- 510(k) regulatory pathway tools
- Device monitoring and alerting
- Multi-tier subscription pricing (specific amounts behind paywall)

### Clarivate (clarivate.com)
- Enterprise regulatory intelligence across 80+ markets
- 30+ years of curated regulatory data
- Covers medical devices as part of broader life sciences offering
- Major publicly traded company ($4B+ market cap)

### IQVIA
- MedTech compliance solutions spanning entire product lifecycle
- Global coverage with geographic-specific insights
- Part of a $40B+ data analytics company

**Assessment:** The competitive landscape is saturated. Multiple well-funded companies with dedicated engineering teams, sales forces, and years of market presence already serve every buyer segment. A new entrant without domain expertise, sales channels, or proprietary data sources would struggle to differentiate.

---

## 4. What Cross-Linking Would Actually Look Like

The most defensible version of this project would be a "Medical Device Risk Intelligence Platform" that cross-links:

| Source | openFDA Endpoint | Records | What It Adds |
|--------|-----------------|---------|--------------|
| MAUDE adverse events | /device/event | 17M+ | Core safety signal data |
| 510(k) clearances | /device/510k | 250K+ | Regulatory pathway, predicate devices |
| PMA approvals | /device/pma | 20K+ | Class III device approvals |
| Device recalls | /device/recall | 30K+ | Recall actions and classifications |
| Enforcement reports | /device/enforcement | 15K+ | Recall enforcement details |
| Device classification | /device/classification | 7K+ | Product codes, device classes, panels |
| UDI database | /device/udi | 3M+ | Unique device identifiers |
| Registrations/listings | /device/registrationlisting | 500K+ | Manufacturer facility data |

The unique analytical value would come from:
1. **Manufacturer entity resolution** across all 8 databases (matching "MEDTRONIC INC" = "Medtronic, Inc." = "MEDTRONIC PLC" etc.)
2. **Predicate device safety chains** — tracking whether devices cleared through 510(k) predicates of recalled devices also have elevated adverse events (a JAMA 2023 study found this is a real issue)
3. **Time-series signal detection** — adverse event spike detection correlated with subsequent recall probability
4. **Device class risk profiles** — comparative safety metrics across product categories

**But Redica Systems already does all of this**, with 200+ paying customers and a dedicated entity resolution pipeline.

---

## 5. Why This Fails the Data Factory Pattern

The reference projects succeed because they:
1. Found **genuinely unstructured public data** that no one had aggregated (AG press releases, school board minutes, pension fund PDFs)
2. Built **deterministic extraction pipelines** that created structured data where none existed
3. Had **no direct free competitors** offering the same data

The FDA MAUDE project fails on all three:
1. The data is **already structured** by the FDA via openFDA
2. There is **no extraction to build** — it is download and reorganize, not extract and structure
3. There are **multiple well-funded competitors** (DeviceEvents, Redica, Clarivate, IQVIA) already serving every buyer segment

The core IP of the Data Factory pattern is the extraction/structuring step. When the data is already structured, the only value-add is analytics and presentation — which is a much weaker moat and faces direct competition from companies with 10+ years of domain expertise.

---

## 6. Final Score

| Criterion | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| Data Gap Reality | 5 | 2 | 10 |
| Buyer Clarity | 5 | 3 | 15 |
| Technical Feasibility | 5 | 5 | 25 |
| Cross-Linking Value | 5 | 4 | 20 |
| Scale Demonstration | 3 | 5 | 15 |
| Credibility Signal | 2 | 2 | 4 |
| **Raw Total** | | **19/30** | |

**Decision: REJECT**

Score of 19 is below the 20-point threshold. Even at exactly 20, this would be a weak candidate given the competitive landscape and lack of data structuring moat.

---

## 7. Could This Be Salvaged?

### Possible pivot: Cross-database Medical Device Risk Intelligence with novel analytics
If the project focused exclusively on the cross-linking angle (linking all 8 openFDA endpoints + FDA warning letters + state-level data) AND produced novel analytical outputs (predicate chain risk scoring, manufacturer compliance timelines, geographic risk mapping) it might score slightly higher. But:
- Redica Systems already does this with $10M+ in funding and 200+ customers
- The analytics layer requires medical device domain expertise to be credible
- The buyer segments are all enterprise (long sales cycles, need credibility Nathan does not yet have in medtech)

### Alternative: Narrow slice for an underserved audience
Litigation attorneys and hedge funds may represent underserved niches where a lower-cost, self-service tool could work. DeviceEvents already targets these segments specifically, but a free/cheap alternative with pre-built cross-linked datasets could find traction. However, this still does not meet the Data Factory pattern of creating structured data from unstructured sources.

### Recommendation
Do not pursue. The time would be better spent on projects where Nathan's extraction pipeline IS the product — where without his code, the structured data simply does not exist. The nursing home tracker, PUC rate case tracker, and insurance rate filing tracker all fit this criterion far better.

---

## Sources

- openFDA Device APIs: https://open.fda.gov/apis/device/
- openFDA MAUDE info: https://open.fda.gov/data/maude/
- FDA MAUDE search: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/search.cfm
- MAUDE file structure primer (PMC): https://pmc.ncbi.nlm.nih.gov/articles/PMC5994953/
- Redica Systems MAUDE analysis: https://redica.com/keys-to-accurately-analyzing-fdas-maude-database/
- DeviceEvents: https://deviceevents.com/
- DeviceEvents hedge fund strategies: https://deviceevents.com/hedge-fund-strategies/
- Redica Systems: https://redica.com/redica-for-medtech/
- FDA device recall database: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfres/res.cfm
- JAMA 510(k) recall study: https://jamanetwork.com/journals/jama/fullarticle/2800188
- Complizen FDA guide: https://www.complizen.ai/post/fda-medical-device-databases-complete-guide
