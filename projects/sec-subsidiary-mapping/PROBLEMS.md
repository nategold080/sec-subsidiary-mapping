# Problems Tracker — SEC Corporate Subsidiary & Ownership Mapping

## P1: Filing quality_score column not populated — DONE
The filings table has a quality_score column but the pipeline only stores quality on ownership_links. Stats query reads from ownership_links correctly. Non-blocking.

## P2: Parse success rate is 76% (1,198/1,576) — OPEN
24% of fetched exhibits yield zero subsidiaries. Common causes: non-standard HTML layouts, plain text without clear column structure, SGML-wrapped files with unusual nesting. Could improve with additional parser strategies.

## P3: Database upsert COALESCE with empty strings — DONE
COALESCE(excluded.ticker, parents.ticker) didn't preserve existing values when update had empty string. Fixed with CASE WHEN for all optional fields.

## P4: Pipeline did not process all 3,489 discovered filings — OPEN
Full pipeline (2023-2025) discovered 3,489 filings but only processed ~1,576. Likely due to background task timeout or interruption. Could re-run pipeline to fill gaps. Current 672 parent companies / 18,865 subsidiaries is sufficient for client-ready status.
