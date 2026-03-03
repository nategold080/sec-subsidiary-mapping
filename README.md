# Data Factory

Autonomous data project generation system powered by Claude Code.

## Setup

1. Place your four existing project folders in `references/existing_projects/`
2. Open this folder in Claude Code with "dangerously skip permissions" enabled and agent team creation enabled
3. Copy the contents of `LAUNCH_PROMPT.md` as your first message
4. Monitor `state/alerts.json` for client-ready notifications and human-input-needed flags

## Structure

```
data-factory/
├── CLAUDE.md                    ← Master instructions (Claude Code reads this automatically)
├── LAUNCH_PROMPT.md             ← What to paste as your first message
├── references/
│   ├── PROJECT_ANALYSIS.md      ← Technical breakdown of your 4 existing projects
│   ├── EVALUATION_CRITERIA.md   ← Scoring rubric for new project ideas
│   ├── OUTREACH_TEMPLATE.md     ← Template for outreach packages
│   └── existing_projects/       ← Your 4 project folders (you add these)
├── templates/
│   ├── project_scaffold/        ← Standard files for new projects
│   └── outreach_scaffold/       ← Standard files for outreach packages
├── state/
│   ├── projects.json            ← Active project tracker
│   ├── research_queue.json      ← Ideas being evaluated
│   └── alerts.json              ← Notifications for Nathan
└── projects/                    ← Where new projects are built
```

## Monitoring

Check `state/alerts.json` periodically. Alerts with type:
- `client-ready` — A project is complete and ready for your review
- `needs-human` — Claude Code needs your input (API key, approval, strategic decision)
- `blocked` — Something is preventing progress
- `milestone` — Notable progress update
