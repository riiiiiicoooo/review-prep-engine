# Product Requirements Document: Review Prep Engine

## Executive Summary

The Review Prep Engine is a workflow automation tool that eliminates the operational bottleneck of manual review briefing assembly in wealth management firms. Instead of paraplanners spending 35-50 minutes per client manually pulling data from 4 systems (custodian, CRM, planning software, compliance spreadsheet), the system assembles complete, flag-driven briefings in minutes and surfaces engagement risk early.

**Target time savings:** 150 hours/quarter → 12 minutes per client = ~72 hours/quarter saved

---

## User Personas

### Primary User: Senior Paraplanner (Age 35-50)

**Background:**
- 8-12 years in wealth management operations
- Reports to compliance officer or COO
- Owns the review assembly process and quality gate
- Currently spends 2-3 hours per day on review prep
- Uses Salesforce CRM casually, comfortable with spreadsheets, not a developer

**Pain Points:**
- Spending 150 hours/quarter on a task that's mostly copy-paste
- Juggling 4 systems with different update frequencies → inconsistent data
- Missing life events because CRM notes are disorganized (23% of advisors miss something)
- Action items from last review live in a Word doc attached to a note (41% never get followed up)
- No systematic way to catch clients who are disengaging

**Goals:**
- Complete review prep in <15 minutes per client (vs. 45 now)
- Have confidence that nothing's been missed
- Shift work from assembly to quality review and proactive flagging
- Identify at-risk clients before they leave

### Secondary User: Senior Advisor (Age 45-60)

**Background:**
- Books 10-15 review meetings per quarter
- Manages relationships, not operations
- Spends 5-10 minutes before each meeting reviewing prep materials
- Wants to walk in knowing the client, not to be surprised

**Pain Points:**
- Prep materials arrive 24 hours before meeting (sometimes during the meeting)
- Half the time the paraplanner missed something (life event, new goal, open action item)
- Doesn't know which clients are at risk of leaving until they call to say goodbye
- Compliance items buried in documents → exposures not caught before reviews

**Goals:**
- Know before the meeting: what's changed, what's flagged, what's at risk
- Surface engagement warning signs before they become crisis
- Reduce time spent hunting for information during meetings

### Tertiary User: Compliance Officer (Age 50-65)

**Background:**
- One compliance person for 12-person firm
- Spends time on document tracking and deadline management
- Reviews for SEC/state exam prep

**Pain Points:**
- Compliance item tracking in a spreadsheet that's constantly out of date
- No automated reminder when RTQ or IPS expires
- Misses beneficiary designation updates on client accounts
- Manually verifies ADV delivery annually

**Goals:**
- Single system of record for all compliance items
- Automated expiration alerts
- Proof that all required docs are current/reviewed in the past 12 months

---

## Current State (Before System)

### As-Is Review Prep Workflow

**Monday morning, week before review:**

1. Paraplanner opens 4 systems in different tabs
2. Custodian portal (Schwab) → pulls account balances, performance
   - Time: ~15 minutes
   - Risk: Performance data is 1-2 days old; positions may be stale
3. Salesforce CRM → reads 6 months of notes looking for life events
   - Time: ~10 minutes
   - Risk: Notes are inconsistent (some advisors log everything, others log nothing)
   - Miss rate: 23% of advisors miss a life event that impacts planning
4. MoneyGuidePro → checks plan currency, goal funding status
   - Time: ~5 minutes
   - Risk: Plan may not reflect recent life events (Margaret's early retirement, Robert's inheritance)
5. Internal spreadsheet → action items from last meeting
   - Time: ~5 minutes
   - Risk: Half the items are never followed up on
6. Word template → copy-paste everything into a meeting document
   - Time: ~15 minutes
7. Print, staple, hand to advisor
   - Advisor reads 5 minutes before meeting or not at all

**Total prep time:** 35-50 minutes per client
**Total quarterly cost:** ~150 hours × $100-150/hr = $15k-22k
**Quality:** Inconsistent, depends on paraplanner knowledge and mood

### Key Metrics

- **Average review prep time:** 42 minutes
- **Client reviews per quarter:** 350 meetings/year ÷ 4 = ~88 per quarter
- **Total quarterly hours:** 88 × 0.7 hrs = ~62 hours (conservative estimate, actual is higher)
- **Life event coverage:** 77% (23% miss something important)
- **Action item follow-through:** 59% (41% are dropped)
- **Compliance item currency:** Not tracked systematically (estimated 85% current)
- **Client attrition rate:** 2.5% per year; 3 clients lost in Q4 2025 with no warning

---

## Proposed Solution: Review Prep Engine

The system replaces the manual assembly process with an automated pipeline that:

1. **Imports data** from custodian, CRM, and planning software via CSV/API
2. **Normalizes** across multiple source formats (Schwab vs. Fidelity, Salesforce vs. Redtail)
3. **Detects changes** since last review (life events, AUM movement, goal status, compliance expirations)
4. **Assembles briefings** with flagged items prioritized (HIGH/MEDIUM/LOW)
5. **Scores engagement** using 6 weighted signals to surface at-risk clients
6. **Exports** as clean Markdown or text for advisor review

### How It Works: The Happy Path

**Monday morning, week before reviews:**

1. Paraplanner opens the dashboard (single system)
2. Sees 12 reviews scheduled this week; system has auto-assembled 8 green (no issues), 3 amber (open items), 1 red (disengaging)
3. Opens Henderson briefing (auto-assembled, needs review)
   - Sees Margaret's retirement flagged (HIGH priority)
   - Sees Robert's mother's death flagged (HIGH priority) + inheritance follow-up needed
   - Sees financial plan is stale (14 months old) flagged (HIGH priority)
   - Sees 2 of 3 action items completed from last review
   - Sees 4 life events since last review
   - Sees conversation starters: "Ask how Margaret is adjusting to retirement"
4. Reviews for accuracy (~5 minutes), marks as reviewed
5. Advisor opens briefing before meeting, walks in prepared
6. Client has better experience because advisor is present, not surprised

**New workflow time per client:** 8-12 minutes (paraplanner) + 5 minutes (advisor)
**Compliance benefit:** All required docs tracked, expirations visible, no surprises in exam

---

## Functional Requirements

### 1. Data Import

**CR-1: Custodial Portfolio Importer**
- Accepts Schwab/Fidelity CSV exports
- Parses: account numbers, balances, types, custodian
- Maps to Account and PerformanceSnapshot models
- Handles multiple custodian formats with pluggable config

**CR-2: CRM Importer**
- Accepts Salesforce/Redtail contact export
- Parses: household members, contact info, relationship, employment, retirement status
- Parses: interactions (meetings, emails, calls, portal logins)
- Maps to HouseholdMember and Interaction models
- Extracts notes for life event detection

**CR-3: Planning Importer**
- Accepts MoneyGuidePro/eMoney goal export
- Parses: goal name, category, target amount, target date, funded %, status
- Maps to FinancialGoal model
- Parses: plan metadata (creation date, last review, next review) as compliance documents

### 2. Briefing Assembly

**CR-4: Briefing Assembler**
- Input: household profile, meeting date
- Output: ReviewBriefing with flagged items
- Sections:
  - Household context (members, risk tolerance, time horizon)
  - Life events since last review (sorted by date, flagged by severity)
  - Portfolio summary (AUM change, performance vs. benchmark, allocation drift)
  - Financial goals (status, funding %, target date)
  - Compliance checks (current, expiring, expired, missing)
  - Open action items (overdue highlighted)
  - Conversation starters (derived from life events and goals)
- Flags: HIGH (must discuss), MEDIUM (should discuss), LOW (nice to know)

**CR-5: Flag Generation**
- Life events: DEATH_FAMILY, RETIREMENT, INHERITANCE, HEALTH_ISSUE, DIVORCE → HIGH
- Compliance: expired/missing → HIGH; expiring (≤60 days) → MEDIUM
- Action items: overdue → HIGH; >2 overdue → HIGH
- Financial plan: >12 months old → HIGH
- Goals: at_risk status → MEDIUM
- Rebalance: drift >5% → MEDIUM

### 3. Engagement Scoring

**CR-6: Engagement Scorer**
- Input: household profile with interaction history
- Output: composite score (0-100) + engagement level + risk factors
- 6 weighted signals:
  - Meeting attendance (20%): scheduled reviews attended
  - Response time (20%): how quickly to emails/calls
  - Interaction frequency (15%): outbound + inbound contacts per period
  - AUM trend (20%): net flows vs. performance
  - Portal activity (10%): logins, document signatures
  - Document compliance (15%): current vs. expired docs
- Engagement levels: STRONG (≥80), HEALTHY (60-79), COOLING (40-59), AT_RISK (20-39), DISENGAGED (<20)
- Attrition risk: LOW, MODERATE, HIGH, CRITICAL
- Alerts: score decline >15%, no contact >90 days, disengaged status

### 4. Data Persistence

**CR-7: JSON Store**
- Save/load ClientHousehold profiles
- Save/load ReviewBriefing documents
- Serialize all dataclasses with proper enum/date handling
- Directory structure: data/households/{hh_id}/profile.json, briefings/{date}.json
- Auto-backup function creates ZIP of all data
- Export single household to self-contained JSON

**CR-8: Briefing History**
- Load previous briefings for delta analysis
- Track action item status over time (open → in_progress → completed)
- Support time-series analysis (which goals improved, which declined)

### 5. Briefing Export

**CR-9: Export to Markdown**
- Clean, readable format for advisor review
- Includes: header, flags, household context, life events, portfolio, goals, compliance, action items, conversation starters
- Can be copy-pasted into email or CMS

**CR-10: Export to Text (2-page format)**
- Professional layout with page breaks
- Page 1: briefing summary + flags + portfolio
- Page 2: compliance + action items + conversation starters
- Includes firm logo placeholder, advisor name, meeting date
- Confidentiality footer

### 6. User Interface

**CR-11: Dashboard**
- List upcoming reviews (next 2 weeks)
- Each review shows: household, tier, advisor, meeting date, high/medium flags, status
- Filter by advisor, tier, urgency
- One-click to open briefing document
- Status indicators: NOT_STARTED (gray), AUTO_ASSEMBLED (blue), REVIEWED (green), APPROVED (green checkmark)

**CR-12: API Endpoints**
- GET /households (list with engagement score, next review date)
- GET /households/{id}/briefing (generate and return briefing)
- GET /households/{id}/action-items (list with status)
- POST /households/{id}/action-items/{item_id}/update (update status)
- GET /dashboard/upcoming-reviews (next 2 weeks with prep status)

---

## Non-Functional Requirements

### Performance
- Briefing assembly: <2 seconds per household
- Dashboard load: <3 seconds
- CSV import (500 rows): <5 seconds

### Reliability
- Zero external dependencies (except Python stdlib + FastAPI)
- JSON persistence has no risk of data loss (file-based, not database)
- All imports are idempotent (can re-run without duplication)

### Usability
- All file paths and configs use standard conventions
- Error messages are specific and actionable
- Sample data provided for testing without real client data

### Security
- No authentication/authorization in MVP (single-advisor firm context)
- Future: role-based access (advisor sees own households, paraplanner sees all)
- Data is stored as JSON (future: encrypt at rest)

---

## Success Metrics

### Time Savings
- **Target:** Review prep <12 minutes per client (down from 45)
- **Measurement:** Time tracking in dashboard

### Quality
- **Target:** 100% of life events captured (up from 77%)
- **Measurement:** Post-meeting survey: "Did the advisor mention anything you'd logged?"
- **Target:** 85%+ action item follow-through (up from 59%)
- **Measurement:** Action items completed before next review

### Risk Detection
- **Target:** Identify at-risk clients >60 days before attrition
- **Measurement:** Engagement score trend analysis + alerts sent vs. clients who leave
- **Baseline:** Lost 3 clients in Q4 2025 with no warning
- **Goal:** Zero unexpected attrition (proactive retention)

### Adoption
- **Target:** 100% of reviews use system-generated briefings
- **Measurement:** Dashboard usage, export counts
- **Target:** System used for 50% of compliance tracking (vs. spreadsheet)
- **Measurement:** Compliance document currency verified via system

---

## Scope

### In Scope (MVP)
- CSV importers for Schwab/Fidelity positions, Salesforce contacts, MoneyGuidePro goals
- ReviewBriefing assembly with flag generation
- 6-signal engagement scoring with attrition risk
- JSON persistence layer (save/load households and briefings)
- FastAPI dashboard with upcoming reviews and briefing viewer
- Markdown and text export formats

### Out of Scope (Phase 2)
- Live API connections to custodians/CRM/planning software (CSV import only for now)
- Advanced analytics (trend analysis, portfolio optimization)
- Mobile app
- Multi-advisor support with role-based access
- Reporting suite for compliance officer
- Integration with Black Diamond or other reporting tools
- Advisor note taking/markup during meetings

---

## Implementation Timeline

- **Week 1:** Core data models + CSV importers
- **Week 2:** Review assembler + flag generation
- **Week 3:** Engagement scorer + persistence layer
- **Week 4:** API + dashboard
- **Week 5:** Export formats (Markdown, text)
- **Week 6:** Testing, sample data, documentation

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Data quality from CSV imports | Missing/incorrect data in briefings | Comprehensive column mapping, error logging, paraplanner review gate |
| Life event detection from unstructured notes | Missed important events | ML-based NLP tagging in phase 2; for now, require structured life event logging |
| Engagement scoring false positives | Advisor follows up on false signals (waste of time) | Calibrate weights against historical attrition; manual override option |
| Adoption resistance from advisors | System unused if advisors prefer old process | Emphasize time savings, better client experience, early risk detection |
| Compliance item tracking incomplete | Missed expirations in exam | Requirement: all compliance docs tracked in system before go-live |

---

## Definition of Done

- All CSV importers tested with sample data
- Sample data includes 6+ diverse households (different tiers, compositions, situations)
- ReviewBriefing generated for each sample household
- All flagged items reviewed by compliance officer for accuracy
- Dashboard shows upcoming reviews with correct status
- Export formats render correctly (Markdown readable, text printable)
- Zero blocking errors in error logs
- Documentation complete (PRD, ARCHITECTURE, DECISION_LOG)
- Sample load script runs end-to-end without manual intervention
