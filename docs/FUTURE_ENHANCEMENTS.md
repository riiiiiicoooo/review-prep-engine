# Future Enhancements

Enhancements scoped during the engagement but not built. The firm had a $20k budget and 6-week timeline. We prioritized the review assembler (immediate time savings), engagement scoring (retention risk was urgent after losing 3 clients), and the advisor dashboard (adoption vehicle). Everything below is Phase 2.

Ordered by estimated impact, not complexity.

---

## 1. Custodian API Integration (Schwab)

**What:** Direct API connection to Schwab's advisor portal to pull account balances, holdings, performance, and transaction history automatically.

**Why we didn't build it:** Schwab's RIA API requires a registered developer account and a compliance review. The approval process takes 4-8 weeks. We scoped CSV import as the interim solution — the operations manager exports a report weekly and drops it in a shared folder.

**What it would do:**
- Nightly sync of account balances, positions, and transactions
- Automatic performance calculation (no manual number-pulling from Black Diamond)
- Real-time AUM tracking for engagement scoring
- Transaction alerts (large withdrawals, external transfers) as early attrition signals

**Estimated effort:** 4-6 weeks (mostly Schwab API approval + OAuth integration)

**Impact:** Eliminates the single biggest manual step in review prep. Also makes engagement scoring significantly more accurate with real-time flow data.

---

## 2. CRM Note Parser (Salesforce)

**What:** Automated extraction of life events, action items, and client preferences from Salesforce activity notes.

**Why we didn't build it:** The firm's Salesforce notes are wildly inconsistent. Some advisors write detailed paragraphs, others write "called client." We'd need NLP or pattern matching to extract structured data from unstructured text, and the training data (their existing notes) wasn't clean enough to build reliable extraction.

**What it would do:**
- Parse CRM notes for life event keywords (retirement, death, marriage, job change, etc.)
- Auto-create LifeEvent records in the client profile
- Extract informal action items ("I told them I'd look into Roth conversions")
- Flag notes that mention competitor firms or client dissatisfaction

**Estimated effort:** 3-4 weeks for basic keyword extraction, 6-8 weeks for NLP-based parsing

**Impact:** Would catch life events that currently get buried in CRM notes and never surface in review prep. Based on our audit, ~40% of relevant life events were logged in Salesforce notes but never made it into review briefings because nobody read back through months of notes.

---

## 3. Financial Plan Integration (MoneyGuidePro)

**What:** API connection to MoneyGuidePro to pull plan status, goal progress, and scenario analysis results.

**Why we didn't build it:** MoneyGuidePro's API is limited. It exposes plan metadata but not the detailed goal tracking we'd need. The workaround is manual — the paraplanner checks plan status in MGP and updates the client profile. Takes 3-5 minutes per client.

**What it would do:**
- Sync goal funding percentages automatically
- Flag when a plan is stale (last updated > 12 months)
- Show probability of success trends over time
- Detect when life events (retirement, inheritance) should trigger a plan update

**Estimated effort:** 2-3 weeks (API is limited, so mostly mapping what's available)

**Impact:** Modest time savings (3-5 min per client) but significant quality improvement — advisors would always know if the plan reflects current circumstances.

---

## 4. Post-Meeting Action Item Tracker

**What:** Structured capture and tracking of action items created during review meetings, with automated assignment, due dates, and follow-up reminders.

**Why we didn't build it:** The firm wanted to see the review prep tool work first before adding more process. Partners were wary of "another thing to fill out after every meeting." We recommended starting with manual action item entry in the client profile and building the structured capture tool once the team was comfortable with the workflow.

**What it would do:**
- Post-meeting form: advisor enters action items, assigns owners, sets due dates
- Automated email reminders at 7 days, 3 days, and 1 day before due date
- Overdue escalation to the advisor if the assigned person misses the deadline
- Action item completion feeds into engagement scoring (follow-through = trust)
- Pre-populates the "Open Items" section of the next review briefing

**Estimated effort:** 2 weeks

**Impact:** Directly addresses the 41% action item follow-through rate. This is the single biggest client experience issue the firm has — clients remember what was promised, even when the advisor doesn't.

---

## 5. Client Portal Activity Tracking

**What:** Integration with the client portal (Black Diamond / Schwab Advisor Center) to track login frequency, statement views, and document downloads.

**Why we didn't build it:** Portal activity data requires API access to the portal provider. Black Diamond has an API but it doesn't expose user activity logs. Schwab's client-facing portal has no API. We'd need to work with the portal providers to get this data, which is a multi-month effort.

**What it would do:**
- Track client portal logins as an engagement signal
- Detect clients who stop logging in (disengagement signal)
- Detect clients who suddenly start logging in frequently (could be doing due diligence before leaving)
- Feed portal activity into the engagement scoring model

**Estimated effort:** 4-6 weeks (mostly vendor coordination)

**Impact:** Would significantly improve engagement scoring accuracy. Portal activity is one of the strongest predictors of attrition — clients who stop checking their accounts are often already mentally disengaged.

---

## 6. Automated Review Scheduling

**What:** System-generated scheduling for upcoming reviews based on service tier and last review date. Sends client-facing scheduling links (Calendly-style).

**Why we didn't build it:** The firm's client service associates handle scheduling manually and were concerned about losing the personal touch. The compromise: the system flags when reviews are due, but a human sends the scheduling email.

**What it would do:**
- Auto-generate the review schedule for the quarter based on tier and last review date
- Send scheduling links to clients with personalized messages
- Track scheduling attempts (first email, follow-up, third attempt)
- Escalate to the advisor if a client doesn't respond to 3 scheduling attempts (disengagement signal)
- Integrate with Google Calendar / Outlook for advisor availability

**Estimated effort:** 2-3 weeks

**Impact:** Reduces scheduling overhead from ~15 hours/quarter to near zero. Also creates structured data about scheduling responsiveness, which is a strong engagement signal.

---

## 7. Attrition Prediction Model

**What:** ML model trained on the firm's historical client data to predict which clients are most likely to leave in the next 90 days.

**Why we didn't build it:** Not enough data. The firm has 8 years of client history but the data is scattered across systems and inconsistently recorded. The engagement scoring module is the foundation — once it's been running for 2-3 quarters with consistent data, we'll have enough labeled examples (clients who left vs. stayed) to train a predictive model.

**What it would do:**
- Predict attrition probability for each client (0-100%)
- Identify the strongest predictive signals specific to this firm's client base
- Generate a quarterly "watch list" of clients most likely to leave
- Estimate revenue at risk from predicted attrition
- Recommend specific retention actions based on the client's risk profile

**Estimated effort:** 4-6 weeks (after sufficient data collection period)

**Impact:** Strategic. Moves from reactive ("they just left") to predictive ("they're likely to leave in Q2, here's why, here's what to do"). The 3 clients lost in Q4 2025 represented $1.8M in AUM — early detection of even one would have been worth the investment.

---

## Phase 2 Recommendation

If the firm moves forward with Phase 2, the priority order is:

1. **Post-Meeting Action Item Tracker** (2 weeks) — Fixes the #1 client experience issue immediately
2. **Automated Review Scheduling** (2-3 weeks) — Reduces admin overhead and creates engagement data
3. **Schwab API Integration** (4-6 weeks) — Eliminates manual data pulls, improves scoring accuracy
4. **CRM Note Parser** (3-4 weeks) — Catches buried life events

Items 5-7 require vendor coordination or extended data collection and should be planned as separate workstreams.

Total Phase 2 estimate: 12-16 weeks, $35-50k depending on API approval timelines.
