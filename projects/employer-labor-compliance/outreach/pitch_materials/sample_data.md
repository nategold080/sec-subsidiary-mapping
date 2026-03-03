# Sample Data Preview — Employer Labor Compliance Tracker

## Top 10 Employers by NLRB Case Volume (2015–Present)

| Rank | Employer | NLRB Cases | States Active | Primary Case Types |
|------|----------|-----------|---------------|-------------------|
| 1 | United States Postal Service | 24,055 | 50+ | C (ULP charges) |
| 2 | United Parcel Service | 2,600+ | 48 | C, CA (employer ULP) |
| 3 | Starbucks Corporation | 2,200+ | 42 | CA (employer ULP), RC (union petition) |
| 4 | AT&T Inc. | 958 | 35 | C, CA, CB (union ULP) |
| 5 | Amazon.com Services | 395 | 30 | CA, RC |
| 6 | Kroger Company | 380+ | 28 | C, CA, CB |
| 7 | General Motors | 350+ | 25 | C, CA |
| 8 | FedEx Corporation | 340+ | 40 | C, CA |
| 9 | Walmart Inc. | 310+ | 38 | CA, RC |
| 10 | McDonald's USA | 290+ | 35 | CA (joint employer) |

## Sample Employer Profile

```json
{
  "employer_name": "STARBUCKS",
  "normalized_name": "STARBUCKS",
  "agencies": ["NLRB"],
  "total_cases": 2200,
  "nlrb_cases": 2200,
  "case_types": ["CA", "RC", "CD"],
  "states_active": ["WA", "NY", "CA", "IL", "TX", "PA", "OH", "MA", "FL", "..."],
  "date_range": "2015-01-05 to 2025-12-31",
  "compliance_risk_score": 0.72,
  "quality_avg": 0.98
}
```

## NLRB Case Type Distribution

| Case Type | Count | Description |
|-----------|-------|-------------|
| CA | 98,000+ | Employer unfair labor practice charges |
| CB | 45,000+ | Union unfair labor practice charges |
| C | 35,000+ | General ULP charges |
| RC | 22,000+ | Union representation petitions (filed by union) |
| CC | 12,000+ | Union restraint/coercion charges |
| RD | 5,000+ | Decertification petitions |
| CD | 3,000+ | Jurisdictional dispute charges |
| RM | 2,500+ | Representation petitions (filed by employer) |

## Geographic Distribution (Top 10 States)

| State | Cases | % of Total |
|-------|-------|-----------|
| CA | 22,000+ | 9.4% |
| NY | 18,000+ | 7.7% |
| TX | 14,000+ | 6.0% |
| FL | 12,000+ | 5.1% |
| IL | 11,000+ | 4.7% |
| PA | 10,000+ | 4.3% |
| OH | 9,000+ | 3.9% |
| NJ | 8,500+ | 3.6% |
| MI | 7,500+ | 3.2% |
| WA | 7,000+ | 3.0% |

---

*Full dataset includes 233,011 NLRB cases across 91,656 employers. OSHA and WHD data to be added in Phase 2.*

*Nathan Goldberg — nathanmauricegoldberg@gmail.com*
