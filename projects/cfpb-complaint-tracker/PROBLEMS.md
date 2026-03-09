# PROBLEMS — CFPB Complaint Tracker

Issue tracker for the CFPB Consumer Complaint Cross-Linked Analysis project.

---

## Open Issues

**P1** — Pipeline not yet run — database is empty
The full data pipeline (`python -m src.cli pipeline --full --enriched`) has not been executed against production sources. All tables in `data/cfpb_tracker.db` are empty. All record counts in the dashboard show zero. Being addressed by Agent 1.
Status: NOT DONE

**P2** — Database size may exceed Railway/Heroku deployment limits
The full enriched database (CFPB complaints ~600MB CSV raw + FDIC financials + HMDA + enforcement across four agencies) is expected to reach 10GB+. Railway and Heroku free tiers have storage limits that this may exceed. Mitigation options: deploy a subset DB with only post-2020 complaints, use Railway volume mounts, or use a slimmed deploy DB (`cfpb_tracker_deploy.db`) with complaints truncated to a representative sample.
Status: NOT DONE

**P3** — Four enrichment tables have never been populated against production data
The tables `institution_financials`, `regulatory_enforcement`, `institution_risk_profiles`, and `hmda_institution_summary` were built and tested in unit tests but have never been populated from a live pipeline run. Their schema, storage functions, and scraper modules are complete and tested, but production data quality and volume are unknown.
Status: NOT DONE

---

## Resolved Issues

(none yet)
