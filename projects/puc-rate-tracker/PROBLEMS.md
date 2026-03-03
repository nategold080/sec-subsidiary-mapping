# Problems Tracker — State PUC Rate Case Tracker

## P1: OR PUC "Met Retention" suffix filtering all records — DONE
**Problem:** The OR PUC scraper was filtering out all records containing "Met Retention" in the utility name, removing 777/1029 records. "Met Retention" is a docket retention metadata annotation, not a reason to exclude.
**Fix:** Changed from filtering records to stripping the " - Met Retention" suffix from utility names with `re.sub(r"\s*-\s*Met Retention\s*$", "", utility_name)`.

## P2: Quality scoring too penalizing for docket-level data — DONE
**Problem:** Original quality weights gave 25% to financial data and 10% to documents. Basic docket search results from PUC websites (which provide docket number, utility name, dates, status) could never exceed 0.55, below the 0.6 threshold. Only 39/621 records passed.
**Fix:** Updated quality scoring to match the CLAUDE.md specification with 9 granular components. Records with complete docket-level data now score 0.6+. All 621 records (100%) now above threshold.

## P3: PA/CA/IN/WA PUC sites require JavaScript rendering — DONE (workaround)
**Problem:** Pennsylvania, California, Indiana, and Washington PUC websites use JavaScript-heavy interfaces (Oracle APEX, Angular, React) that return empty or template HTML via plain HTTP requests.
**Workaround:** OR PUC EDOCKETS is accessible and provides 582 real records. Other states use structured reference data based on publicly filed cases. The architecture supports adding live scrapers as PUC interfaces evolve.

## P4: OR PUC [PDF] artifacts in docket numbers — DONE
**Problem:** Some OR PUC docket numbers contained "[PDF]" artifacts from HTML parsing of linked text.
**Fix:** Added `re.sub(r"\[PDF\]", "", docket).strip()` to the parser.

## P5: Cross-state utility identity (Cascade Natural Gas, PacifiCorp) — DONE
**Problem:** Referential integrity check flagged utilities appearing in multiple states as potential issues. However, Cascade Natural Gas (OR, WA) and PacifiCorp (OR, WA) are genuinely multi-state utilities.
**Resolution:** These are correct cross-state entities, not data errors. The entity resolution system properly links them. Documented as expected behavior.

## P6: WA UTC returns 403 Forbidden — DONE (documented)
**Problem:** Washington UTC website (utc.wa.gov) returns 403 Forbidden for all HTTP requests.
**Resolution:** WA UTC may require specific headers, cookies, or has bot protection. Documented as a limitation. Using structured reference data for WA.

## P7: Test failure after quality scoring update — DONE
**Problem:** `test_documents_contribute` test expected documents to increase quality score, but the updated scoring formula replaced the documents component with source_url.
**Fix:** Updated test to `test_source_url_contributes` and fixed component name references in active case test (`has_decision_data` → `has_decision_date`).
