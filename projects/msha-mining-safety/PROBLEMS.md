# Problems Tracker — MSHA Mining Safety Tracker

## P1 — MSHA blocks Python HTTP libraries (DONE)
MSHA's web server (Microsoft-IIS behind Akamai CDN) returns 403 for requests from httpx/requests. Fixed by using `subprocess.run(["curl", ...])` for downloads.

## P2 — Operator profile build was O(N*M) (DONE)
Original `build_operator_profiles()` ran 13+ individual SQL queries per operator — with 49K+ operators and 8M+ records, this was extremely slow (30+ min). Rewrote to use 5 bulk GROUP BY queries that complete in seconds.

## P3 — Penalties table deduplication (DONE)
CivilPenaltyDocketsDecisions dataset had duplicate docket_no entries. Using INSERT OR IGNORE drops duplicates correctly (477K raw → 93K unique dockets).
