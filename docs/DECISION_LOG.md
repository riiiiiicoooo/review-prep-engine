# Decision Log: Review Prep Engine

## Key Architectural Decisions

### 1. Delta-Based Briefings (Why we show what changed, not everything)

**Decision:** Build briefings around changes since last review, not full data dump.

**Rationale:**
- Advisor's mental model: "What's different?" not "Tell me everything again"
- Reduces cognitive load (flags 5-10 items instead of 50)
- Naturally surfaces important items (AUM change, life events, goal status shifts, compliance expirations)
- Matches how advisors actually prepare (notes taken: "Up 8%", "Margaret retired", "IPS expires next month")

**What Changed Since Last Review:**
- AUM change (absolute and %)
- Life events (logged after last meeting)
- Goal status changes (from on_track to at_risk, funding % changes)
- Compliance expirations (documents expiring within 60 days)
- Open action items (from last meeting, not completed)
- New interactions (emails, calls, portal logins)

**What We Don't Repeat:**
- Core household data (members, accounts) — only if changed
- Historical performance (only show since-last-review)
- Goals that are stable on-track
- Compliance items that are current and not expiring

**Implementation:**
- `ReviewBriefing.flags` surface only items needing attention
- `BriefingFlag.severity` prioritizes (HIGH/MEDIUM/LOW)
- Advisor reviews flags first, details second
- This 3-minute scan reveals what matters for this meeting

---

### 2. Engagement Scoring Added Retroactively (Why we learned this the hard way)

**Decision:** Add 6-signal engagement scoring to detect attrition risk.

**Context:**
- Firm lost 3 clients in Q4 2025 with zero warning
- Post-mortem analysis: every client showed signals in their data
  - Client A: Skipped 2 reviews, took 5+ days to respond to emails, AUM down 12%
  - Client B: No portal logins in 6 months, all contacts firm-initiated
  - Client C: Compliance docs expired, no follow-up from last action items
- **The signals existed; nobody was watching for them**

**Decision:** This wasn't in original scope but becomes critical after retention crisis.

**Why Weighted Signals:**
- Meeting attendance: 20% — easiest to measure, most predictive
- Response time: 20% — shows how engaged they are
- Interaction frequency: 15% — thin vs. thick relationship
- AUM trend: 20% — voting with their feet (withdrawals)
- Portal activity: 10% — passive check-in behavior
- Document compliance: 15% — obligation/responsiveness

**Why 6 Not 3:**
- 3-signal model missed clients (e.g., active interaction but declined AUM)
- 6-signal composite catches different attrition patterns
- Weighted allows firm to adjust based on their historical data
  - Asset team might weight AUM heavily; relationship team might weight interaction frequency

**Why Alerts Not Just a Score:**
- Score alone (82/100) doesn't trigger action
- Alerts (score decline >15%, no contact >90 days, disengaged) prompt immediate follow-up
- Advisor sees "ALERT: Score dropped from 78 to 62, no contact in 87 days" and acts

**Thresholds Calibrated Against:**
- Firm's historical attrition data
- Client tenure (older relationships have higher tolerance for gaps)
- Service tier (Platinum clients expect more frequent contact)
- Advisor relationship (some advisors naturally contact more)

---

### 3. Conversation Starters (Why we generate talking points)

**Decision:** Generate natural conversation starters from life events and goals.

**Rationale:**
- Advisor goal: walk in knowing the client (not surprised)
- But advisors are busy; they don't read all notes
- Life events buried in notes: "Ask how Margaret is enjoying retirement"
- Goals at risk: "Discuss timeline adjustment for vacation home goal"
- These are the things that make clients feel known

**Examples Generated:**
```
From RETIREMENT event:
"Ask how Margaret is adjusting to retirement. Any changes to spending or lifestyle?"

From DEATH_FAMILY event:
"Express condolences if not already done. Ask about estate/probate timeline—don't push."

From BIRTH_GRANDCHILD event:
"Congratulate on the grandchild. Natural segue to 529 plan or gifting strategy."

From AT_RISK goal:
"Vacation home goal is at risk (45% funded). Discuss whether to adjust target, timeline, or contributions."
```

**Why Not Auto-Generated from Notes?**
- NLP is not deterministic; false positives feel weird
- Manual curation ensures quality
- Future phase 2: ML-based suggestions ("System found this: 'Bob mentioned his daughter graduated'")

**Implementation:**
- Hard-coded templates per life event category
- Goal status triggers conversation about options (adjust target, timeline, contributions)
- Engagement-based starters ("It's been 8 months since review—check for major changes")

---

### 4. Zero External Dependencies (Why we built JSON persistence instead of using a database)

**Decision:** No external dependencies beyond Python stdlib + FastAPI (API only).

**Rationale - Risk Management:**
1. Compliance: Wealth management firms are high-audit environments
   - Every external package needs vendor assessment, CVE scanning, support contracts
   - Zero dependencies = zero risk surface
2. Portability: Runs anywhere Python runs
   - Desktop (advisor's laptop)
   - On-prem server (firm's infrastructure)
   - Cloud (AWS Lambda for batch import)
   - No dependency on particular cloud provider
3. Long-term Maintainability
   - If package author abandons or sells to bad actor, we're unaffected
   - No "package X stopped supporting Python Y" surprises
   - Core code stays stable over years

**What We Could Use But Don't:**
- SQLAlchemy ORM (instead: JSON files + manual serialization)
- Pandas (instead: csv.DictReader + pure Python)
- Pydantic for validation (instead: dataclass type hints)
- Requests library (instead: urllib.request built-in)
- APScheduler for scheduling (instead: cron or systemd timer)

**Exception: FastAPI for API**
- Lightweight, widely adopted in wealth tech
- Pydantic models for validation
- Auto-generated OpenAPI docs
- Essential for browser dashboards
- If it becomes a liability, easy to replace with Flask

**JSON Persistence Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| JSON files | No dependency, portable, auditable, simple | No SQL querying, slower for large datasets, concurrent write risks |
| SQLite | No dependency, queryable, atomic | Slightly less portable, requires schema migration |
| PostgreSQL | Powerful queries, enterprise | External dependency, requires cloud/server |

**Why JSON:**
- Firm has ~200 households (small dataset)
- Briefings are time-series (one per quarter per client = ~800 briefings/year)
- No concurrent writes (paraplanner's batch job, not real-time app)
- Simpler backup/recovery (ZIP files with JSON)
- Easier to version control (human-readable diffs)

**Serialization Approach:**
- Dataclasses + EnumEncoder handle conversion to/from JSON
- Custom dict_to_dataclass() reconstructs typed objects
- Enums preserved (ServiceTier.GOLD stays typed, not just "gold" string)
- Dates handled (ISO format strings → datetime objects)
- Lists of dataclasses handled (e.g., list[HouseholdMember])

---

### 5. CSV Import Instead of Live APIs (Why we chose batch import)

**Decision:** Start with CSV import (Schwab export, Salesforce export, MoneyGuidePro export).

**Not Phase 1:** Live API connections to custodian, CRM, planning software.

**Rationale:**
1. **Reality of Wealth Management Tech Stack:**
   - Firms have multiple custodians (Schwab, Fidelity, TD)
   - APIs are different across custodians
   - API access requires agreements, vendor relationships, support contracts
   - CSV export is available today without infrastructure work

2. **Process Reality:**
   - Portfolio data is 1-2 days old anyway (T+1 settlement)
   - CRM data is updated by humans (slow)
   - Planning data updated quarterly at best
   - Weekly batch import (Monday morning, before reviews) is sufficient

3. **Phased Rollout:**
   - Phase 1: CSV import (works immediately, no vendor relationships needed)
   - Phase 2 (later): API integrations for real-time (if value justifies complexity)

**CSV Flow:**
1. Monday morning: Paraplanner exports CSVs from each system
   - Schwab portal → Download positions, transactions, performance
   - Salesforce → Export contacts, interactions, notes
   - MoneyGuidePro → Export goals, plan metadata
2. Run import script: `python sample_data/load_sample.py` (batch process)
3. Review briefings auto-assembled
4. Paraplanner QA-checks for accuracy
5. Advisor opens 5 minutes before review

**Why CSV Mapping is Pluggable:**
- Schwab CSV columns: AccountNumber, MarketValue, AsOfDate
- Fidelity CSV columns: Account Number, Market Value, As Of Date
- Custom firm export columns: AcctNum, MktVal, DateGenerated
- Solution: Pluggable PositionImportConfig with column name mapping

---

### 6. Flag Severity Over Raw Metrics (Why flags instead of a score)

**Decision:** Flag-driven briefing (HIGH/MEDIUM/LOW) instead of numeric scoring.

**Example: Why Not This?**
```python
briefing.portfolio_performance_impact = 8.3  # Hard to know what action to take
```

**Instead This:**
```python
briefing.flags = [
    BriefingFlag(severity=HIGH, title="Financial plan stale (14 months)",
                 recommendation="Schedule plan update meeting"),
    BriefingFlag(severity=MEDIUM, title="Risk tolerance expiring in 30 days",
                 recommendation="Schedule renewal during review"),
]
```

**Rationale:**
- Flags are actionable (the briefing tells advisor what to do)
- Flags are contextual (severity accounts for client situation)
- Advisor can scan flags in 1 minute and know priorities
- Raw metrics require interpretation ("8.3% excess return is good or bad?")

**Flag Severity Logic:**
- HIGH: Must discuss in meeting (client will ask, compliance issue, action item overdue)
- MEDIUM: Should discuss if time permits (goal status, expiring soon, rebalance)
- LOW: Nice to know but not urgent

**Example Flags:**
```
[HIGH] Margaret's retirement (Sept 2025)
       → "Update financial plan for earlier retirement"

[HIGH] Robert's mother passed away (Oct 2025, inheritance pending)
       → "Follow up on inheritance amount and timing"

[MEDIUM] Risk tolerance expires in 30 days
         → "Schedule renewal"

[MEDIUM] Vacation home goal at risk (45% funded, timeline pressured)
         → "Discuss adjustment to target or timeline"

[LOW] Portfolio up 8.3% (beating 60/40 benchmark by 1.2%)
      → Nice context but not a flag
```

---

### 7. Per-Household Briefings, Not Batch Scoring (Why we generate on-demand)

**Decision:** Assemble each briefing separately (not generate all briefings at once).

**Rationale:**
- Paraplanner workflow: "I need to review the Hendersons this week"
- System loads HH-001, assembles briefing on-demand
- Can re-assemble if data changes (new transaction, life event logged)
- Allows for Paraplanner QA: "Let me review this before the advisor sees it"

**Why Not Batch:**
- Batch on Monday would generate 88 briefings for the quarter
- 10-12 of those aren't due until week 3-4
- Batch approach = refresh all of them daily? Expensive
- On-demand allows "just-in-time" assembly

**Performance:**
- Briefing assembly <2 seconds per household
- Engagement scoring <1 second per household
- Acceptable latency for a web request

---

### 8. 6-Month Assessment Window (Why we look back 180 days)

**Decision:** Engagement scoring uses 6-month rolling window for signals.

**Rationale:**
- Quarterly reviews → want to see trend over 2 review cycles
- Annual clients (Silver tier) → 6 months captures meaningful activity
- Avoids over-weighting recent spikes (one bad email response doesn't tank score)
- Long enough to see AUM trend (4-6 months of flows)

**Alternative Considered:**
- 12 months: Too long-term, misses current disengagement
- 3 months: Too short, noisy (one missed email inflates it)
- 6 months: Goldilocks zone

**Implementation:**
```python
config = ScorerConfig(assessment_period_days=180)
cutoff = date.today() - timedelta(days=180)
recent_interactions = [i for i in household.interactions if i.date >= cutoff]
```

---

### 9. High-Priority Flags First (Why we sort by severity)

**Decision:** Briefing flags sorted by severity (HIGH first, then MEDIUM, then LOW).

**Rationale:**
- Advisor has 5-10 minutes before meeting to scan briefing
- Sees HIGH flags first (things that will definitely come up)
- Can skip to MEDIUM if time permits
- LOW flags are informational (context, not action items)

**Example Order:**
```
[HIGH] Margaret retired from teaching (Sept 2025)
[HIGH] Robert's mother died (inheritance pending)
[HIGH] Financial plan 14 months old
[HIGH] One action item overdue (LTC insurance research)
[MEDIUM] RTQ expires in 30 days
[MEDIUM] Vacation home goal at risk
[MEDIUM] Portfolio rebalance recommended
[LOW] AUM up 8.3% since review
[LOW] Exceeded contribution room for SEP IRA
```

---

### 10. Household-Level Aggregation (Why we don't separate spouses)

**Decision:** Treat household as the unit, not individual accounts or people.

**Rationale:**
- Wealth management operates on household basis (joint decisions)
- Accounts are often joint or intertwined (Robert's IRA, Margaret's IRA, joint brokerage)
- Planning goals are household goals ("retirement at 65", not "Robert's retirement at 65")
- Lifecycle events (retirement, inheritance, death) affect whole household

**Modeling:**
```python
household = ClientHousehold(
    members=[Robert, Margaret],  # Both in one household
    accounts=[joint, robert_ira, margaret_ira, margaret_rollover],  # All accounts
    goals=[household_retirement, ltc_insurance, college_fund],  # Household goals
)
```

**Not:**
```python
robert_profile = Household(accounts=[joint, robert_ira], goals=["Robert's retirement"])
margaret_profile = Household(accounts=[joint, margaret_ira], goals=["Margaret's retirement"])
# This creates data duplication and coordination complexity
```

---

### 11. Compliance Documents as Time-Series (Why we track expiration dates)

**Decision:** Store compliance documents with expiration dates for proactive renewal.

**Rationale:**
- Risk: SEC exam finds expired or missing compliance items
- Solution: Track every required document, alert when expiring soon
- Generates HIGH flags for briefings when item is overdue

**Examples:**
```python
ComplianceDocument(
    document_type=DocumentType.INVESTMENT_POLICY_STATEMENT,
    status="current",
    last_completed=date(2025, 6, 15),
    expiration_date=date(2026, 6, 15),
    renewal_period_months=12,
)

ComplianceDocument(
    document_type=DocumentType.RISK_TOLERANCE_QUESTIONNAIRE,
    status="expiring",  # expires in 28 days
    last_completed=date(2025, 8, 1),
    expiration_date=date(2026, 4, 1),
    renewal_period_months=12,
)
```

**Properties:**
- `days_until_expiry`: Calculated on-the-fly
- `is_expiring_soon`: True if 0 < days ≤ 60
- `is_expired`: True if days ≤ 0

**Briefing Impact:**
- Expired or missing → HIGH flag
- Expiring soon (≤60 days) → MEDIUM flag

---

### 12. Action Item Tracking Over Time (Why we keep history)

**Decision:** Track action item status changes with timestamps.

**Rationale:**
- Example: Action item created 6 months ago, still open → HIGH flag
- Paraplanner marks as OPEN (created in Q3 review)
- Q4 review: still OPEN → overdue, needs escalation
- Tracking history shows when it was created vs. when it became overdue

**Implementation:**
```python
tracker = ActionItemTracker(action_item)
tracker.status_history = [
    {"status": "open", "changed_at": "2025-09-15T14:30:00", "notes": "Created in Q3 review"},
    {"status": "in_progress", "changed_at": "2025-11-01T10:00:00", "notes": "Paraplanner assigned to Sarah"},
    {"status": "completed", "changed_at": "2026-01-15T16:45:00", "notes": "Beneficiary forms signed"},
]
```

**Why Not Just Current Status?**
- Current status only shows "open" (doesn't show 6-month old)
- Created date + status gives context ("created 6 months ago, still open = overdue")

---

## Rejected Alternatives

### Machine Learning for Life Event Detection (Rejected, Phase 2)
- **Idea:** Auto-detect life events from CRM notes using NLP
- **Why Rejected:** Requires ML model, training data, ongoing tuning; false positives feel weird to advisor
- **Phase 2:** Suggest detected events to paraplanner for manual review

### Multi-Advisor Support in MVP (Rejected, Phase 2)
- **Idea:** Role-based access (advisor sees own households, paraplanner sees all)
- **Why Rejected:** Adds complexity (permissions, filtering, audit logging); single-advisor firm doesn't need it yet
- **Phase 2:** Add after proving value with single advisor

### Predictive Analytics (Rejected, Phase 2)
- **Idea:** "This client will be at risk in 30 days based on trends"
- **Why Rejected:** Requires historical data, model training, validation; can't do on day-1
- **Phase 2:** Build after 1 year of scoring data

### Real-Time API Integration (Rejected, Phase 1)
- **Idea:** Live connection to Schwab/Salesforce APIs
- **Why Rejected:** CSV export is available today; APIs require vendor agreements and custom code per custodian
- **Phase 2:** Implement after CSV proves concept

### Multiple Briefing Formats at Launch (Rejected, Phase 1)
- **Idea:** PDF, Word, HTML, custom templates
- **Why Rejected:** Markdown and text are sufficient; other formats can be added later
- **Scope Creep Risk:** Each format adds testing and maintenance burden

---

## Tradeoffs Made

### Engagement Scoring vs. Simplicity
- **Tradeoff:** More complexity but catches attrition early
- **Decision:** Worth it (firm lost 3 clients with no warning)
- **Mitigation:** Weights are configurable; firm can adjust based on experience

### CSV Import vs. Real-Time APIs
- **Tradeoff:** 1-2 day data lag vs. no external dependencies
- **Decision:** CSV is acceptable for weekly briefing cycle
- **Mitigation:** Phase 2 can add real-time if needed

### Zero Dependencies vs. Development Speed
- **Tradeoff:** Slower to build JSON serialization vs. using a database
- **Decision:** Speed cost is minimal; audibility and portability matter more
- **Mitigation:** JSON serialization library could be open-sourced if needed

### Single-Household Briefings vs. Batch Generation
- **Tradeoff:** Slightly less efficient vs. better paraplanner workflow
- **Decision:** On-demand is better UX (can review anytime, not waiting for batch)
- **Mitigation:** Weekly batch can still run as scheduled task

---

## Open Questions for Future

1. **How should we handle held-away accounts?**
   - Visible in briefing but not included in AUM calculations?
   - Create separate held-away account line items?

2. **Should action items survive across reviews?**
   - Currently: carried forward if not completed
   - Alternative: close them on next review, re-open if still needed
   - Pro: cleaner history; Con: more manual work

3. **How to score clients with very recent life events?**
   - New inheritance might temporarily reduce AUM due to illiquidity
   - Shouldn't tank engagement score immediately
   - Solution: contextual scoring based on event type?

4. **Should compliance tracking include client-signed documents?**
   - E.g., updated beneficiary form signed by client
   - Interaction history captures this; should ComplianceDocument also reference the signature date?

5. **How to handle advisor turnover?**
   - If advisor leaves, does household reassign?
   - History tracking needed?
   - What about briefing continuity?

---

## Decisions We're Confident About

✅ **Delta-based briefings** — Matches advisor mental model perfectly
✅ **Engagement scoring** — Solves real attrition problem (firm proved this)
✅ **Zero dependencies** — Risk profile favorable for compliance environment
✅ **CSV import** — Pragmatic first step (avoid API complexity)
✅ **Household-level aggregation** — Correct modeling for wealth management
✅ **JSON persistence** — Simple, portable, auditable

---

## Decisions We'll Revisit

🔄 **Engagement scoring weights** — Will calibrate after 3-6 months of real data
🔄 **Flag severity thresholds** — May adjust based on advisor feedback
🔄 **CSV column mappings** — Will add Fidelity, TD Ameritrade configs as needed
🔄 **Batch import frequency** — May increase to daily if valuable
