# Problems Tracker — CPSC Product Safety Tracker

## P1: SaferProducts CSV disclaimer row before header — DONE
The incidents CSV starts with a disclaimer line before the actual column headers. Parser now scans for the header row starting with "Report No" before initializing the DictReader.

## P2: DictReader None key with extra CSV values — DONE
When CSV rows have more values than headers, DictReader stores extras under a None key as a list. Fixed by skipping None keys and handling list values via str join.

## P3: Import violations Excel URL changes with date — DONE
The CPSC NOV data file URL includes a date stamp that changes. Parser tries multiple URL patterns and caches the download. Currently using 2026-02-19 version with 39,261 records across 6 sheets. 13,902 unique after dedup.

## P4: Manufacturer names in recalls include location suffix — OPEN
Many recall API records include the manufacturer's city/state in the name field (e.g., "Polaris Industries Inc., of Medina, Minn."). The normalization strips punctuation and legal suffixes but the location text persists, leading to duplicate profiles for same manufacturer with different location text.

## P5: NEISS product codes not resolved to names — OPEN
NEISS records use numeric product codes (e.g., 1234 for "Knives") but the product code reference table is not populated from the CPSC Comparability Table PDF. Would need to parse the PDF or find a machine-readable version of the product code list.

## P6: Country names in import violations not standardized — OPEN
Import violations have inconsistent country names (e.g., "China" vs "CHINA" vs "china"). Could normalize to uppercase but some entries have non-standard formats. Minor impact on analysis since most are clearly identifiable.
