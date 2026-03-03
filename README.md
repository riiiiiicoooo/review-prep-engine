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

## Technical Notes

- Python 3.11+, React with Recharts
- No external dependencies beyond standard library
- In production, data would be pulled via APIs from Salesforce (CRM), Black Diamond (portfolio data), and MoneyGuidePro (financial plans)
- For the prototype, all data is synthetic but modeled on real wealth management client profiles
- Engagement scoring uses a weighted composite of 6 signals, calibrated against the firm's historical attrition data

---

## What This Demonstrates

- **Understanding a domain deeply enough to identify non-obvious automation** — review prep isn't a "product" anyone would think to build. It's an operational bottleneck that firms accept as the cost of doing business. Quantifying it (150 hours/quarter, $22k) makes the case.
- **Designing for the actual workflow** — the tool doesn't replace the paraplanner, it changes their job from assembly to review. That's important for adoption. Nobody loses their job; everyone's work gets better.
- **Multi-source data aggregation** — the core product challenge is normalizing data from 4 different systems with different schemas, update frequencies, and reliability levels into a single coherent view.
- **Engagement scoring as a retention tool** — this wasn't in the original scope. We added it after noticing the firm had lost 3 clients in Q4 with no warning. The data to predict attrition was there; nobody was looking at it.
