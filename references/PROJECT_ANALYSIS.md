# Comprehensive Analysis of Four Data Projects

**Generated: 2026-03-02**
**Purpose: Blueprint for an autonomous system to generate similar projects**

---

# PROJECT A: AG Enforcement Tracker

## A1. PROJECT IDENTITY

**Name:** AG Enforcement Tracker
**Description:** A structured database of state Attorney General enforcement actions scraped from AG press release websites across 9 US states.

**Data gap:** No centralized, machine-readable database of state AG enforcement actions exists. Government affairs consultancies, compliance teams, and corporate counsel currently rely on manual monitoring of individual state AG websites to track enforcement trends, identify multi-state enforcement targets, and benchmark settlement amounts.

**Who cares:** Government affairs consultancies, corporate compliance departments, defense-side law firms, lobbying firms, media/investigative journalists, academic researchers studying regulatory enforcement.

**Monetization angle:** Data licensing to government affairs consultancies (subscription model for ongoing updates), one-time sale of curated datasets to compliance teams, research collaboration with law schools studying enforcement patterns.

**Credibility boost:** The dataset covers $893B in total monetary enforcement value across 5,779 active records. Cross-state defendant tracking (201 defendants in multiple states) demonstrates analytical sophistication. The methodology one-pager and polished dashboard serve as client-ready deliverables.

## A2. TECHNICAL ARCHITECTURE

### File/Folder Structure
```
AG regulations project/
  ag-enforcement-tracker/
    CLAUDE.md                          (529 lines - project bible)
    PROBLEMS.md                        (328 lines - 38 issues, all DONE)
    DEMO_READINESS_PROMPT.md           (142 lines)
    DEMO_POLISH_PROMPT.md              (63 lines)
    DEFERRED.md                        (14 lines)
    pyproject.toml                     (66 lines)
    requirements.txt                   (9 lines)
    runtime.txt                        (python-3.12.8)
    Procfile                           (Streamlit deployment)
    .streamlit/config.toml             (dark theme)
    .devcontainer/devcontainer.json    (Python 3.11 container)
    config/
      states.yaml                      (316 lines - 15 states, 6 active)
      taxonomy.yaml                    (193 lines - 12 violation categories)
      entities.yaml                    (187 lines - 140+ alias mappings)
      defendant_blocklist.yaml         (289 lines - 220 exact + 68 regex)
    src/
      __init__.py
      cli.py                           (645 lines - Click CLI, 10 commands)
      scrapers/
        base.py                        (457 lines - async httpx, rate limiting)
        registry.py                    (108 lines - auto-discovery)
        states/
          new_york.py                  (14 lines)
          ohio.py                      (13 lines)
          oregon.py                    (14 lines)
          pennsylvania.py              (81 lines)
          texas.py                     (48 lines)
          virginia.py                  (61 lines)
      extractors/
        filter.py                      (412 lines - two-stage enforcement filter)
        patterns.py                    (797 lines - core regex extraction)
        press_release.py               (350 lines - extraction orchestrator)
        llm_fallback.py                (13 lines - placeholder)
      normalization/
        entities.py                    (447 lines - fuzzy entity resolution)
      validation/
        schemas.py                     (220 lines - Pydantic v2 models)
        dedup.py                       (335 lines - multistate duplicate detection)
      storage/
        models.py                      (194 lines - SQLAlchemy ORM, 8 tables)
        database.py                    (102 lines - DB operations)
        migrations.py                  (76 lines)
      api/
        server.py                      (27 lines - FastAPI)
        routes.py                      (390 lines - 6 endpoints)
      dashboard/
        app.py                         (1,296 lines - Streamlit dashboard)
    scripts/
      analyze.py                       (515 lines - insights report)
      export.py                        (153 lines)
      export_clean.py                  (228 lines)
      bulk_extract.py                  (413 lines - batch extraction)
      bulk_scrape.py                   (151 lines - concurrent async scrape)
      curate_demo_sample.py            (467 lines - representative sample)
      seed_from_fixtures.py            (323 lines - fixture-based seeding)
      wayback_scrape.py                (934 lines - Wayback Machine CDX)
      rescrape_details.py              (230 lines)
      backfill.py                      (32 lines - placeholder)
    tests/                             (~274 test cases across 10 files)
    tests/fixtures/                    (43 HTML fixture files across 10 states)
    data/processed/                    (CSV, JSON, Markdown exports)
    data/ag_enforcement.db             (SQLite database)
```

### Tech Stack
- **Language:** Python 3.12.8
- **HTTP:** httpx (async), selectolax for HTML parsing
- **Fuzzy matching:** thefuzz (token_sort_ratio)
- **ORM:** SQLAlchemy 2.0 + SQLite
- **Validation:** Pydantic v2
- **CLI:** Click + Rich (console tables, progress bars)
- **API:** FastAPI with CORS
- **Dashboard:** Streamlit + Plotly (choropleth maps, bar/donut/line charts)
- **Deployment:** Heroku/Streamlit Cloud (Procfile + runtime.txt)
- **No LLM dependency** for any core extraction

### Data Sources

| State | URL | Method |
|-------|-----|--------|
| California | `https://oag.ca.gov/media/news` | Direct scrape, query_param pagination |
| New York | `https://ag.ny.gov/press-release` | Wayback Machine CDX API |
| Ohio | `https://www.ohioattorneygeneral.gov/Media/News-Releases` | Direct scrape |
| Oregon | `https://www.doj.state.or.us/media-home/news-media-releases/` | Direct scrape |
| Texas | `https://www.texasattorneygeneral.gov/news/releases` | Direct scrape |
| Washington | `https://www.atg.wa.gov/news/news-releases` | Direct + Wayback |
| Massachusetts | `https://mass.gov/news/ag-*` | Wayback Machine CDX |
| Pennsylvania | `https://www.attorneygeneral.gov/taking-action/*` | Wayback Machine CDX |
| Virginia | Joomla-based AG site | Direct scrape |

**Wayback Machine CDX API:** `https://web.archive.org/cdx/search/cdx` with state-specific URL patterns. Rate limited at 1 request/second.

### Data Pipeline (Step by Step)

1. **SCRAPE** -- Async httpx scrapers hit AG press release websites. Config-driven CSS selectors from `states.yaml`. Rate limited at 2s per domain, 3 retries with exponential backoff. User-Agent: "AGEnforcementTracker/1.0 (academic research project)". For blocked states (NY, PA, CT, MA, IL), Wayback Machine CDX API fetches archived versions. Stores: state, date, headline, source_url, raw_text (up to 10,000 chars).

2. **FILTER** -- Two-stage classifier separates enforcement from non-enforcement press releases. Stage 1: 68 enforcement keywords vs 142 non-enforcement keywords + 112 headline regex patterns. Stage 2: requires defendant-like entity AND (dollar amount OR statute citation OR court name). Filters ~48% of press releases.

3. **EXTRACT** -- Rule-based regex extraction from press release text. Extracts: action type (6 types), settlement amounts (3-priority hierarchy with $30B cap), defendants (12 headline + 14 body patterns), statutes (4 regex + 42 common name mappings), violation categories (12 categories via keyword matching), dates, multistate status. Quality score formula: date(0.15) + defendants(0.25) + amount(0.20) + category(0.15) + statute(0.10) + body_length(0.10) + type(0.05).

4. **NORMALIZE** -- Entity resolution: clean legal suffixes -> alias lookup (entities.yaml, 140+ mappings) -> fuzzy match (thefuzz token_sort_ratio >=85 auto, 70-85 review) -> new entity. 124+ stopwords, 40+ garbage patterns, blocklist validation.

5. **VALIDATE** -- Pydantic schemas enforce types. Deduplication via O(n^2) pairwise comparison with union-find clustering. 30-day window for single-state, 730 days for multistate. Confidence = defendant(40%) + date(20%) + amount(30%) + headline(10%).

6. **STORE** -- SQLAlchemy 2.0 ORM with SQLite. 8 tables: enforcement_actions, defendants, action_defendants, violation_categories, monetary_terms, statutes_cited, multistate_actions, scrape_runs.

7. **SERVE** -- FastAPI REST API (6 endpoints). Streamlit dashboard with 15+ interactive sections.

### Output Format
- **SQLite database:** 11,229 scraped records, 5,779 active (quality > 0.1), 3,930 defendants, $893B monetary value
- **CSV exports:** Full export (33,349 rows), clean export with quality >= 0.5 (4,531 rows), curated demo sample (62 rows)
- **JSON exports:** Full structured data (224,584 lines)
- **Markdown reports:** 8-section insights report, demo insights, methodology one-pager
- **PDF:** Methodology one-pager (print-ready HTML)
- **Streamlit dashboard:** Live interactive web app

### Data Quality Validation
- Quality scoring (0.0-1.0) on every record
- 38 documented problems, all resolved
- 274 test cases across 10 test files
- Entity resolution verification for top 5 companies (78-100% accuracy)
- $50B sanity cap on settlement amounts
- Defendant blocklist (220 exact + 68 regex patterns)
- 124+ stopword filters for garbage entity names

### Scheduling/Automation
No cron jobs. Manual CLI execution: `ag-tracker scrape --all` then `ag-tracker extract --all`.

## A3. OUTREACH STRUCTURE
**No outreach files exist** in this project. No target lists, email templates, or contact databases. The dashboard footer contains: Nathan Goldberg, nathanmauricegoldberg@gmail.com, LinkedIn link.

## A4. SCOPE & EFFORT

- **Total Python lines:** ~8,500+ (source + scripts + tests)
- **Hardest part technically:** The Wayback Machine scraper (934 lines) for states that block direct access, and the regex extraction engine (patterns.py at 797 lines) covering dollar amounts, defendants, statutes, and action types with dozens of edge cases.
- **External dependencies requiring manual intervention:** None for core pipeline. Wayback Machine is fully public. Some states may occasionally change website structure.
- **Fully automatable:** Scraping, extraction, export, dashboard. **Requires human judgment:** Entity resolution review queue (fuzzy matches 70-85%), curating demo samples, adding new states (requires CSS selector configuration).

---

# PROJECT B: RegScope (Law Comment Data Project)

## B1. PROJECT IDENTITY

**Name:** RegScope -- Federal Rulemaking Public Comment Analyzer
**Description:** A 7-stage NLP pipeline that downloads, structures, and analyzes public comments on federal rulemakings from Regulations.gov.

**Data gap:** Federal agencies receive thousands of public comments on proposed rules, but there's no automated way to analyze them at scale. Agencies, lobbyists, and advocacy groups manually read through comments to understand stakeholder positions, identify form letter campaigns, and find the most substantive input.

**Who cares:** Federal agencies (rulemaking staff), lobbying firms, trade associations, law firms specializing in regulatory practice, advocacy organizations, academic researchers studying the rulemaking process.

**Monetization angle:** Per-docket analysis reports sold to law firms and trade associations ($500-5,000 per docket). Subscription service for continuous monitoring of agency dockets. Research collaboration with administrative law scholars.

**Credibility boost:** Processes 2,150 real comments across 6 dockets from 5 federal agencies (BOEM, DOT, NHTSA, PHMSA, USCG). Demonstrates form letter detection (326-copy campaign in PHMSA docket), stance analysis, and substantiveness scoring. The methodology is reproducible and testable (158 tests passing).

## B2. TECHNICAL ARCHITECTURE

### File/Folder Structure
```
Law Comment Data Project/
  CLAUDE.md                            (209 lines)
  pyproject.toml                       (49 lines - 17 dependencies)
  requirements.txt                     (3 lines - dashboard only)
  runtime.txt                          (python-3.12.8)
  Procfile                             (Railway deployment)
  README.md                            (87 lines)
  config.toml.example                  (96 lines - 33 configurable keys)
  .streamlit/config.toml               (dark theme)
  .gitignore
  regscope/
    __init__.py                        (version 0.1.0)
    __main__.py                        (6 lines)
    cli.py                             (309 lines - 9 Click commands)
    config.py                          (147 lines - TOML loader)
    db.py                              (519 lines - per-docket SQLite, 11 tables)
    PROBLEMS.md                        (302 lines - 42 issues, all fixed)
    api/
      regulations.py                   (185 lines - Regulations.gov v4 client)
    pipeline/
      ingest.py                        (273 lines - download from API)
      extract.py                       (321 lines - PDF/DOCX/HTML extraction)
      dedup.py                         (326 lines - 3-tier deduplication)
      embed.py                         (209 lines - sentence embeddings)
      topics.py                        (329 lines - BERTopic modeling)
      classify.py                      (549 lines - stance/stakeholder/substantiveness)
      report.py                        (759 lines - Markdown/CSV/JSON/Excel export)
    utils/
      rate_limit.py                    (98 lines - thread-safe rate limiter)
      text.py                          (161 lines - normalization, hashing)
  dashboard/
    app.py                             (1,072 lines - Streamlit dashboard)
  data/dockets/
    BOEM-2024-0008.db                  (14.4 MB - 1,207 comments)
    BOEM-2025-0582.db                  (3.2 MB - 352 comments)
    DOT-OST-2024-0049.db              (4.2 MB - 108 comments)
    NHTSA-2024-0100.db                (1.4 MB - 37 comments)
    PHMSA-2024-0005.db                (17.1 MB - 405 comments)
    USCG-2025-0903.db                 (560 KB - 41 comments)
  output/                              (reports, CSV, JSON exports)
  tests/                               (8 test files, 158 tests)
```

### Tech Stack
- **Language:** Python 3.11+
- **HTTP:** httpx (sync client)
- **NLP:** sentence-transformers (all-MiniLM-L6-v2), BERTopic, HDBSCAN, UMAP, transformers (facebook/bart-large-mnli for zero-shot classification)
- **Dedup:** datasketch (MinHash LSH), numpy (cosine similarity)
- **Document extraction:** PyMuPDF (fitz), python-docx, pytesseract (OCR fallback)
- **Database:** SQLite with WAL mode, per-docket databases
- **CLI:** Click + Rich
- **Dashboard:** Streamlit + Plotly + Pandas
- **Optional LLM:** OpenAI gpt-4o-mini for topic labels only (not required)
- **Deployment:** Railway (Procfile)

### Data Sources

| Source | URL | Access |
|--------|-----|--------|
| Regulations.gov API v4 | `https://api.regulations.gov/v4` | Free API key (900 requests/hour) |

**API endpoints used:**
- `GET /dockets/{docket_id}` -- Docket metadata
- `GET /comments?filter[docketId]=X` -- List comments with pagination
- `GET /comments/{comment_id}?include=attachments` -- Individual comment detail

### Data Pipeline (Step by Step)

1. **INGEST** (ingest.py) -- Downloads docket metadata and all comments from Regulations.gov API. Cursor-based pagination handles >5,000 comments. Fetches individual comment details including attachments. Per-key rate limiting with round-robin API key rotation.

2. **EXTRACT** (extract.py) -- Extracts text from attachment files. PDF via PyMuPDF, OCR fallback via Tesseract for scanned PDFs. DOCX via python-docx. HTML via regex stripping. Detects "see attached" stub comments and replaces with attachment text.

3. **DEDUP** (dedup.py) -- Three-tier deduplication:
   - Tier 1: Exact (SHA-256 hash of normalized text)
   - Tier 2: Near-duplicate (MinHash LSH, Jaccard threshold 0.85, word 3-grams)
   - Tier 3: Semantic (cosine similarity on sentence embeddings, threshold 0.92)

4. **EMBED** (embed.py) -- Generates sentence embeddings using all-MiniLM-L6-v2 for unique/representative comments only. Batch size 64. Stores as BLOB in SQLite.

5. **TOPICS** (topics.py) -- BERTopic with pre-computed embeddings. Adaptive parameter scaling based on corpus size. CountVectorizer with bigrams. Propagates topics to dedup group members.

6. **CLASSIFY** (classify.py) -- Three sub-stages:
   - Stakeholder type: Rule-based pattern matching on organization field (8 types: academic, government, law_firm, trade_association, nonprofit, industry, individual, unknown)
   - Stance: Zero-shot classification via facebook/bart-large-mnli (6 stances: support, oppose, conditional_support, conditional_oppose, neutral_informational, unclear)
   - Substantiveness: Weighted heuristic (7 subscores: length, citations, section refs, technical vocab, data references, legal terms, uniqueness)

7. **REPORT** (report.py) -- Generates 7-section Markdown reports + CSV/JSON/Excel exports. Optional LLM topic labels via gpt-4o-mini.

### Output Format
- **Per-docket SQLite databases:** 11 tables, 15 indexes
- **Markdown reports:** 7 sections (overview, landscape, topics, stakeholders, stance, substantiveness, quality)
- **CSV/JSON/Excel exports:** 19 columns per comment
- **Streamlit dashboard:** Multi-docket browser with deep-dive per docket

### Data Quality Validation
- 42 documented problems, all fixed
- 158 tests passing
- Comment quality metrics in every report (text coverage, attachment extraction rates)
- Dedup verification (exact + near + semantic tiers)
- Substantiveness scoring validated against known high-quality comments

### Scheduling/Automation
No cron jobs. CLI-driven: `regscope analyze DOCKET-ID --api-key KEY`.

## B3. OUTREACH STRUCTURE
**No outreach files exist.** Dashboard footer: Nathan Goldberg, email, LinkedIn.

## B4. SCOPE & EFFORT

- **Total Python lines:** ~7,800 (regscope package ~2,900 + dashboard 1,072 + tests ~2,874 + scripts)
- **Hardest part technically:** The 3-tier deduplication system (exact + MinHash LSH + semantic cosine similarity), the adaptive BERTopic parameter scaling for varying corpus sizes, and the substantiveness scoring heuristic (7 weighted subscores).
- **External dependencies requiring manual intervention:** Regulations.gov API key (free, requires registration at api.data.gov). Optional: OpenAI API key for topic labels.
- **Fully automatable:** Entire pipeline from ingest to report. **Requires human judgment:** Choosing which dockets to analyze, interpreting report findings, tuning substantiveness weights.

---

# PROJECT C: Pension Fund Alternative Investment Tracker

## C1. PROJECT IDENTITY

**Name:** Pension Fund Alternative Investment Extraction Tool
**Description:** Extracts, normalizes, and cross-links private equity/alternative investment commitment data from 5 major US public pension fund disclosures.

**Data gap:** There is no centralized database of which public pension funds invest in which private equity funds. Each pension publishes disclosures in different formats (HTML, PDF) with different schemas. Nobody has systematically linked the same PE fund across multiple pension systems to enable cross-allocator analysis.

**Who cares:** Private equity fundraising teams (knowing which pensions invest in competitors), placement agents, investment consultants, fund-of-funds managers, academic researchers studying institutional investor behavior.

**Monetization angle:** Primary target is Dakota Marketplace (Rob Robertson, President) -- a PE fundraising intelligence platform. Data licensing to PE fund marketers. Research collaboration with finance academics.

**Credibility boost:** 2,489 commitment records across 5 pension systems totaling $508B. 346 funds cross-linked across 2+ systems (14 across all 5). Board meeting intelligence pipeline extracting forward-looking signals from meeting minutes. Professional Excel deliverables and methodology PDFs prepared for Dakota Marketplace evaluation.

## C2. TECHNICAL ARCHITECTURE

### File/Folder Structure
```
pension fund project/
  .env                                 (3 PageIndex API keys)
  .gitignore
  .streamlit/config.toml              (dark theme)
  CLAUDE.md
  PROBLEMS.md                          (24 issues, all DONE)
  README.md
  Procfile                             (Streamlit on Heroku)
  requirements.txt                     (12 dependencies)
  runtime.txt                          (python-3.12.8)
  setup.py                             (pension-fund-tracker package)
  src/
    __init__.py
    __main__.py                        (4 lines)
    cli.py                             (481 lines - 13 Click commands)
    pipeline.py                        (264 lines - extraction orchestrator)
    database.py                        (783 lines - 11 SQLite tables)
    entity_resolution.py               (390 lines - cross-system fund matching)
    quality.py                         (368 lines - data quality checks)
    export.py                          (635 lines - 11 export files)
    analysis.py                        (582 lines - demo analysis outputs)
    dashboard.py                       (1,332 lines - Streamlit + Plotly)
    board_minutes.py                   (1,125 lines - NLP from meeting PDFs)
    pageindex_extraction.py            (352 lines - PageIndex API integration)
    llm.py                             (11 lines - placeholder)
    seed.py                            (107 lines - consulting firm data)
    adapters/
      __init__.py                      (56 lines - registry)
      base.py                          (136 lines - abstract adapter)
      calpers.py                       (190 lines - HTML table parsing)
      calstrs.py                       (209 lines - PDF parsing)
      wsib.py                          (192 lines - PDF parsing)
      oregon.py                        (199 lines - PDF parsing)
      ny_common.py                     (256 lines - PDF parsing)
      texas_trs.py                     (345 lines - limited disclosure)
      florida_sba.py                   (345 lines - blocked, 0 records)
    utils/
      normalization.py                 (1,046 lines - parsing + classification)
      html_parser.py                   (38 lines)
      pdf_parser.py                    (46 lines)
  tests/                               (13 test files, ~1,400 lines)
  data/
    pension_tracker.db                 (SQLite, 11 tables)
    cache/                             (cached source documents)
    exports/                           (11 CSV/MD files + 7 demo files)
    pageindex/                         (board meeting extraction results)
    board_intelligence.json            (structured board meeting signals)
    seed/consulting_firms.yaml         (12 firms, 9 engagements)
  docs/
    adding_a_fund.md
    data_dictionary.md
  create_dakota_sample.py              (737 lines - Excel for Dakota)
  fix_and_export.py                    (362 lines - verified Excel)
  verify_data.py                       (251 lines - data integrity audit)
  create_methodology_pdf.py            (209 lines - reportlab PDF)
  create_board_minutes_pdf.py          (931 lines - 4-page PDF)
  Dakota_Pension_Fund_Data_Sample.xlsx
  Dakota_Pension_Fund_Data_Sample_Feb19_.xlsx
  Pension_Fund_Commitment_Data_Methodology.pdf
  Board_Minutes_Intelligence_Methodology.pdf
```

### Tech Stack
- **Language:** Python 3.12.8
- **HTTP:** requests
- **HTML parsing:** BeautifulSoup + lxml
- **PDF parsing:** pdfplumber (word-level extraction with column boundaries)
- **Fuzzy matching:** rapidfuzz (ratio + token_sort_ratio)
- **NLP:** spaCy (board minutes)
- **Document intelligence:** PageIndex API (tree-structured RAG)
- **Database:** SQLite with WAL mode
- **CLI:** Click
- **Dashboard:** Streamlit + Plotly
- **Excel:** openpyxl (styled deliverables)
- **PDF generation:** reportlab (methodology documents)
- **Deployment:** Heroku (Procfile)

### Data Sources

| Pension Fund | AUM | URL | Format | Records |
|-------------|-----|-----|--------|---------|
| CalPERS | $503B | `calpers.ca.gov/.../pep-fund-performance-print` | HTML table | 429 |
| CalSTRS | $338B | `calstrs.com/private-equity-portfolio-performance-table` | PDF | 469 |
| WSIB (WA) | $190B | `sib.wa.gov/docs/reports/quarterly/ir063025.pdf` | PDF | 462 |
| Oregon | $100B | Oregon Treasury site, Q3 2025 report | PDF | 402 |
| NY Common | $268B | `osc.ny.gov/.../asset-listing-2025.pdf` | PDF (pp 146-152) | 727 |
| Texas TRS | $200B | TRS website (Incapsula-protected) | PDF (ACFR) | 1 (summary) |
| Florida SBA | $260B | sbafla.com (403 block) | PDF | 0 |

**Board meeting PDFs** from WSIB and Oregon, processed via PageIndex API.

### Data Pipeline (Step by Step)

1. **FETCH** -- Each adapter's `fetch_source()` downloads raw data (HTML page or PDF). Source hash (SHA256) caching prevents re-processing unchanged documents. `use_cache` parameter reads from `data/cache/` instead of making HTTP requests.

2. **PARSE** -- Adapter-specific deterministic parsing:
   - CalPERS: BeautifulSoup `<tr>` parsing with column index mapping
   - CalSTRS/WSIB/Oregon/NY Common: pdfplumber word-level extraction with hardcoded column boundaries (pixel coordinates)
   - Each adapter maps raw data to standardized record dict (18 fields)

3. **NORMALIZE** -- 1,046-line normalization module handles: dollar amounts ($1.2B, $500MM, parentheses-negative), percentages, dates (ISO/US/quarter/fiscal year), multiples (1.5x), fund names (strip LP/LLC, expand abbreviations), GP extraction from fund names (~170 known GPs), strategy classification (keyword-based + 150+ GP default mappings).

4. **ENTITY RESOLUTION** -- FundRegistry resolves fund names across pension systems:
   - Exact canonical name match -> "exact"
   - Exact alias match -> "alias"
   - Fuzzy match (rapidfuzz, 2+ secondary signals: GP match, vintage match, name_sim >85%) -> "fuzzy"
   - Hard reject if Roman numeral fund numbers differ
   - Create new fund -> "new"

5. **QUALITY** -- Checks: value ranges (commitment $0.1M-$5B, IRR -50% to +150%, multiple 0-15x), completeness (>33% of key fields), cross-fund consistency (vintage mismatch, multiple divergence >0.5x).

6. **EXPORT** -- 11 files: commitments.csv, fund_summary.csv, cross_pension_matrix.csv, top_funds.csv, top_gps.csv, performance_comparison.csv, performance_by_vintage.csv, consulting_engagements.csv, consultant_pension_matrix.csv, quality_report.md, summary_stats.md. Plus 7 demo analysis files.

7. **BOARD INTELLIGENCE** (separate pipeline) -- Board meeting PDFs -> NLP extraction (regex + spaCy) for investment commitments, personnel changes, policy approvals, dissent/sentiment, forward-looking signals -> PageIndex API for tree-structured RAG queries -> board_intelligence.json.

### Output Format
- **SQLite database:** 11 tables, 2,489 commitments, 1,640 funds, 346 cross-linked funds
- **CSV exports:** 11 files including cross-pension matrix
- **Excel deliverables:** Styled workbooks for Dakota Marketplace with 20 columns, alternating row colors, Re-Up flags
- **PDF methodology documents:** 1-page commitment data methodology + 4-page board minutes methodology
- **JSON:** Board intelligence feed (structured signals from 3 meetings)
- **Streamlit dashboard:** Interactive visualizations with board intelligence tab

### Data Quality Validation
- 24 documented problems, all resolved
- ~1,400 test lines across 13 files
- 132 auto-generated quality flags, 12 unresolved
- Cross-fund validation (346 funds independently cross-linked)
- Data integrity audit script (verify_data.py) checking Excel against SQLite
- Board intelligence: 100% commitment extraction accuracy (n=37)

### Scheduling/Automation
No cron jobs. CLI: `python -m src run` then `python -m src export`.

## C3. OUTREACH STRUCTURE

No dedicated outreach module, but **deliverables are explicitly prepared for a named target:** Rob Robertson, President of Dakota Marketplace. The Excel files include a cover sheet with contact info: "Nathan Goldberg, nathanmauricegoldberg@gmail.com, February 19, 2026, Prepared for: Rob Robertson, President -- Dakota Marketplace."

**Target information tracked implicitly:**
- Pension fund categorization (Tier 1 vs Tier 2 by disclosure quality)
- Consulting firm tracking (12 firms, 9 engagements)
- Cross-allocator intelligence (which GPs have broadest LP relationships)

## C4. SCOPE & EFFORT

- **Total Python lines:** ~14,084 across 37 Python files
- **Hardest part technically:** The pdfplumber word-level column boundary extraction (each PDF adapter has hardcoded pixel coordinates), the cross-system entity resolution with fuzzy matching and multiple secondary signals, and the board minutes NLP pipeline (1,125 lines).
- **External dependencies requiring manual intervention:** PageIndex API keys ($), manual PDF download for Texas TRS (Incapsula protection) and Florida SBA (403 block), manual cache file placement.
- **Fully automatable:** CalPERS (HTML), board intelligence dashboard. **Requires human judgment:** PDF column boundary calibration when pension funds change report formats, entity resolution review, Texas TRS/Florida SBA access workarounds.

---

# PROJECT D: School Board Vote Tracker

## D1. PROJECT IDENTITY

**Name:** School Board Vote Tracker
**Description:** The first structured database of school board voting records in the United States, scraping meeting minutes from 150 school districts across 20 states.

**Data gap:** No structured, searchable database of school board votes exists. Decisions on curriculum, budgets, personnel, and policies are made in thousands of local school board meetings but never aggregated or made searchable. Companies like Quorum Analytics track Congress/state legislatures but not school boards.

**Who cares:** EdTech companies (Quorum Analytics, FiscalNote, Burbio), education policy researchers, journalists covering local governance, advocacy groups monitoring school board decisions on DEI/curriculum/safety.

**Monetization angle:** Primary targets are Quorum Analytics, FiscalNote, and Burbio for data licensing or acquisition. The proof-of-concept demonstrates viability of school board vote tracking at scale. Could also serve as a job pipeline (demonstrating data engineering capabilities to these companies).

**Credibility boost:** 5,790 formal votes across 150 districts and 20 states. 11,366 individual roll-call vote records with named board members. 181 contested (non-unanimous) votes identified. Zero LLM cost via 1,865-line deterministic rule engine. Live dashboard at school-board-votes.up.railway.app.

## D2. TECHNICAL ARCHITECTURE

### File/Folder Structure
```
school vote project/
  claude_code_prompt.md                (341 lines - project specification)
  DEMO_FIX_PROMPT.md                   (114 lines)
  school-board-votes/
    .env                               (OpenAI + GitHub tokens)
    .env.example
    .streamlit/config.toml             (dark theme)
    Procfile                           (Railway deployment)
    requirements.txt                   (18 dependencies)
    README.md                          (235 lines)
    TECHNICAL_WRITEUP.md               (232 lines)
    PROBLEMS.md                        (347 lines - 37 issues, all DONE)
    config/
      settings.py                      (66 lines - env loader)
      districts.json                   (1,352 lines - 150 districts)
      extraction_config.yaml           (66 lines)
    database/
      models.py                        (163 lines - SQLAlchemy, 6 tables)
      operations.py                    (294 lines - CRUD + queries)
      init_db.py                       (24 lines)
    scraper/
      base_scraper.py                  (102 lines)
      boarddocs_scraper.py             (264 lines - Playwright headless)
      pdf_scraper.py                   (232 lines - unused in production)
      html_scraper.py                  (191 lines - unused in production)
      district_discovery.py            (56 lines)
    extraction/
      rule_engine.py                   (~1,865 lines - THE CORE IP)
      extractor.py                     (214 lines - LLM pipeline, unused)
      schemas.py                       (51 lines - Pydantic models)
      prompts.py                       (197 lines - LLM prompts, unused)
      validator.py                     (128 lines)
    analytics/
      vote_analytics.py                (222 lines)
      visualizations.py                (173 lines)
    interface/
      app.py                           (1,123 lines - Streamlit dashboard)
    scripts/
      run_scraper.py                   (107 lines)
      run_extraction.py                (288 lines)
      run_analytics.py                 (72 lines)
      scrape_all.py                    (434 lines - enhanced batch scraper)
      validate_sample.py               (94 lines)
      discover_districts.py            (276 lines)
    tests/                             (5 test files, 112 tests)
    docs/
      generate_methodology_pdf.py      (435 lines)
      methodology.pdf                  (1-page)
    data/
      database.sqlite                  (16 MB)
      scrape_progress.json             (resume support)
      raw_minutes/                     (1,646 .txt files, 32 MB)
      extracted/                       (1,634 .json files, 16 MB)
```

### Tech Stack
- **Language:** Python 3.12.8
- **HTTP:** requests
- **Browser automation:** Playwright (headless Chromium for BoardDocs AJAX)
- **HTML parsing:** BeautifulSoup + lxml
- **PDF parsing:** pdfplumber + PyMuPDF (fallback)
- **LLM (unused):** OpenAI gpt-4o-mini / gpt-4o (built but replaced by rule engine)
- **ORM:** SQLAlchemy 2.0 + SQLite with WAL mode
- **Validation:** Pydantic v2
- **Dashboard:** Streamlit + Plotly
- **PDF generation:** reportlab
- **Deployment:** Railway

### Data Sources

| Source | URL Pattern | Method |
|--------|-------------|--------|
| BoardDocs | `https://go.boarddocs.com/{state}/{org}/Board.nsf/Public` | Playwright headless browser |
| BoardDocs SEO API | `BD-GETMeetingsListForSEO` endpoint | Direct HTTP (no auth) |
| BoardDocs AJAX | `BD-GetAgenda`, `BD-GetAgendaItem`, `BD-GetMinutes` | Intercepted via Playwright |

**150 districts** configured in districts.json, all using BoardDocs platform. Districts identified by NCES ID. State distribution: CA=24, NY=17, OH=15, FL=11, VA=10, CO=8, TX=7, IL=6, WA=6, KS=4, NC=4, PA=4, WI=4, plus 6 more states.

### Data Pipeline (Step by Step)

1. **DISCOVER** -- `BD-GETMeetingsListForSEO` public API returns meeting IDs, dates, and types for any BoardDocs organization. No authentication needed.

2. **SCRAPE** -- Playwright headless browser opens BoardDocs meeting page. Intercepts AJAX responses (`BD-GetAgenda`, `BD-GetAgendaItem`) as items are clicked. Captures up to 25 agenda items per meeting. Detects and clicks "View Minutes" link, captures `BD-GetMinutes` response. Saves structured text to `data/raw_minutes/<district_id>/<name>_<date>.txt`. Rate limited at 1.5s between meetings. Single browser session reused across all districts.

3. **EXTRACT** -- Rule engine (1,865 lines) processes raw text:
   - Parses metadata header (district, date, meeting type)
   - Splits by `=== N.TITLE ===` delimiters into agenda sections
   - Classifies each item into 15 categories via regex patterns (~200+ patterns)
   - Detects vote likelihood via 30 positive + 20 negative patterns
   - Extracts vote details: counts ("5-2", "Ayes: 5, Nays: 2"), result, motion maker/seconder
   - Parses MINUTES TEXT sections for attendance and roll-call votes in 2 formats
   - Post-processing: deduplication, count validation, unanimity recalculation, impossible vote rejection, time-string guard

4. **VALIDATE** -- Normalizes vote types ("unanimous"/"consent" mapping), results ("approved"/"carried" -> "passed"), categories, member votes ("aye"/"yea" -> "yes"). Confidence scoring: high (3+ individual votes), medium (1-2 or explicit result), low (single pattern).

5. **STORE** -- SQLAlchemy ORM with SQLite. 6 tables: districts, meetings, agenda_items, votes, individual_votes, board_members. Name normalization strips 20+ title prefixes and 10+ suffixes.

6. **SERVE** -- Streamlit dashboard with 3 tabs (Overview, Board Members, Explore) and 4 exploration modes (Contested Votes, Keyword Search, Browse Districts, Find Board Members).

### Output Format
- **SQLite database:** 6 tables, 16 MB
- **Raw text files:** 1,646 meeting transcripts (32 MB)
- **Extracted JSON:** 1,634 structured meeting files (16 MB)
- **Streamlit dashboard:** Live at school-board-votes.up.railway.app
- **PDF methodology:** 1-page professional document

### Data Quality Validation
- 37 documented problems, all resolved and verified
- 112 tests (73 rule engine, integration, scraper, database)
- Confidence tiers: 58.6% high, 25.5% medium, 16.0% low
- Manual validation script (validate_sample.py) for random 30-vote audit
- Post-processing catches: impossible consent agenda votes, 0-0 false votes, time-string false parses, result/count mismatches

### Scheduling/Automation
No cron jobs. Scripts: `python scripts/scrape_all.py` (with `--resume`), then `python scripts/run_extraction.py`.

## D3. OUTREACH STRUCTURE
**No dedicated outreach files.** The project specification (claude_code_prompt.md) names targets: Quorum Analytics, FiscalNote, Burbio. Dashboard footer: Nathan Goldberg, email, LinkedIn.

## D4. SCOPE & EFFORT

- **Total Python lines:** ~8,700+ (rule_engine alone is 1,865 lines)
- **Hardest part technically:** The rule engine (1,865 lines) with ~200+ regex patterns for category classification, vote detection, count extraction, and roll-call parsing in 2 different formats. The BoardDocs Playwright scraper intercepting AJAX responses is also non-trivial (264 lines).
- **External dependencies requiring manual intervention:** Playwright browser installation. OpenAI API key (built but unused). BoardDocs districts must be manually discovered and added to districts.json.
- **Fully automatable:** Scraping, extraction, database storage, dashboard. **Requires human judgment:** Discovering new districts, handling non-BoardDocs platforms, validating new extraction patterns.

---

# 5. PATTERNS ACROSS ALL FOUR PROJECTS

## Common Architectural Patterns

### Shared Technology Stack
All four projects share:
- **Python 3.12.8** (identical runtime.txt)
- **SQLite with WAL mode** as the database
- **Click** for CLI
- **Streamlit + Plotly** for dashboards
- **Dark theme** with identical color scheme: `primaryColor="#0984E3"`, `backgroundColor="#0E1117"`, `secondaryBackgroundColor="#1B2A4A"`, `textColor="#E2E8F0"`
- **Pydantic v2** for validation
- **Rich** for terminal output
- Identical dashboard footer: "Built by Nathan Goldberg" + email + LinkedIn
- **Procfile** for deployment (Railway or Heroku)
- **CLAUDE.md** project specification files
- **PROBLEMS.md** issue tracking (total: 38 + 42 + 24 + 37 = 141 issues, ALL resolved)

### Pipeline Architecture (Identical Pattern)
Every project follows: **SCRAPE -> EXTRACT -> NORMALIZE -> STORE -> EXPORT -> SERVE**

| Stage | AG Tracker | RegScope | Pension Fund | School Vote |
|-------|-----------|----------|-------------|-------------|
| Scrape | httpx async | httpx sync | requests + cache | Playwright headless |
| Extract | Regex (797 lines) | PDF/DOCX/HTML extraction | pdfplumber column boundaries | Rule engine (1,865 lines) |
| Normalize | Entity resolution (thefuzz) | MinHash + embeddings | Entity resolution (rapidfuzz) | Category classification (regex) |
| Store | SQLAlchemy + SQLite | Raw SQLite | Raw SQLite | SQLAlchemy + SQLite |
| Export | CSV/JSON/Markdown | CSV/JSON/Excel/Markdown | CSV/Excel/Markdown/PDF | JSON + SQLite |
| Serve | Streamlit + FastAPI | Streamlit | Streamlit | Streamlit |

### Zero-LLM Design Philosophy
All four projects use **deterministic, rule-based extraction** as their core engine. LLM integration exists only as unused fallback or for optional enhancement (RegScope topic labels, School Vote hybrid extractor). This is a deliberate design choice for:
- Zero marginal cost per record
- Reproducible results
- No API dependency for core functionality

### Quality Tracking Pattern
Every project has a `PROBLEMS.md` with numbered issues (P1, P2, ...) and a status marker (DONE). This serves as both a development log and a quality assurance artifact.

## Common Outreach Patterns

**No project has a dedicated outreach module.** All four projects use the dashboard itself as the outreach/demo vehicle, with the author's contact information in the footer. Specific targets are named in project specification documents:
- AG Tracker: Government affairs consultancies (unnamed)
- RegScope: Law firms, agencies (unnamed)
- Pension Fund: Dakota Marketplace (Rob Robertson, named)
- School Vote: Quorum Analytics, FiscalNote, Burbio (named)

## What Makes These Projects "Good" (Evaluation Criteria for New Projects)

1. **Fills a real data gap** -- Information that is public but not aggregated, structured, or searchable
2. **Clear buyer** -- Specific organizations or industry verticals that would pay for this data
3. **Defensible methodology** -- Rule-based extraction with documented accuracy, quality scoring, and extensive testing
4. **Production-ready deliverable** -- Polished Streamlit dashboard, clean exports, methodology documentation
5. **Scale demonstration** -- Enough records (1,000+) across enough entities (100+) to prove viability
6. **Cross-entity linking** -- The most valuable insight comes from connecting the same entity across different data sources (AG: defendants across states; Pension: funds across pension systems)
7. **Minimal ongoing cost** -- No LLM dependency, no paid APIs for core pipeline (Regulations.gov is free, BoardDocs is public, pension disclosures are public)

## Minimum Viable Version

A new project reaches "client-ready" when it has:
1. **Data:** 500+ structured records from 3+ distinct sources
2. **Quality:** Quality scoring with 80%+ of records above minimum threshold
3. **Testing:** 50+ tests with documented problems and fixes
4. **Dashboard:** Live Streamlit app with 5+ interactive sections
5. **Exports:** CSV + at least one polished deliverable (Excel or PDF)
6. **Documentation:** CLAUDE.md + PROBLEMS.md + methodology one-pager

## Shared Config/Utilities/Templates

No code is literally shared across projects (they are separate directories, not a monorepo). However, the following patterns are replicated:
- `.streamlit/config.toml` (identical dark theme config)
- Dashboard CSS (Inter font, KPI cards, hidden Streamlit branding)
- Procfile + runtime.txt deployment pattern
- CLAUDE.md + PROBLEMS.md documentation pattern
- Click CLI structure with similar command names (scrape, extract, export, dashboard)
- SQLite + WAL mode database setup
- Quality scoring formulas (weighted component approach)

---

# 6. DEPENDENCIES & ENVIRONMENT

## Python Dependencies (Union Across All Projects)

### Core (all projects)
- click, rich, pydantic, pyyaml, python-dotenv, pandas, streamlit, plotly, pytest

### HTTP/Scraping
- httpx (AG Tracker, RegScope)
- requests (Pension Fund, School Vote)
- beautifulsoup4, lxml (AG Tracker, Pension Fund, School Vote)
- playwright (School Vote)
- selectolax (AG Tracker, HTML parsing)

### PDF/Document Processing
- pdfplumber (Pension Fund, School Vote)
- pymupdf/fitz (RegScope, School Vote)
- python-docx (RegScope)
- pytesseract, pdf2image (RegScope -- OCR fallback)
- reportlab (Pension Fund, School Vote -- PDF generation)
- openpyxl (Pension Fund, RegScope -- Excel)

### NLP/ML
- sentence-transformers (RegScope)
- torch (RegScope)
- bertopic (RegScope)
- hdbscan (RegScope)
- umap-learn (RegScope)
- transformers (RegScope -- zero-shot classification)
- scikit-learn (RegScope)
- datasketch (RegScope -- MinHash LSH)
- spacy (Pension Fund -- board minutes)
- rapidfuzz (Pension Fund -- entity resolution)
- thefuzz (AG Tracker -- entity resolution)

### Database
- sqlalchemy (AG Tracker, School Vote)
- sqlite3 (all, via stdlib)

### Other
- openai (School Vote -- built but unused; RegScope -- optional topic labels)
- tenacity (School Vote -- retry logic)
- tqdm (School Vote -- progress bars)
- altair (School Vote -- unused/minimal)
- numpy (RegScope, Pension Fund)
- python-dateutil (Pension Fund)

## Environment Variables

| Variable | Project | Required? |
|----------|---------|-----------|
| `REGSCOPE_API_KEY` | RegScope | Yes (Regulations.gov) |
| `OPENAI_API_KEY` | School Vote, RegScope | Optional (unused/topic labels) |
| `PAGEINDEX_API_KEY` | Pension Fund | Yes (for board intelligence) |
| `PAGEINDEX_API_KEY_2` | Pension Fund | Optional (backup) |
| `PAGEINDEX_API_KEY_3` | Pension Fund | Optional (backup) |
| `GITHUB_TOKEN` | School Vote | No (artifact in prompt) |
| `DATABASE_PATH` | School Vote | Optional (default: data/database.sqlite) |
| `SCRAPE_DELAY_SECONDS` | School Vote | Optional (default: 1.5) |

## External Services

| Service | Project | Cost |
|---------|---------|------|
| Regulations.gov API | RegScope | Free (api.data.gov key) |
| Wayback Machine CDX API | AG Tracker | Free |
| BoardDocs public endpoints | School Vote | Free |
| PageIndex API | Pension Fund | Paid |
| OpenAI API | School Vote, RegScope | Pay-per-use (optional) |
| Railway | School Vote, RegScope | Hosting |
| Heroku | AG Tracker, Pension Fund | Hosting |

## OS-Level Dependencies
- Python 3.12.8
- Playwright + Chromium browser (School Vote: `playwright install chromium`)
- Tesseract OCR (RegScope: `brew install tesseract` or `apt install tesseract-ocr`)
- poppler-utils (RegScope: for pdf2image, `brew install poppler`)

---

# 7. DATA SOURCE LANDSCAPE

## AG Enforcement Tracker

| Source | URL | Access | Fragility |
|--------|-----|--------|-----------|
| CA AG | `oag.ca.gov/media/news` | Fully public | Low (stable HTML) |
| NY AG | `ag.ny.gov/press-release` | Via Wayback Machine | Medium (live site blocks) |
| OH AG | `ohioattorneygeneral.gov/Media/News-Releases` | Fully public | Low |
| OR AG | `doj.state.or.us/media-home/news-media-releases/` | Fully public | Low |
| TX AG | `texasattorneygeneral.gov/news/releases` | Fully public | Medium (soft hyphens) |
| WA AG | `atg.wa.gov/news/news-releases` | Direct + Wayback | Low |
| MA AG | `mass.gov/news/ag-*` | Via Wayback Machine | Medium |
| PA AG | `attorneygeneral.gov/taking-action/*` | Via Wayback Machine | Medium |
| VA AG | Joomla-based site | Fully public | High (Joomla-specific) |
| Wayback CDX | `web.archive.org/cdx/search/cdx` | Fully public/free | Low |

## RegScope

| Source | URL | Access | Fragility |
|--------|-----|--------|-----------|
| Regulations.gov API v4 | `api.regulations.gov/v4` | Free API key (registration) | Very low (official API) |
| Comment attachments | Various agency URLs | Public | Low (standard file URLs) |

## Pension Fund Tracker

| Source | URL | Access | Fragility |
|--------|-----|--------|-----------|
| CalPERS | `calpers.ca.gov/.../pep-fund-performance-print` | Fully public | Medium (HTML structure) |
| CalSTRS | `calstrs.com/private-equity-portfolio-performance-table` | Fully public | High (PDF column positions) |
| WSIB | `sib.wa.gov/docs/reports/quarterly/ir063025.pdf` | Fully public | High (PDF column positions, URL changes quarterly) |
| Oregon | Oregon Treasury site | Fully public | High (PDF column positions) |
| NY Common | `osc.ny.gov/.../asset-listing-2025.pdf` | Fully public | High (PDF column positions, URL changes annually) |
| Texas TRS | TRS website | Requires manual download (Incapsula) | Very high |
| Florida SBA | sbafla.com | Blocked (403) | Very high |
| PageIndex API | PageIndex service | Paid API key | Low (stable API) |
| Board meeting PDFs | WSIB + Oregon websites | Fully public | Medium |

## School Board Vote Tracker

| Source | URL | Access | Fragility |
|--------|-----|--------|-----------|
| BoardDocs SEO API | `go.boarddocs.com/{state}/{org}/Board.nsf/BD-GETMeetingsListForSEO` | Fully public, no auth | Low (stable API) |
| BoardDocs meeting pages | `go.boarddocs.com/{state}/{org}/Board.nsf/Public` | Public, requires Playwright | Medium (AJAX-heavy) |
| BoardDocs AJAX endpoints | `BD-GetAgenda`, `BD-GetAgendaItem`, `BD-GetMinutes` | Public, intercepted via browser | Medium |

### Fragility Summary

**Most fragile:** Pension fund PDF adapters (hardcoded pixel column boundaries break when PDF layout changes). Texas TRS and Florida SBA are essentially inaccessible programmatically.

**Least fragile:** Regulations.gov (official versioned API), BoardDocs SEO endpoint (stable public API), Wayback Machine CDX (stable archive service).

**General pattern:** HTML scraping is medium fragility (CSS selectors break on redesign). PDF parsing is high fragility (column positions are brittle). APIs are low fragility (versioned, documented). Wayback Machine is a reliable fallback for blocked live sites.
