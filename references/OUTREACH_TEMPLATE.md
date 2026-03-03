# Outreach Package Template

## Overview

Every project must have a complete outreach package before being marked client-ready. This document defines what that package looks like and how to build it.

---

## targets.json Schema

Each target entry must include:

```json
{
  "name": "Full Name",
  "title": "Job Title",
  "organization": "Company or Institution Name",
  "email": "email@domain.com or null if not found",
  "linkedin": "Full LinkedIn URL or null",
  "website": "Personal or org website if relevant",
  "category": "potential_client | potential_employer | research_collaborator | media_contact | strategic_partner",
  "subcategory": "More specific label (e.g., 'govtech_saas', 'law_professor', 'edtech_journalist')",
  "relevance": "1-3 sentence explanation of why this person/org is a target for THIS project",
  "priority": "high | medium | low",
  "source": "How you found them (LinkedIn search, company website, paper citation, etc.)",
  "outreach_angle": "Specific angle for reaching out (e.g., 'Their product lacks school board data — we fill the gap')",
  "notes": "Any additional context (mutual connections, recent activity, conference attendance)",
  "status": "not_contacted | queued | contacted | responded | meeting_scheduled | closed"
}
```

---

## Target Minimums Per Project

| Category | Minimum Count | What to Look For |
|----------|--------------|-----------------|
| potential_client | 5 | Companies that sell data in adjacent verticals, compliance/analytics platforms, SaaS companies whose product would be enhanced by this data |
| potential_employer | 3 | Companies hiring for data engineering, product, or research roles where this project demonstrates relevant skills |
| research_collaborator | 3 | Professors who have published papers in related fields, especially at top universities |
| media_contact | 2 | Journalists who cover this domain (govtech, fintech, education policy, etc.) |
| strategic_partner | 2 | Organizations that could distribute or integrate the data (industry associations, nonprofits, data marketplaces) |

**Total minimum: 15 targets per project**

---

## Email Templates

Create templates for each category. Templates should be stored in `outreach/email_templates/` as markdown files.

### Template Structure

**Subject line:** Short, specific, and curiosity-provoking. Never generic.

**Body structure:**
1. **Hook** (1-2 sentences) — Why you're reaching out, specific to THEM
2. **Value prop** (2-3 sentences) — What the dataset is and why it matters
3. **Proof point** (1-2 sentences) — Specific impressive number or insight from the data
4. **Ask** (1 sentence) — What you want (meeting, feedback, collaboration)
5. **Sign-off** — Brief, professional

### Template: Potential Client
```
Subject: [COMPANY] + structured [DOMAIN] data — [SPECIFIC GAP] you don't have yet

Hi [NAME],

I noticed [COMPANY]'s [PRODUCT] covers [WHAT THEY DO] but doesn't yet include [SPECIFIC GAP THIS PROJECT FILLS]. I've built something that might interest you.

I've created [PROJECT NAME] — [ONE SENTENCE DESCRIPTION]. It covers [SCALE: X records across Y sources] with [KEY DIFFERENTIATOR: cross-entity linking, historical depth, etc.].

One finding: [SPECIFIC INTERESTING INSIGHT FROM THE DATA — e.g., "201 defendants appear in enforcement actions across multiple states" or "346 PE funds are independently tracked across 5 pension systems"].

Would you have 15 minutes this week to see a quick demo? I have a live dashboard and sample data ready.

Best,
Nathan Goldberg
nathanmauricegoldberg@gmail.com
[LinkedIn URL]
```

### Template: Research Collaborator
```
Subject: Structured dataset for [THEIR RESEARCH AREA] — [X] records across [Y] sources

Dear Professor [NAME],

I read your [YEAR] paper on [TOPIC] in [JOURNAL/CONFERENCE] and thought you might be interested in a dataset I've built.

[PROJECT NAME] is a structured database of [DESCRIPTION] covering [SCALE]. The data is extracted from public sources using deterministic rule-based methods (no LLM dependency), with quality scoring and full methodology documentation.

I'm the first high school student published in the AAAI Educational Advances track in 20 years (presenting on AI tutoring implementation), and I'm looking for research collaboration opportunities in [RELEVANT FIELD].

Would you be open to a brief conversation about whether this data could support your research? I'm happy to share a sample dataset and methodology document.

Best regards,
Nathan Goldberg
nathanmauricegoldberg@gmail.com
Published: AAAI 2026, Educational Advances in AI
```

### Template: Potential Employer
```
Subject: [DOMAIN] data project — [X] records, zero LLM cost, production-ready

Hi [NAME],

I built [PROJECT NAME] — [ONE SENTENCE] — and I think it demonstrates the kind of data engineering work [COMPANY] does.

The technical highlights: [RECORD COUNT] structured records from [SOURCE COUNT] sources, deterministic extraction pipeline, cross-entity resolution, live Streamlit dashboard, and comprehensive test suite. Zero LLM cost for the core pipeline.

I'm currently exploring opportunities where I can apply this kind of work at scale. Would you be open to a quick conversation?

Best,
Nathan Goldberg
nathanmauricegoldberg@gmail.com
```

### Template: Media Contact
```
Subject: First-ever structured database of [DOMAIN] — [INTERESTING FINDING]

Hi [NAME],

I saw your recent piece on [THEIR ARTICLE TOPIC] and thought you might be interested in a new dataset.

I've built [PROJECT NAME], which is [BRIEF DESCRIPTION OF WHAT MAKES IT NOVEL — e.g., "the first structured database of school board voting records in the United States"]. It covers [SCALE].

One finding that might be newsworthy: [SPECIFIC INTERESTING INSIGHT].

Happy to share the data and methodology if you're interested. The full dataset and live dashboard are available.

Best,
Nathan Goldberg
nathanmauricegoldberg@gmail.com
```

---

## Pitch Materials

### 1-Page Pitch Document (per project)
Store in `outreach/pitch_materials/pitch_one_pager.md`

Structure:
- **Headline:** What this is in one line
- **The Problem:** 2-3 sentences on the data gap
- **The Solution:** 2-3 sentences on what you built
- **By the Numbers:** 4-5 KPIs (record count, source count, dollar value, entity cross-links, etc.)
- **Sample Insight:** One compelling finding from the data
- **Use Cases:** 3-4 bullet points on who uses this and how
- **About:** Brief bio of Nathan with AAAI publication, Gabble, Oak Tree, DebateGuru
- **Contact:** Email, LinkedIn, dashboard URL

### Sample Data Preview (per project)
Store in `outreach/pitch_materials/sample_data.csv`

- 10-20 curated records that show the most interesting/impressive data
- Should demonstrate cross-linking, data quality, and breadth of coverage
- Include a header comment explaining what the columns mean

---

## How to Find Targets

### For Companies/Clients
1. Search Crunchbase, LinkedIn, and Google for companies in the vertical
2. Look at their product pages — what data do they sell/use?
3. Find the gap between what they offer and what you have
4. Identify the right person: VP Data, VP Product, CTO, CEO (smaller companies)
5. Find email: check company website, use pattern (first.last@domain), check LinkedIn

### For Researchers
1. Search Google Scholar for papers in the domain from the last 3 years
2. Filter for authors at top universities (top 50 US, top 20 global)
3. Check their faculty page for current research interests and contact info
4. Prioritize those who have previously used similar datasets or called for better data
5. Email is usually on their faculty page or in their published papers

### For Media
1. Search Google News for recent articles about this domain
2. Identify journalists who cover this beat regularly
3. Check their Twitter/X for engagement with data-driven stories
4. Look for op-eds or investigative pieces that cite data gaps
5. Contact info is often in their bylines or Twitter bios

### For Strategic Partners
1. Search for industry associations, nonprofits, and advocacy groups in the domain
2. Look for open data initiatives or data marketplace platforms
3. Identify organizations that would benefit from the data but aren't direct buyers
4. Find partnership/BD contacts on their websites

---

## Outreach Tracking

Every target starts at `status: "not_contacted"`. Nathan will update statuses as he reaches out. The outreach package should be complete and ready for Nathan to start sending emails immediately upon reviewing a client-ready project.
