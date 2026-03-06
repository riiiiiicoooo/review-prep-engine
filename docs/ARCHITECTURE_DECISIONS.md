# Architecture Decision Records

Technical decisions made during the design and implementation of the Review Prep Engine. Each ADR captures the context, rationale, alternatives considered, and consequences of a significant architectural choice.

---

## ADR-001: Unified Client Profile via Dataclasses (No ORM, No Database Dependencies in Core)

**Status:** Accepted
**Date:** 2024-11
**Context:** Client data lived in four separate systems: Salesforce (contacts, notes, meeting history), Black Diamond/Schwab (portfolio performance, holdings, balances), MoneyGuidePro (financial plans, goals, projections), and a compliance spreadsheet (IPS dates, risk tolerance, ADV delivery). Advisors had to mentally stitch together information from all four systems during meetings. The firm's infrastructure is Salesforce plus cloud apps plus a shared drive -- there is no internal database server or ORM available in the environment where this module runs.
**Decision:** Model the entire client household as a hierarchy of Python dataclasses (`ClientHousehold` as the root, containing `HouseholdMember`, `Account`, `PerformanceSnapshot`, `AssetAllocation`, `LifeEvent`, `FinancialGoal`, `ComplianceDocument`, `ActionItem`, `ReviewRecord`, and `Interaction`). The core modules (`client_profiler`, `engagement_scorer`, `review_assembler`) have zero database or ORM dependencies. They operate purely on in-memory dataclass instances.
**Alternatives Considered:**
- SQLAlchemy ORM with a PostgreSQL schema mirroring the Supabase tables. Rejected because the core logic needs to run in environments without direct database access (CSV import scripts, local advisor machines, CI pipelines).
- Pydantic models. Considered for validation, but dataclasses were chosen for simplicity and zero external dependencies in the core modules. The `dataclasses.asdict()` integration made JSON serialization straightforward.
- A monolithic class with nested dicts. Rejected for lack of type safety and poor readability. The enum-based status tracking (`GoalStatus`, `ActionItemStatus`, `ServiceTier`) provides compile-time clarity.
**Consequences:**
- The core engine is fully testable without any database or network mocking.
- Importers (`custodial_import`, `crm_import`, `planning_import`) act as adapters that translate CSV data into dataclass instances, cleanly separating data ingestion from business logic.
- The `JSONStore` layer in `storage/json_store.py` handles serialization separately, meaning persistence strategy can change without touching scoring or assembly logic.
- Trade-off: computed properties (e.g., `total_aum`, `aum_change_pct`, `compliance_status`) are recalculated on every access rather than cached, which is acceptable for the current household-level scale but would need optimization for book-level aggregations exceeding thousands of households.

---

## ADR-002: Weighted Composite Engagement Scoring with Six Configurable Signals

**Status:** Accepted
**Date:** 2024-12
**Context:** The firm lost three clients in Q4 2025 with no warning. In each case, the disengagement pattern was visible in retrospect: fewer portal logins, skipped reviews, unanswered emails, declining AUM. There was no system to aggregate these signals. The team needed a quantitative score that could trigger proactive outreach before a client was already talking to another firm.
**Decision:** Implement a composite engagement score (0-100) built from six weighted signals: meeting attendance (20%), response time (20%), AUM trend (20%), interaction frequency (15%), document compliance (15%), and portal activity (10%). Weights are configurable via a `ScorerConfig` dataclass. The scorer classifies clients into five engagement levels (Strong >= 80, Healthy >= 60, Cooling >= 40, At Risk >= 20, Disengaged < 20) and calculates attrition risk as a separate categorical output (low, moderate, high, critical) that factors in both the score and its trend direction.
**Alternatives Considered:**
- A simple threshold system (e.g., "if no contact in 90 days, flag as at-risk"). Rejected because it misses compound signals -- a client can have recent contact but still be disengaging through AUM outflows and skipped reviews.
- Machine learning model trained on historical churn data. Rejected because the firm has too few churn events (three clients) for statistical training data, and a weighted heuristic is transparent and explainable to compliance officers and advisors.
- Equal weighting across all signals. Rejected because meeting attendance and response time are stronger predictors of engagement than portal logins, based on advisor feedback.
**Consequences:**
- The weighted approach produces actionable scores immediately without historical training data.
- The `ScorerConfig` allows individual firms to tune weights based on their client base (e.g., firms with older clients might reduce portal activity weight).
- The scorer generates specific `EngagementAlert` objects when scores decline beyond configurable thresholds (15% drop triggers a warning, 25% drop triggers a critical alert), which feed into the attrition alert email workflow.
- Trade-off: the score can be gamed by advisors (e.g., logging superficial interactions to boost frequency). Mitigation depends on CRM data integrity rather than the scoring algorithm itself.
- The `score_book()` method enables batch scoring of all clients, sorting by score ascending so the most at-risk clients surface first.

---

## ADR-003: Delta-Oriented Briefing Assembly Pipeline

**Status:** Accepted
**Date:** 2024-12
**Context:** Review prep was taking paraplanners 45 minutes per client. They were manually copying data from four systems into a Word document. Advisors said they did not need a full data dump -- they needed to know what changed since the last review and what needs their attention. The briefing should be organized in the order advisors actually run meetings: context, changes, portfolio, compliance, action items, conversation starters.
**Decision:** The `ReviewAssembler` produces a `ReviewBriefing` dataclass through a multi-section pipeline: `_build_household_context` -> `_build_life_events` (filtered to events since last review) -> `_build_portfolio_summary` (with drift analysis and rebalance flagging) -> `_build_goals` -> `_build_compliance` -> `_build_action_items` (excluding completed/cancelled) -> `_generate_conversation_starters` -> `_generate_flags`. Flags are severity-sorted (HIGH first) and categorized by source (life_event, compliance, action_item, performance, goal). The assembler also generates natural-language conversation starters based on life events and at-risk goals.
**Alternatives Considered:**
- A template-based approach where each section is a Jinja2 template filled with raw data. Rejected because the flag generation logic requires cross-section analysis (e.g., a stale financial plan flag requires checking life events against plan dates) that does not fit a simple template fill.
- An LLM-generated narrative summary. Considered for conversation starters but rejected for the full briefing because compliance requires deterministic, auditable output. The firm needs to know exactly what data is surfaced and why.
- A single flat report without prioritization. Rejected because advisors consistently said they scan for "what's urgent" first and only read details if flagged.
**Consequences:**
- The `BriefingStatus` enum tracks the briefing lifecycle: NOT_STARTED -> AUTO_ASSEMBLED -> REVIEWED (paraplanner verified) -> APPROVED (advisor signed off) -> MEETING_COMPLETE. This gives the prep dashboard visibility into which briefings still need human review.
- The `assemble_upcoming()` method batch-assembles briefings for all reviews due within a configurable window, combining overdue and upcoming reviews with deduplication.
- The `_format_briefing()` method produces a plain-text document that can be printed or emailed. The `BriefingRenderer` in `export/briefing_renderer.py` adds Markdown and professional text format outputs.
- Trade-off: conversation starters are rule-based (mapping life event categories to prompt templates) rather than contextually generated. This limits their naturalness but ensures they are always appropriate and never hallucinated.

---

## ADR-004: JSON File Storage as the Primary Persistence Layer

**Status:** Accepted
**Date:** 2024-11
**Context:** The core engine needed to persist household profiles, briefings, and engagement data without requiring the firm to set up a database. The target deployment environment ranged from a shared drive to a cloud function. The Supabase schema exists for the production deployment path (via n8n workflows and Trigger.dev jobs), but the Python core modules needed a persistence layer that works standalone.
**Decision:** Implement `JSONStore` in `storage/json_store.py` as a file-based persistence layer. It organizes data hierarchically: `data/households/{household_id}/profile.json` for client profiles and `data/households/{household_id}/briefings/{date}.json` for briefings. A custom `EnumEncoder` handles serialization of Python enums and dates. `BriefingHistory` provides lookup and listing of historical briefings. `ActionItemTracker` maintains an in-memory status history log for action items with timestamped transitions.
**Alternatives Considered:**
- SQLite as the local persistence layer. Would have provided query capabilities but adds a dependency and makes the data less inspectable. JSON files can be opened, diffed, and version-controlled directly.
- Direct Supabase integration in the Python modules. Rejected to avoid coupling the core logic to a specific cloud provider. The Supabase integration happens through the n8n workflow layer and Trigger.dev jobs, which call the Supabase REST API directly.
- Pickle serialization. Rejected for security reasons (arbitrary code execution) and because the data needs to be human-readable for debugging and compliance review.
**Consequences:**
- Data is portable: a `backup_data()` method creates ZIP archives, and `export_household_data()` consolidates a household's profile, briefings, and engagement data into a single JSON file.
- The `dataclass_to_dict` and `dict_to_dataclass` utility functions handle the full round-trip including nested dataclasses, enums, dates, and optional fields. This is non-trivial and required explicit type introspection.
- Trade-off: no query capability. Finding all households with a specific engagement level requires loading every profile file. This is acceptable at the scale of a single advisory firm (typically 100-500 households) but would not scale to an enterprise multi-tenant deployment.
- The Supabase schema (`supabase/migrations/001_initial_schema.sql`) provides the production query layer with proper indexes, RLS policies, and analytics views for the dashboard and API.

---

## ADR-005: Review Scheduling Based on Service Tier with Urgency Cascades

**Status:** Accepted
**Date:** 2024-11
**Context:** The firm had no systematic method for determining which clients needed reviews and when. Platinum clients (AUM > $2M) expected quarterly reviews, Gold clients ($500K-$2M) expected semi-annual reviews, and Silver clients (< $500K) expected annual reviews. Reviews were tracked informally and frequently missed or scheduled too late for proper prep.
**Decision:** Encode review frequency directly into the `ServiceTier` enum and `ClientHousehold` model. The `review_prep_urgency` property returns a cascade of urgency levels: "overdue" (past due), "this_week" (<= 7 days), "next_week" (<= 14 days), "this_month" (<= 30 days), "upcoming" (> 30 days), or "unscheduled". The `ClientBook` class provides `list_reviews_due(within_days)` and `list_overdue_reviews()` for batch filtering. The engagement scorer penalizes missed reviews as a signal, and the review assembler's `assemble_upcoming()` method combines overdue and upcoming reviews into a single prioritized queue.
**Alternatives Considered:**
- A separate scheduling service or calendar integration. Deferred as a future enhancement because the firm currently manages scheduling through Salesforce and email. The engine surfaces urgency; it does not own the calendar.
- Dynamic review frequency based on engagement score (e.g., at-risk clients get more frequent reviews). Discussed but deferred to avoid changing the service agreement without client consent. The current approach respects the service tier commitment.
- Fixed calendar dates (e.g., "first week of Q1"). Rejected because it does not account for rescheduled or ad-hoc reviews, and the rolling urgency window is more operationally useful.
**Consequences:**
- The n8n review reminder workflow (`n8n/review_reminder.json`) queries Supabase for households with `next_review_date` within the next 7 days every Monday at 8 AM, triggering briefing generation and advisor email notifications.
- The dashboard (`dashboard/dashboard.jsx`) sorts clients by `nextReviewDays` in the Upcoming Reviews tab, visually highlighting overdue (red border) and this-week (amber border) reviews.
- Trade-off: the `next_review_date` must be maintained externally (via CRM sync or manual update). The engine reads it but does not compute it. If the CRM sync fails, review dates become stale.

---

## ADR-006: Multi-Layer Architecture with n8n Orchestration and Trigger.dev Async Jobs

**Status:** Accepted
**Date:** 2025-01
**Context:** The production deployment needed to coordinate data flow between Salesforce (CRM), Schwab/Fidelity (custodians), Supabase (database), and the Python scoring engine. The team did not have backend engineering bandwidth to build a custom orchestration layer. The chosen approach needed to be maintainable by a paraplanner or operations manager, not just developers.
**Decision:** Use n8n for workflow orchestration (daily CRM sync, weekly review reminders) and Trigger.dev for async compute jobs (briefing generation, batch engagement scoring). The n8n workflows are JSON-defined and run on a schedule (daily at 6 AM for CRM sync, Monday at 8 AM for review reminders). They handle Salesforce SOQL queries, Supabase upserts, custodian API calls, position change detection, and email notifications via SendGrid. Trigger.dev jobs handle the compute-intensive work: multi-step briefing generation (10-step pipeline in `briefing_generation.ts`) and batch engagement scoring across all households (`engagement_batch.ts`).
**Alternatives Considered:**
- A monolithic Python service with cron jobs. Rejected because it couples scheduling, data fetching, business logic, and notification delivery into a single process. Failures in one step would block all downstream steps.
- AWS Step Functions or Temporal for orchestration. More robust but significantly more complex to set up and maintain. n8n's visual workflow editor makes the data flow visible to non-developers.
- Supabase Edge Functions for all compute. Rejected because briefing generation involves multiple sequential database queries and is better suited to a long-running job with logging and retry support.
**Consequences:**
- The n8n CRM daily sync workflow has 16 nodes handling the full Salesforce-to-Supabase pipeline including position change detection and conditional briefing trigger.
- Trigger.dev provides structured logging (`logger.info`, `logger.warn`, `logger.error`) and writes to `sync_logs` for audit trail on both success and failure.
- The engagement batch job processes households in configurable chunks (default 100) with `Promise.allSettled` for fault tolerance -- individual household failures do not block the batch.
- Email templates (`emails/review_reminder.tsx`, `emails/attrition_alert.tsx`) use React Email for type-safe, styled HTML emails with briefing status badges and risk factor lists.
- Trade-off: this architecture has more moving parts (n8n, Trigger.dev, Supabase, SendGrid) than a monolithic approach. Each component is a potential point of failure. Mitigation comes through the sync_logs audit trail and error alerting to the ops email.
