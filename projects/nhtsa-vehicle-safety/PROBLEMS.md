# Problems Tracker — NHTSA Vehicle Safety Defect Tracker

## P1: Investigation flat file column mapping was wrong — DONE
My initial column mapping assumed nhtsa_id in col 1, but actual format has make in col 1, model in col 2, year in col 3, components in col 4, manufacturer in col 5. Fixed parser to correct mapping.

## P2: Tesla, Inc. normalization — DONE
normalize_make regex didn't handle comma before "Inc." suffix. Added optional comma to regex pattern.

## P3: Cross-linker component matching — DONE
NHTSA uses hierarchical components like "WHEELS:LUGS/NUTS/BOLTS/STUDS". Original set intersection on comma-split couldn't match. Fixed with prefix matching: "WHEELS" now matches "WHEELS:LUGS/NUTS/BOLTS/STUDS".

## P4: Recall flat files return 404 — DONE
FLAT_RCL.zip and FLAT_TSBS.zip URLs return 404. Switched to JSON API per make/model/year.
Fetched all 33 major makes × 12 years (396 queries), yielding 2,955 recall campaigns.

## P5: Investigation dedup reduces 153K rows to 5,326 — DONE
Flat file has one row per investigation-make-model combination (many-to-many). SQLite PK on
investigation_number deduplicates to unique investigations. This is correct behavior —
the vehicles table preserves the make/model associations. Accepted as design decision.

## P6: FCA US LLC normalization — DONE
After regex strips "LLC" suffix, "FCA US" didn't match alias map entry "FCA US LLC" → "CHRYSLER". Added "FCA US" as explicit alias.

## P7: Regulations.gov API key needed for investigation dockets — OPEN
Enrichment 3 (investigation docket narratives) requires a free API key from Regulations.gov.
Register at: https://open.gsa.gov/api/regulationsgov/
Then set REGULATIONS_GOV_API_KEY environment variable or add to config/api_keys.yaml.
Scraper, schema, dashboard tab, and tests are all built — just needs the key to run.

## P8: Vehicle attribute body classification defaults to Sedan/Car — DONE
Rule-based classification with hardcoded model name sets covers ~95% of popular models.
For uncommon models, body classification defaults to "Sedan/Car". VPIC API fetch provides
better classification for API-enriched vehicles. 11,088 vehicles enriched with attributes.
