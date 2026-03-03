# State Medical Board Disciplinary Actions Tracker

## Research Date: 2026-03-02

## Concept
Aggregate disciplinary actions against physicians and other healthcare providers from state medical boards across all 50 states into a single structured, searchable database. Cross-link with NPI (National Provider Identifier) registry, CMS exclusion lists, and malpractice lawsuit data to create a comprehensive provider accountability tracker.

## Data Gap Assessment: 3/5
The FSMB's Physician Data Center (PDC) is the elephant in the room. It contains disciplinary actions dating back to the 1960s for all actively licensed physicians. DocInfo.org provides FREE public lookup of any individual physician's disciplinary history. However:
- PDC is a lookup tool, not a downloadable database — you can search one doctor at a time
- No bulk download or API is publicly available
- FSMB charges institutions for data licensing agreements
- Public Citizen publishes aggregate RANKINGS of state boards by discipline rates, but not the underlying record-level data
- ProPublica has a doctor investigation tool but it focuses on Medicare billing, not state board actions
- Individual state boards publish actions in wildly different formats (HTML tables, PDFs, newsletters, press releases)
- No free, open, structured cross-state database of disciplinary actions exists

The 3/5 score reflects that DocInfo.org provides the lookup capability (reducing the data gap) even though no bulk structured database exists.

## Source Accessibility (Tested)
1. **California Medical Board** - Tested: redirected to 404. Their enforcement documents page exists but may require JavaScript rendering. Published monthly enforcement action reports as web pages.
2. **State boards generally** - Each state has its own website with varying levels of data accessibility. Some publish monthly action bulletins (CA, NY, TX), others require individual searches. Formats range from HTML tables to PDF newsletters.
3. **FSMB DocInfo** - Free individual lookups but no bulk access. Would need to be scraped doctor-by-doctor (requires NPI or name list as input).
4. **CMS NPPES (NPI Registry)** - Free bulk download available. 7M+ provider records with name, specialty, address.
5. **OIG Exclusion List (LEIE)** - Free downloadable CSV. Providers excluded from federal healthcare programs.

## Cross-Linking Value: 4/5
- Match disciplined physicians across multiple state boards (doctors licensed in multiple states)
- Cross-reference with NPI registry (specialty, practice location)
- Cross-reference with OIG exclusion list (federal exclusion vs. state discipline)
- Cross-reference with CMS Open Payments (industry payments to disciplined physicians)
- Track: Do disciplined doctors in one state get licensed in another?

## Scale: 4/5
- Public Citizen reports ~3,000-4,000 serious disciplinary actions per year across all states
- Historical data going back 10-20 years = 30,000-80,000 records
- 50+ state medical boards as sources
- NPI registry: 7M+ providers for cross-linking

## Specific Buyers

### Potential Clients
1. **Doximity** - Physician networking platform; credential verification data
2. **Definitive Healthcare** - Healthcare commercial intelligence; provider data
3. **Symplr (previously Cactus)** - Credentialing and privileging software for hospitals
4. **Verifiable** - Healthcare credentialing automation startup
5. **Hospital systems** - Direct consumers of credentialing data

### Research Collaborators
1. **Dr. Sidney Wolfe** (Public Citizen Health Research Group) - Publishes annual medical board discipline rankings
2. **Patient safety researchers** at Johns Hopkins, Harvard
3. **State medical board researchers** cited in PMC articles

### Media
1. **KFF Health News** (formerly Kaiser Health News) - Investigative healthcare journalism
2. **ProPublica** - Has investigated doctors extensively

## Technical Feasibility: 2/5
This is the critical weakness:
- 50+ state medical board websites with completely different structures
- Many use JavaScript-heavy frameworks requiring Selenium/Playwright
- Some publish actions as PDFs or image scans
- No standard format for action types (revocation, suspension, probation, reprimand, etc.)
- California's site returned a 404 redirect on basic access test
- Would need to build 50+ custom scrapers
- Some states may require CAPTCHA solving or manual browsing
- Rate limiting concerns across 50 different government sites
- Ongoing maintenance as state sites change

This is dramatically more work than any reference project, which typically had 5-10 sources.

## Credibility Signal: 4/5
Patient safety is a high-profile topic. Medical board accountability is regularly covered by investigative journalists. Academic interest from patient safety researchers. Could lead to meaningful collaborations with Public Citizen or patient advocacy organizations.

## Score Summary
| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 3 | DocInfo provides lookups; no bulk structured DB exists |
| Buyer Clarity | 4 | Named credentialing companies and health systems |
| Technical Feasibility | 2 | 50+ custom scrapers needed; many JS-heavy/PDF sources |
| Cross-Linking Value | 4 | Multi-state tracking + NPI + exclusion lists |
| Scale | 4 | 30,000-80,000 historical records achievable |
| Credibility Signal | 4 | Patient safety is high-profile topic |
| **TOTAL** | **21** | **CONDITIONAL ACCEPT** |

## Risks and Concerns
- Technical feasibility (2/5) is a major red flag — 50 custom scrapers is enormous ongoing maintenance
- FSMB may view this as competing with their paid PDC product and could take action
- Personal health provider data raises privacy sensitivities (though public disciplinary actions are public record)
- Consider starting with 5-10 states that have the most accessible data, not attempting all 50
- Time-to-value is high compared to other ideas
