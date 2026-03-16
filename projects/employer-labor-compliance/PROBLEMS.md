# PROBLEMS — Employer Labor Compliance Tracker

## P1: DOL enforcedata.dol.gov migration — DONE
DOL API key obtained. WHD enforcement data (363,365 raw records) successfully
downloaded via v4 API and loaded into database (6,998 unique cases after
filtering to 2015+ and deduplicating by case_id). Cross-linking produced
190,618 links and 529 multi-agency offenders (employers with both WHD and NLRB cases).
OSHA download was started but interrupted; OSHA data pending future completion.

## P2: GROUP_CONCAT DISTINCT syntax — DONE
SQLite bundled with Python 3.12 doesn't support `GROUP_CONCAT(DISTINCT col, sep)`.
Fixed by removing DISTINCT from the NLRB allegation aggregation query.

## P3: NLRB data access — DONE
Initially planned to use NLRB.gov API pagination. Research found that
labordata/nlrb-data provides a nightly-refreshed SQLite database (951MB)
with 5.9M records across 12 tables. Updated scraper to use bulk download.
