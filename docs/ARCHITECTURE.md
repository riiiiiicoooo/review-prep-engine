# Architecture Documentation: Review Prep Engine

## System Overview

The Review Prep Engine is a data pipeline that transforms raw portfolio, CRM, and planning data into advisor-ready briefings with engagement risk scoring. It uses a pure Python architecture with zero external dependencies (beyond stdlib), enabling deployment anywhere without dependency hell.

```
CSV Imports           Normalize              Change Detection         Briefing Assembly
┌─────────────┐    ┌──────────────┐      ┌────────────────┐       ┌──────────────┐
│ Schwab CSV  │───→│ Account Data  │     │ Life Events    │──────→│ ReviewBriefing
│ Fidelity CSV│    │ Performance   │────→│ AUM Delta      │       │ (with flags) │
│ CRM CSV     │    │ Interactions  │     │ Goal Status    │──────→│              │
│ Planning CSV│    │ Goals         │     │ Compliance Exp │       └──────────────┘
└─────────────┘    └──────────────┘     │ Action Items   │
                                        └────────────────┘

Engagement Scoring              Persistence              Export
┌──────────────────┐           ┌────────────┐          ┌──────────┐
│ 6 Signals:       │──────────→│ JSON Store │────────→ │ Markdown │
│ - Meeting Attend │           │ - Profiles │          │ Text     │
│ - Response Time  │           │ - Briefings│          │ API      │
│ - Interaction    │           │ - History  │          └──────────┘
│ - AUM Trend      │           └────────────┘
│ - Portal Activity│
│ - Doc Compliance │
└──────────────────┘
```

## Module Structure

### src/client_profiler.py
**Purpose:** Core data model — the "single client view"

**Key Classes:**
- `ClientHousehold`: Top-level container for all client data
  - Computed properties: total_aum, aum_change, open_action_items, compliance_issues
- `HouseholdMember`: Individual in household (name, relationship, DOB, occupation, retirement status)
- `Account`: Investment account (custodian, type, balance, is_managed flag)
- `PerformanceSnapshot`: Period-over-period performance (return%, benchmark, net flows)
- `AssetAllocation`: Current vs. target allocation with drift calculation
- `LifeEvent`: Major life events (marriage, retirement, death, inheritance, etc.)
- `FinancialGoal`: Financial goal with status (on_track, at_risk, off_track, achieved, deferred)
- `ComplianceDocument`: Tracked compliance items (IPS, RTQ, ADV, beneficiary designations) with expiration
- `ActionItem`: Follow-up from review meeting with status and priority
- `ReviewRecord`: Historical meeting record (attendees, topics, action items created)
- `Interaction`: Any contact with client (email, phone, meeting, portal login)

**Design Rationale:**
- Pure dataclasses, no ORM dependencies
- Enum types for all categorical fields (ServiceTier, AccountType, LifeEventCategory, etc.)
- Computed properties (@property) for derived data (age, balance_change, excess_return, days_until_expiry)
- ClientBook class aggregates households with utility methods (list_by_advisor, list_reviews_due, list_compliance_issues)

### src/review_assembler.py
**Purpose:** Builds advisor-ready briefings from client profiles

**Key Classes:**
- `ReviewBriefing`: Complete briefing output with sections and flags
- `BriefingFlag`: Flagged item with severity (HIGH/MEDIUM/LOW), category, detail, recommended action
- `PortfolioSummary`: AUM, performance, allocation, rebalance needs
- `ComplianceCheck`: Compliance status and items requiring action
- `ReviewAssembler`: Main engine that produces briefings

**Process:**
1. Build household context (members, risk tolerance, time horizon)
2. Extract life events since last review
3. Calculate portfolio changes (AUM delta, performance vs. benchmark, allocation drift)
4. Summarize goal status and funding
5. Check compliance currency (expired, expiring, missing documents)
6. List open action items with overdue flagging
7. Generate flags across all sections
8. Create conversation starters from life events and goal status
9. Format as readable text document

**Flag Severity Rules:**
- HIGH: Life events (death, divorce, retirement, health, inheritance); expired/missing compliance; >1 overdue action item; financial plan >12 months old
- MEDIUM: Life events (job change, home purchase, birth); expiring compliance (≤60 days); at_risk goals; rebalance needed
- LOW: Other life events; other goal status

**Conversation Starters:**
Generated dynamically from:
- "Ask how [member] is adjusting to retirement" (from RETIREMENT event)
- "Express condolences... ask about estate/probate timeline" (from DEATH_FAMILY event)
- "Congratulate on grandchild... natural segue to 529" (from BIRTH_GRANDCHILD event)
- Job change → 401k rollover and benefits discussion
- Home purchase → insurance, mortgage strategy, cash flow impact
- At-risk goals → discuss adjustment to target, timeline, or contributions
- Long time since last review → check for major changes

### src/engagement_scorer.py
**Purpose:** Detect early attrition signals using 6 weighted engagement signals

**Key Classes:**
- `EngagementReport`: Complete engagement assessment with composite score and risk assessment
- `EngagementAlert`: Alert for specific concerning patterns (score decline, no contact, disengaged)
- `SignalScore`: Individual signal with weight, raw score, weighted score, detail, data points
- `EngagementScorer`: Scoring engine

**6 Signals (weights sum to 1.0):**
1. **Meeting Attendance (20%):** Expected reviews attended based on tier
   - Platinum (quarterly): expect ~2 per 6 months
   - Gold (semi-annual): expect 1 per 6 months
   - Silver (annual): expect 0.5 per 6 months
   - Bonus: +10 points if spouse attended
2. **Response Time (20%):** Average response time to outbound contacts
   - ≤4 hours = 100
   - ≤24 hours = 80
   - ≤72 hours = 50
   - ≤1 week = 25
   - >1 week = 10
3. **Interaction Frequency (15%):** Total contacts vs. expected for tier
   - Platinum: ~2 per month
   - Gold: ~1 per month
   - Silver: ~1 per 2 months
   - Bonus: +15 if >30% client-initiated contacts
   - Penalty: -15 if gap >60 days between contacts
4. **AUM Trend (20%):** Direction of money (inflows vs. outflows)
   - Net inflows: 70-100 (very positive)
   - Net outflows <5%: 65 (probably planned)
   - Net outflows 5-10%: 50
   - Net outflows 10-20%: 35
   - Net outflows >20%: 15 (very concerning)
5. **Portal Activity (10%):** Client logins and document signatures
   - No activity: 30 (might just prefer phone/email)
   - Expected ~1 login per month
6. **Document Compliance (15%):** Current, expiring, expired, missing
   - Score: (current/total) × 80% - (expired × 15) - (expiring × 5)

**Engagement Levels:**
- STRONG (≥80): Engaged, responsive, growing AUM
- HEALTHY (60-79): Normal patterns, routine contact
- COOLING (40-59): Early warning signs (missing meetings, delayed responses, AUM flat)
- AT_RISK (20-39): Multiple disengagement signals (outbound heavy, declining AUM, compliance overdue)
- DISENGAGED (<20): Likely already exploring alternatives (long silence, multiple failed outreach, withdrawals)

**Attrition Risk:**
- LOW: Score ≥60 with stable trend
- MODERATE: Score 40-60 or ≥3 risk factors
- HIGH: Score <60 with declining trend or score <40
- CRITICAL: Score <20 (disengaged)

**Alerts Generated:**
- Score decline >15% between scoring periods
- No contact >90 days
- Disengaged status (DISENGAGED level)

### importers/custodial_import.py
**Purpose:** Import portfolio data from custodian CSV exports

**Key Classes:**
- `CustodialImporter`: Main importer with methods for positions, transactions, performance, allocations
- `PositionImportConfig`: Pluggable column mapping for different custodians
- `SchwabPositionConfig`: Pre-configured for Schwab CSV format
- `FidelityPositionConfig`: Pre-configured for Fidelity CSV format

**Process:**
1. import_positions(csv_file) → List[Account]
   - Read CSV with configurable column mapping
   - Parse balance (remove $ and commas)
   - Parse date (YYYY-MM-DD format)
   - Map account type strings to AccountType enum
   - Consolidate positions to account level (sum if multiple rows per account)
2. import_transactions(csv_file) → List[Dict]
   - Read transaction CSV (date, amount, description, type)
   - Returned as dicts for flow analysis
3. import_performance(csv_file) → List[PerformanceSnapshot]
   - Read performance period CSV (period dates, return%, benchmark, net flows)
   - Create PerformanceSnapshot objects
4. import_allocations(csv_file) → List[AssetAllocation]
   - Read allocation CSV (asset class, target%, actual%, market value)
   - Create AssetAllocation objects

**Column Mapping Strategy:**
Pluggable config object allows different custodian formats:
```python
config = SchwabPositionConfig()  # Pre-configured
importer.import_positions("file.csv", config)

# Or custom:
config = CustomConfig(
    account_number_col="Acct",
    balance_col="Market Value",
    ...
)
importer.import_positions("file.csv", config)
```

### importers/crm_import.py
**Purpose:** Import contact and interaction data from CRM CSV exports

**Key Classes:**
- `CRMImporter`: Main importer with methods for contacts, interactions, notes

**Process:**
1. import_contacts(csv_file) → List[HouseholdMember]
   - Read CSV (first/last name, DOB, email, phone, employer, occupation, retired status, retirement date, relationship, notes)
   - Parse dates and boolean fields
   - Create HouseholdMember objects
2. import_interactions(csv_file) → List[Interaction]
   - Read CSV (date, interaction type, direction, initiated by, summary, response time)
   - Normalize direction (inbound vs. outbound)
   - Normalize interaction types (email, phone, meeting, portal_login, document_signed)
   - Parse response time as float (hours)
3. import_notes(csv_file) → List[Dict]
   - Read notes CSV (contact name, date, text, category)
   - Return as dicts for manual processing (future: NLP for auto-categorization)

### importers/planning_import.py
**Purpose:** Import financial goals and plan metadata from planning software CSV

**Key Classes:**
- `PlanningImporter`: Main importer with methods for goals, plan metadata, projections

**Process:**
1. import_goals(csv_file) → List[FinancialGoal]
   - Read CSV (goal name, category, target amount, target date, funded %, status, last review date, notes)
   - Map status strings to GoalStatus enum (On Track, At Risk, Off Track, Achieved, Deferred)
   - Map category strings to standard categories (retirement, education, estate, lifestyle)
   - Create FinancialGoal objects with auto-incrementing IDs (G-001, G-002, etc.)
2. import_plan_metadata(csv_file) → List[ComplianceDocument]
   - Read plan data (plan name, created date, last review date, next review date, status, notes)
   - Create ComplianceDocument objects with DocumentType.FINANCIAL_PLAN
   - Use next review date as expiration date
3. import_projections(csv_file) → List[Dict]
   - Read projection data (scenario, year, age, projected balance, income, withdrawals)
   - Return as dicts for optional scenario analysis (phase 2)

### storage/json_store.py
**Purpose:** Lightweight JSON-based persistence (no database needed)

**Key Classes:**
- `JSONStore`: Main persistence interface
- `BriefingHistory`: Time-series briefing loading and querying
- `ActionItemTracker`: Status change tracking for individual action items
- `EnumEncoder`: Custom JSON encoder for dataclass enums and dates

**Design Rationale:**
- Pure file-based storage (no database dependency)
- Dataclass-to-dict conversion handles enums, dates, nested objects
- Dict-to-dataclass reconstruction rebuilds typed objects from JSON
- Directory structure: `data/households/{hh_id}/profile.json` and `data/households/{hh_id}/briefings/{date}.json`
- History support for delta analysis (load previous briefing to calculate what changed)

**Interface:**
```python
store = JSONStore("data")

# Save/load households
store.save_household(household)
household = store.load_household("HH-001")

# Save/load briefings
store.save_briefing(briefing)
briefing = store.load_briefing("HH-001", date(2026, 3, 3))
latest = store.load_briefing("HH-001")  # None date = latest

# Engagement scores
store.save_engagement(reports_dict)
engagement = store.load_engagement("HH-001")
all_engagements = store.list_engagements()

# Export
store.backup_data("backup_2026-03-03.zip")
store.export_household_data("HH-001", "export_HH-001.json")

# Action item tracking
tracker = store.track_action_item(action_item)
store.update_action_item_status("AI-001", ActionItemStatus.COMPLETED, "Completed in review")
history = store.get_action_item_history("AI-001")
```

### api/app.py (FastAPI)
**Purpose:** REST API for dashboard and external integrations

**Endpoints:**
- `GET /households` — List all households with engagement scores, next review date, service tier
- `GET /households/{id}/briefing` — Get/generate briefing for specific household
- `GET /households/{id}/action-items` — List open action items with status
- `POST /households/{id}/action-items/{item_id}/update` — Update action item status
- `GET /dashboard/upcoming-reviews` — Briefings due within next 14 days with status

**Pydantic Models:** For request/response validation (type hints + serialization)

### export/briefing_renderer.py
**Purpose:** Format briefings for different output formats

**Methods:**
- `render_markdown(briefing) → str` — Clean Markdown format for email/documentation
- `render_text(briefing) → str` — Professional 2-page text format (for printing)
  - Page 1: briefing header + flags + portfolio summary
  - Page 2: compliance + action items + conversation starters
  - Includes firm logo placeholder, advisor name, meeting date, confidentiality footer

## Data Flow Example: The Henderson Household

```
Input: Schwab CSV with 4 accounts (ACCT-001 through ACCT-004)
       Salesforce CSV with Robert & Margaret Henderson
       MoneyGuidePro CSV with 4 goals

   ↓

Import Phase:
  - CustodialImporter reads positions
    ACCT-001 Joint balance $485,000
    ACCT-002 Traditional IRA balance $312,000
    ACCT-003 Roth IRA balance $198,000
    ACCT-004 Rollover IRA balance $245,000

  - CRMImporter reads contacts
    Robert Henderson, primary, age 62, employer Henderson & Associates, occupation Small business owner
    Margaret Henderson, spouse, age 61, retired teacher, is_retired=True, retirement_date=2025-09-01

  - PlanningImporter reads goals
    "Retirement at 65 (Robert)" — target $2.5M, target date 2027-08-14, funded 78%, on_track
    "Margaret's Long-Term Care" — target $250k, funded 35%, at_risk
    "College fund for grandson" — target $120k, funded 32%, on_track
    "Vacation home down payment" — target $150k, funded 45%, at_risk

   ↓

Normalization Phase:
  - Build ClientHousehold("HH-001")
    service_tier = GOLD (AUM $1.24M)
    members = [Robert, Margaret]
    accounts = [4 accounts, total $1.24M]
    goals = [4 goals]

   ↓

Change Detection Phase:
  - Load previous briefing (from 95 days ago)
    Previous AUM was $919,000
    Current AUM is $1,240,000
    Change = +$321,000 (+35%)

  - Detect life events since last review
    Margaret's retirement (event_date 2025-09-01, logged 2025-09-05)
    Robert's mother's death (event_date 2025-10-15, logged 2025-10-18)

  - Detect goal status changes
    "Vacation home" went from on_track to at_risk (due to Margaret's early retirement)

  - Detect compliance expirations
    Financial plan (last updated 2024-11-20) is 14 months old → flag as HIGH
    Risk tolerance questionnaire expires in 30 days → flag as MEDIUM

   ↓

Briefing Assembly Phase:
  - Assemble ReviewBriefing
    household_id = HH-001
    primary_contact = Robert Henderson
    service_tier = GOLD
    advisor = Michelle Torres
    meeting_date = 2026-03-15

  - Household context: Robert (primary, age 62), Margaret (spouse, age 61, retired)

  - Life events: 2 events since last review (RETIREMENT, DEATH_FAMILY)

  - Portfolio:
    AUM $1.24M (+35.0% since review)
    Performance +8.3% (benchmark +7.1%, excess +1.2%)
    Allocation: US Equity 43.2% (target 40%, +3.2% drift)

  - Goals: 3 on_track, 1 at_risk

  - Compliance: 1 expired, 1 expiring (action required)

  - Action items: 3 open, 1 overdue (>30 days)

  - Flags:
    [HIGH] Margaret's retirement — "Update financial plan for earlier retirement"
    [HIGH] Robert's mother's death — "Follow up on inheritance amount and timing"
    [HIGH] Financial plan stale (14 months) — "Schedule plan update meeting"
    [MEDIUM] Risk tolerance expires in 30 days — "Schedule renewal"
    [MEDIUM] Vacation home goal at risk — "Discuss adjustment to timeline or contributions"

  - Conversation starters:
    "Ask how Margaret is adjusting to retirement. Any changes to spending or lifestyle?"
    "Express condolences... ask about estate/probate timeline (don't push)"

   ↓

Persistence Phase:
  - JSONStore.save_briefing(briefing)
    Writes to data/households/HH-001/briefings/2026-03-03.json
    Briefing file contains all sections, flags, action items, conversation starters

  - JSONStore saves engagement report (from EngagementScorer)
    Score: 82.3 (STRONG)
    Trend: STABLE
    Attrition risk: LOW

   ↓

Export Phase:
  - BriefingRenderer.render_markdown(briefing)
    Produces clean, readable Markdown for email

  - BriefingRenderer.render_text(briefing)
    Produces 2-page text format (page 1: header+flags+portfolio, page 2: compliance+actions+starters)

   ↓

Dashboard Phase:
  - API returns briefing in upcoming-reviews list
  - Paraplanner opens, reviews for accuracy (5 min), marks as reviewed
  - Status: REVIEWED (was AUTO_ASSEMBLED)
  - Advisor can now open and review before 45-minute meeting
```

## Why Zero Dependencies?

**Decision:** No external dependencies beyond Python stdlib + FastAPI (for API only).

**Rationale:**
1. **Dependency Hell Prevention:** Wealth management firms are risk-averse. Zero dependencies = zero CVE risk, zero version conflicts, zero deployment complexity.
2. **Portability:** Runs on any Python 3.11+ environment (desktop, server, cloud, on-prem).
3. **Auditability:** Code can be fully reviewed for compliance/security concerns.
4. **Maintainability:** If a package maintainer abandons a project or adds problematic features, we're unaffected.
5. **Custom Needs:** CSV import configs can be customized without forking a package.

**Implementation Strategy:**
- Use pure dataclasses (built-in to Python 3.7+)
- Use pathlib for cross-platform file handling (built-in)
- Implement JSON serialization manually (handle enums, dates, nested objects)
- Use zipfile for backup export (built-in)
- Use csv.DictReader for CSV parsing (built-in)
- FastAPI is an exception (lightweight, widely used in wealth tech, essential for API)

## Configuration & Customization

### CSV Column Mapping
```python
# Schwab format
config = SchwabPositionConfig()

# Fidelity format
config = FidelityPositionConfig()

# Custom format
from importers.custodial_import import PositionImportConfig
config = PositionImportConfig(
    account_number_col="AcctNum",
    account_type_col="Type",
    custodian_col="Custodian",
    owner_col="AccountOwner",
    balance_col="Balance",
    date_col="AsOfDate",
)
importer.import_positions("custom.csv", config)
```

### Engagement Scoring Weights
```python
from src.engagement_scorer import ScorerConfig

config = ScorerConfig(
    weight_meeting_attendance=0.25,  # Increase importance
    weight_response_time=0.15,
    weight_interaction_frequency=0.15,
    weight_aum_trend=0.25,
    weight_portal_activity=0.10,
    weight_document_compliance=0.10,
    cooling_threshold=50,  # Lower threshold for alerts
    no_contact_alert_days=60,  # Earlier alert
)
scorer = EngagementScorer(config)
```

### Briefing Flag Thresholds
Edit in `src/review_assembler.py`:
- Rebalance drift threshold: currently 5% (line 205)
- Plan staleness: currently 12 months (line 418)
- Compliance expiration: currently 60 days (line 254)

## Testing Strategy

1. **CSV Import Tests:** Run importers on sample data, verify accounts/contacts/goals created correctly
2. **Briefing Generation Tests:** Generate briefings for all sample households, verify flags are accurate
3. **Engagement Scoring Tests:** Score all households, verify composites and risk levels make sense
4. **Persistence Tests:** Save/load households and briefings, verify round-trip fidelity
5. **API Tests:** Call all endpoints, verify responses match expected schemas
6. **Export Tests:** Render all households as Markdown and text, verify readability

## Future Enhancements

1. **Phase 2: Live Integrations**
   - OAuth connections to Schwab/Fidelity APIs (vs. CSV export)
   - Salesforce API for real-time CRM data
   - MoneyGuidePro API for live plan data

2. **Phase 2: Advanced Scoring**
   - Machine learning model for attrition prediction
   - Weighted scoring based on firm's historical data
   - Peer comparison (how does this client compare to similar households?)

3. **Phase 2: NLP for Life Events**
   - Automatic detection of life events from CRM notes
   - Keyword extraction and categorization
   - Suggestion system ("System found possible life event: 'Bob mentioned his daughter graduated' — should we log this?")

4. **Phase 3: Multi-Advisor Support**
   - Role-based access control (advisor sees own households, paraplanner sees all)
   - Activity logging and audit trail
   - Approval workflow (paraplanner → advisor → client)

5. **Phase 3: Advanced Analytics**
   - Trend analysis (which clients' AUM is growing, which declining)
   - Cohort analysis (compare this household to similar tier/profile)
   - Forecasting (project which clients will be at risk next quarter)
