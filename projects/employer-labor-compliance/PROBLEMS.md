# PROBLEMS — Employer Labor Compliance Tracker

## P1: DOL enforcedata.dol.gov migration — OPEN (needs human)
DOL has migrated from enforcedata.dol.gov to data.dol.gov (JavaScript SPA).
The old bulk CSV download URLs for WHD and OSHA data now return 301 redirects.
Research confirmed both datasets ARE available on the v4 API:
- **WHD Enforcement** (Dataset ID 10246): `apiprod.dol.gov/v4/get/WHD/enforcement/json`
  - 110 columns, concluded compliance actions since FY 2005, updated quarterly
  - Fields: case_id, trade_nm, legal_name, address, violations by statute (FLSA, SCA, H1B, FMLA, etc.)
- **OSHA Inspection** (Dataset ID 10313): `apiprod.dol.gov/v4/get/OSHA/inspection/json`
  - 36 columns, updated daily
  - Additional tables: Violation (10317), Accident (10310), Accident Injury (10312)
- **Action needed**: Register for free API key at `dataportal.dol.gov/registration`
- **Impact**: NLRB-only Phase 1 shipped. WHD + OSHA data for Phase 2 once key obtained.

## P2: GROUP_CONCAT DISTINCT syntax — DONE
SQLite bundled with Python 3.12 doesn't support `GROUP_CONCAT(DISTINCT col, sep)`.
Fixed by removing DISTINCT from the NLRB allegation aggregation query.

## P3: NLRB data access — DONE
Initially planned to use NLRB.gov API pagination. Research found that
labordata/nlrb-data provides a nightly-refreshed SQLite database (951MB)
with 5.9M records across 12 tables. Updated scraper to use bulk download.
