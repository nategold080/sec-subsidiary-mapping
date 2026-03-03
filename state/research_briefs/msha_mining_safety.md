# MSHA Mining Safety & Enforcement Tracker — Research Brief

## Score: 24/30

| Criterion | Score | Notes |
|-----------|-------|-------|
| Data Gap Reality | 4/5 | 20+ bulk datasets, no cross-linked product exists |
| Buyer Clarity | 4/5 | Mining companies, ESG investors, UMWA, env groups, law firms |
| Technical Feasibility | 5/5 | All datasets free bulk downloads, pipe-delimited, no auth |
| Cross-Linking Value | 5/5 | MINE_ID links all sources; operator profiles aggregate violations+inspections+accidents+penalties |
| Scale Demonstration | 3/3 | 8M+ records from 6+ core datasets |
| Credibility Signal | 2/2 | Mining safety politically relevant, labor/environmental angle |

## Data Sources Confirmed

All downloadable from: `https://arlweb.msha.gov/OpenGovernmentData/DataSets/`

| Dataset | Records | Format | Coverage |
|---------|---------|--------|----------|
| Mines | 91,587 | Pipe-delimited ZIP | Since 1970 |
| Accidents/Injuries | 271,621 | Pipe-delimited ZIP | Since 2000 |
| Inspections | 1,137,929 | Pipe-delimited ZIP | Since 2000 |
| Violations | 3,055,941 | Pipe-delimited ZIP | Since 2000 |
| Assessed Violations | 2,989,669 | Pipe-delimited ZIP | Since 2000 |
| Civil Penalty Dockets | 477,094 | Pipe-delimited ZIP | Since 2000 |
| Employment/Production | TBD | Pipe-delimited ZIP | Since 2000 |
| Controller/Operator History | TBD | Pipe-delimited ZIP | Historical |
| Orders Issued (107a) | TBD | Pipe-delimited ZIP | Since 2000 |
| **Total Core** | **~8M+** | | |

## Key Numbers
- $1.8 billion in proposed penalties
- 1,194 fatalities
- 2,456 permanent disabilities
- 91,587 mines (since 1970)

## Cross-Linking Strategy
- **MINE_ID** is the universal foreign key across ALL datasets
- **OPERATOR_ID** and **CONTROLLER_ID** link to operator/controller profiles
- Mines → Inspections → Violations → Assessed Violations → Penalties → Accidents
- Operator profiles aggregate across all mines they operate
- Controller (parent company) profiles show portfolio-wide safety performance

## Competition
- MSHA's own Enforcement Data 2.5 tool is a basic search interface — not a structured product
- Pipeline Safety Trust has some mining data dashboards but limited
- Good Jobs First Violation Tracker includes some MSHA data but not cross-linked
- No product connects mines → inspections → violations → penalties → accidents → operator profiles

## Target Buyers
1. **Mining companies** — Safety benchmarking, compliance audit, due diligence
2. **ESG investors/ratings** — MSCI, Sustainalytics, ISS ESG need mine safety data
3. **UMWA (United Mine Workers of America)** — Safety advocacy, bargaining data
4. **Environmental groups** — Earthjustice, Sierra Club mining campaigns
5. **Law firms** — Personal injury, environmental litigation, regulatory defense
6. **Insurance/reinsurance** — Mining liability risk assessment
7. **State mine safety agencies** — Benchmarking against federal data
8. **Academic researchers** — Occupational safety, environmental health

## Recommendation
STRONG ACCEPT. Highest-scale dataset of any project so far (8M+ records). All data freely downloadable with no auth barriers. Universal MINE_ID key makes cross-linking straightforward. Rich penalty, injury, and inspection data supports multiple buyer categories.
