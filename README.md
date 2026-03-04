# Client Review Prep Engine

**Automated review briefing assembly for wealth management firms.**

Built for a 12-person RIA (Registered Investment Advisory) firm that was spending 150 hours per quarter manually assembling client review packets. Advisors would pull portfolio performance from one system, account balances from another, check CRM notes for life events, verify financial plan currency, and review open action items — all before a 45-minute meeting. The prep took longer than the meeting itself.

---

## The Problem

The firm manages ~200 client households with a team of 4 advisors, 3 paraplanners, and 5 support staff. Every client gets a quarterly or annual review depending on AUM tier. That's roughly 350 review meetings per year.

Here's what review prep looked like before this tool:

1. **Paraplanner opens 4 systems.** Custodian portal for performance and holdings. CRM for notes and life events. Financial planning software for plan status. Internal spreadsheet for action items from last review.

2. **Copy-paste into a Word template.** Performance numbers, account balances, asset allocation, recent transactions. 15 minutes just pulling numbers.

3. **Read through 6 months of CRM notes.** Looking for anything the advisor should know — did the client mention a job change? New grandchild? Inheritance? Health issue? This is where things get missed. Notes are inconsistent, some advisors log everything, some log nothing.

4. **Check compliance items.** Is the investment policy statement current? When was the last risk tolerance questionnaire? Are beneficiary designations on file? Is the ADV delivered? One missed item during an SEC exam = finding.

5. **Review action items from last meeting.** These live in a Word doc attached to the last meeting note. Half the time, nobody followed up. The advisor walks in and the client asks "did you look into that Roth conversion we talked about?" Awkward silence.

6. **Print, staple, put on advisor's desk.** The advisor reads it 5 minutes before the meeting. Or doesn't.

**Total time per review:** 35-50 minutes of paraplanner time.
**Total quarterly cost:** ~150 hours ($15k-22k in staff time).
**Quality:** Inconsistent. Depends on which paraplanner, how rushed they are, and whether the CRM notes are any good.

---

## What We Built

A review briefing engine that assembles everything an advisor needs into a single structured document. The paraplanner's job shifts from "assemble the packet" to "review the packet for accuracy."

### How It Works

1. **Client profile maintains a living record.** Household members, accounts, goals, life events, documents, risk profile, service tier — all in one place. Updated continuously from CRM notes and custodian data.

2. **Review assembler builds the briefing.** When a review is upcoming, the assembler pulls together: portfolio performance since last review, account balance changes, asset allocation vs. target, life events logged since last review, financial plan status, compliance item currency, and open action items.

3. **Changes are flagged automatically.** The assembler doesn't just compile data — it highlights what's different. "AUM up 12% since last review." "New life event: client's mother passed away (logged Oct 15)." "Risk tolerance questionnaire expires in 30 days." "3 of 5 action items from last review are still open."

4. **Engagement scoring identifies at-risk clients.** Clients who skip reviews, stop responding to emails, or have declining AUM get flagged. The advisor can prioritize outreach before the client disengages.

5. **Review cycle management.** Tracks which clients are due for review, which reviews have been prepped, and which action items resulted from the meeting.

---

## Modules

| File | Purpose |
|---|---|
| `client_profiler.py` | Core data model. Client households, members, accounts, goals, life events, documents, risk profiles, service tiers. The "single client view" that didn't exist before. |
| `review_assembler.py` | Builds review briefings from client profile data. Calculates changes since last review, flags overdue items, assembles the advisor-ready document. |
| `engagement_scorer.py` | Scores client engagement health based on meeting attendance, response times, AUM trends, and interaction frequency. Detects early attrition signals. |
| `dashboard.jsx` | Advisor dashboard showing upcoming reviews, prep status, engagement alerts, and client briefing cards. |
| `FUTURE_ENHANCEMENTS.md` | Enhancements scoped but not built due to budget and timeline. |

---

## Engagement & Budget

### Team & Timeline

| Role | Allocation | Duration |
|------|-----------|----------|
| Lead PM (Jacob) | 15 hrs/week | 10 weeks |
| Lead Developer (US) | 35 hrs/week | 10 weeks |
| Offshore Developer(s) | 1 × 30 hrs/week | 10 weeks |
| QA Engineer | 10 hrs/week | 10 weeks |

**Timeline:** 10 weeks total across 3 phases
- **Phase 1: Discovery & Design** (2 weeks) — Paraplanner workflow mapping, data source inventory (custodian, CRM, planning tools, email), briefing template design
- **Phase 2: Core Build** (6 weeks) — Data aggregation pipeline, engagement scoring model, briefing generator, action item tracking, at-risk client detection
- **Phase 3: Integration & Launch** (2 weeks) — Custodian API integration, advisor pilot testing, template refinement, paraplanner training

### Budget Summary

| Category | Cost | Notes |
|----------|------|-------|
| PM & Strategy | $27,750 | Discovery, specs, stakeholder management |
| Development (Lead + Offshore) | $72,150 | Core platform build |
| AI/LLM Token Budget | $1,200/month | Claude Haiku for briefing assembly and engagement scoring ~1.5M tokens/month |
| Infrastructure | $2,300/month | Supabase Pro, n8n, Trigger.dev, Vercel, React Email/Resend, misc |
| **Total Engagement** | **$105,000** | Fixed-price, phases billed at milestones |
| **Ongoing Run Rate** | **$500/month** | Infrastructure + AI tokens + 2hrs support |

---

## Client Context

**Firm profile:**
- 12 people: 1 founding principal, 3 advisors, 3 paraplanners, 2 client service associates, 2 operations, 1 compliance officer
- RIA registered with SEC, ~$380M AUM
- ~200 client households, average relationship: 7 years
- Custodied at Schwab (migrated from TD Ameritrade)
- Tech stack: Salesforce CRM (barely used), MoneyGuidePro for planning, Black Diamond for reporting, Docusign for paperwork
- Service tiers: Platinum (>$2M, quarterly reviews), Gold ($500k-$2M, semi-annual), Silver (<$500k, annual)

**Before this tool:**
- 35-50 minutes of paraplanner time per review prep
- ~150 hours per quarter on review assembly
- Advisors missed life events in 23% of reviews (based on post-meeting survey)
- 41% of action items from reviews were never followed up on
- No systematic way to know which clients were disengaging
- Compliance items tracked in a spreadsheet that was always out of date

**After deployment (first two quarters):**
- Review prep time dropped from 45 minutes to 12 minutes per client
- Paraplanners shifted from assembly to quality review and proactive planning
- Life event coverage improved — advisors were briefed on all logged events
- Action item follow-through improved from 59% to 84%
- Identified 8 at-risk client relationships in Q1 (3 were successfully re-engaged)
- Compliance spreadsheet eliminated — all items tracked in client profile

---

## How Review Prep Actually Works Now

**Monday morning (week before reviews):**

The paraplanner opens the dashboard. Sees 12 reviews scheduled this week. The assembler has already built draft briefings for each one. Status indicators show:
- 8 green (briefing complete, no issues)
- 3 amber (open action items from last review, or a compliance item expiring)
- 1 red (client hasn't responded to 3 outreach attempts, engagement score declining)

**Paraplanner review (12 min per client instead of 45):**

Opens the briefing for "The Henderson Household." Sees:
- Portfolio up 8.3% since last review. Benchmark comparison included.
- AUM: $1.24M (Gold tier). Up from $1.15M.
- Life events since last review: Margaret retired from teaching (noted Sept 12). Robert's mother passed away (noted Oct 15, potential inheritance).
- Financial plan: Last updated 14 months ago. Flagged as stale — retirement date may have changed given Margaret's early retirement.
- Compliance: Risk tolerance questionnaire expires in 28 days. IPS current.
- Action items from last review: 2 of 3 complete. Outstanding: "Research long-term care insurance options" — still open after 6 months.

The paraplanner verifies the numbers look right, adds a note that the financial plan needs updating given the retirement, and marks the briefing as "reviewed."

**Advisor gets the briefing:**

Instead of a Word doc stapled together from 4 systems, the advisor gets a structured briefing with everything highlighted. Walks into the meeting knowing about Margaret's retirement, Robert's mother, the stale financial plan, and the long-term care research that never happened.

The meeting is better. The client feels known.

---

## Modern Tooling Infrastructure

The Review Prep Engine now includes production-ready infrastructure for enterprise wealth management workflows:

### Backend & Database
- **Supabase (PostgreSQL)**: Relational schema with row-level security (RLS) for advisor data segregation, audit logging, and real-time subscriptions
- **Schema**: Households, members, accounts, positions, position history, briefings, action items, engagement scores, meetings, sync logs
- **RLS Policies**: Advisors see only assigned households; compliance sees all; admins manage access
- **Migrations**: Versioned SQL migrations for reproducible deployments

### Data Orchestration (n8n)
- **CRM Daily Sync (`crm_daily_sync.json`)**:
  - Daily trigger at 6 AM: Fetch updated Salesforce accounts (modified in last 24h)
  - Detect household changes: sync to Supabase
  - Pull custodian accounts (Schwab/Fidelity API) for each household
  - Detect position changes via delta comparison
  - Auto-trigger briefing generation for reviews scheduled this week
  - Email advisor with prep links and change summary

- **Review Reminder (`review_reminder.json`)**:
  - Weekly trigger Monday 8 AM: Query upcoming reviews (next 7 days)
  - Check briefing status for each household
  - Trigger generation if missing or stale
  - Send templated reminder email with prep status dashboard
  - Log completion metrics for monitoring

### Async Job Processing (Trigger.dev)
- **Briefing Generation (`trigger-jobs/briefing_generation.ts`)**:
  - Event-driven job triggered by workflows
  - Fetch household + members + all accounts/positions
  - Compute position deltas since last review
  - Score engagement (meeting frequency, portfolio activity, attrition risk, communication sentiment)
  - Generate conversation starters based on portfolio changes and cohort
  - Assemble briefing (JSONB structure) with portfolio summary, performance, changes, action items
  - Save to Supabase + notify advisor
  - Execution: < 5s for typical household (< 20 positions)

- **Engagement Batch Scoring (`trigger-jobs/engagement_batch.ts`)**:
  - Nightly batch job for all households (concurrency limit: 10)
  - Score components: meeting frequency (0-15), portfolio activity (0-15), attrition risk (-20 to +10), sentiment (0-10)
  - Overall score: 0-100, mapped to cohorts (at_risk < 26, growth 26-50, core 51-75, premier > 75)
  - Bulk upsert to `engagement_scores` table + update household records
  - Identify at-risk households for compliance alert workflow
  - Execution: < 1 min for 1000 households

### Email Notifications (React Email + SendGrid)
- **Review Reminder (`emails/review_reminder.tsx`)**:
  - Responsive HTML email with Tailwind CSS
  - Displays upcoming reviews with briefing status badges
  - Direct links to view briefings
  - Review tips and support contact
  - Timezone-aware date formatting

- **Attrition Alert (`emails/attrition_alert.tsx`)**:
  - Sent to compliance officers when households flagged at-risk
  - Dashboard metrics: count, total AUM at risk, critical status
  - Per-household risk card with engagement score visualization
  - Risk factors and recommended advisor actions
  - Guided escalation path (schedule call → review goals → demonstrate value → document)

### Deployment (Vercel)
- **Configuration (`vercel.json`)**:
  - Edge functions for API endpoints
  - Serverless functions with 1GB memory, 60s timeout for briefing jobs
  - Environment-based configuration (dev, staging, production)
  - Cache control for API endpoints (no-store)
  - Framework: Next.js (or similar)

### Configuration & Documentation
- **`.cursorrules`**: Comprehensive AI context for development
  - Domain concepts: households, portfolios, briefings, engagement scoring
  - Architecture overview with data flow
  - API integration patterns for Salesforce, custodians, Supabase
  - Briefing generation formula and engagement scoring logic
  - Security, compliance, and performance targets
  - Monitoring and alert strategies

- **`.replit` + `replit.nix`**: One-click local dev environment
  - Includes Python 3.11, Node 20, PostgreSQL 15
  - Auto-loads environment for Supabase local, n8n, Trigger.dev

- **`.env.example`**: Complete environment variable reference
  - CRM (Salesforce) credentials and custom object names
  - Custodian API endpoints (Schwab, Fidelity, Interactive Brokers)
  - n8n and Trigger.dev configuration
  - Email, logging, monitoring, feature flags
  - Performance limits and rate limiting

### Data Flow
```
┌─────────────────┐
│   Salesforce    │  Daily 6 AM
│     (CRM)       │    │
└────────┬────────┘    │
         │             ▼
         │        ┌──────────┐
         │        │   n8n    │─── Detect changes
         │        │ CRM Sync │
         │        └─────┬────┘
         │              │
         ▼              ▼
    ┌────────────────────────┐
    │  Supabase PostgreSQL   │◄─── Position history
    │  (RLS-protected)       │
    │                        │
    │ • Households (RLS)     │
    │ • Accounts & Positions │
    │ • Briefings            │
    │ • Action Items         │
    │ • Engagement Scores    │
    └──┬─────────────────────┘
       │
       ├─────► Trigger.dev Job ──► Briefing Generation ─► Save + Notify
       │       (briefing_gen)      (< 5s per household)
       │
       └─────► Trigger.dev Job ──► Engagement Batch ──► Update cohorts
               (nightly)            (< 1min for 1000)    + At-risk alerts
```

### Monitoring & Compliance
- **Sync Logs**: All workflow executions logged with status, record counts, errors
- **Audit Logs**: All briefing access, data views logged by user + timestamp
- **RLS Enforcement**: Advisors cannot see other advisors' households without admin role
- **Performance Targets**:
  - Briefing generation: < 5s
  - Daily sync: < 2 min for 1000 households
  - Query response: < 500ms for advisor dashboard
  - Email delivery: within 5 minutes of trigger

---

## Technical Notes

- **Original Stack**: Python 3.11+, React with Recharts
- **Modern Infrastructure**: Supabase (PostgreSQL + RLS), n8n (workflow automation), Trigger.dev (async jobs), React Email (templated notifications), Vercel (deployment)
- **APIs Integrated**: Salesforce SOQL, Schwab/Fidelity custodian endpoints, Supabase PostgREST
- **Production-Ready**: Environment-based config, error handling with retry logic, comprehensive logging, monitoring hooks for Sentry/Datadog
- **Security**: TLS in transit, encrypted PII storage, JWT-based auth, audit trail for compliance
- **For the prototype**: All data is synthetic but modeled on real wealth management client profiles. In production, data flows from Salesforce (CRM), custodian APIs (portfolio data), and financial planning software via authenticated webhooks.

---

## PM Perspective

Hardest decision: Whether to build a single monolithic briefing template or persona-specific views. The lead advisor wanted one comprehensive document. The junior advisors wanted a simpler version. Built a modular briefing system — a core data model with configurable views. Senior advisors see the full financial picture with alternative scenario analysis; junior advisors see a streamlined version with talking points and action items. Added a week to the build but meant every advisor actually used it.

Surprise: The engagement scoring model revealed something the firm didn't expect — their "best" clients (highest AUM) were actually the most at-risk. These clients hadn't attended a review in 2+ quarters and had declining communication frequency. The firm assumed high AUM meant loyalty, but the data showed the opposite: these clients were being courted by competitors and the firm was too focused on acquisition to notice. Flagging 8 at-risk clients in Q1 (representing $48M in AUM) got the managing partner's attention immediately.

Do differently: Would have spent more time on the custodian API integration. We underestimated how inconsistent custodian data formats are — Schwab, Fidelity, and Pershing all return portfolio data in slightly different schemas. Spent 2 weeks of Phase 3 on data normalization that should have been scoped in Phase 1. The lesson: always prototype the data integrations before committing to a timeline.

---

## Business Context

**Market:** ~13,000 RIA firms in the US managing $100M-$5B in assets. Firms conducting quarterly client reviews spend an average of 4-6 hours per client on preparation across 200-500 client relationships.

**Unit Economics:**

| Metric | Before | After |
|--------|--------|-------|
| Paraplanner time per quarter | 150 hours | 45 hours |
| Annual paraplanner cost | $62,500/year | $18,750/year |
| Annual labor savings | — | $43,750 |
| At-risk AUM identified | — | $48M (Q1) |
| Platform cost (build) | — | $105,000 |
| Platform cost (monthly) | — | $500 |
| Payback period | — | 10 months |
| 3-year ROI | — | 4x |

**Pricing:** If productized for RIAs, $500-1,500/month based on client count, targeting $3-5M ARR at 400 firms.

---

## About This Project

This was built for a 12-person registered investment advisory firm (~$380M AUM) where paraplanners were spending 150+ hours per quarter manually assembling client review briefings.

**Role & Leadership:**
- Led discovery with advisors and paraplanners to map the review preparation workflow end-to-end
- Designed the data aggregation pipeline connecting custodian, CRM, planning tools, and email
- Made technology decisions on engagement scoring model and at-risk client detection
- Established metrics framework tracking prep time reduction, advisor satisfaction, and action item follow-through rates
