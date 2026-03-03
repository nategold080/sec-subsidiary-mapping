# PROBLEMS — Employer Labor Compliance Tracker

## P1: DOL enforcedata.dol.gov migration — OPEN
DOL has migrated from enforcedata.dol.gov to data.dol.gov (JavaScript SPA).
The old bulk CSV download URLs for WHD and OSHA data now return redirects.
The new v4 API at apiprod.dol.gov/v4 requires a free API key and doesn't
yet list WHD or OSHA datasets (only 10 datasets are live, all ILAB/WB/MSHA).
- **Impact**: Cannot programmatically download WHD or OSHA bulk data
- **Workaround**: Manual download through data.dol.gov portal, or wait for v4 API
- **Action needed**: Register for free API key at dataportal.dol.gov/api-keys

## P2: GROUP_CONCAT DISTINCT syntax — DONE
SQLite bundled with Python 3.12 doesn't support `GROUP_CONCAT(DISTINCT col, sep)`.
Fixed by removing DISTINCT from the NLRB allegation aggregation query.

## P3: NLRB data access — DONE
Initially planned to use NLRB.gov API pagination. Research found that
labordata/nlrb-data provides a nightly-refreshed SQLite database (951MB)
with 5.9M records across 12 tables. Updated scraper to use bulk download.
