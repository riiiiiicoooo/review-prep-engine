# Review Prep Engine: Improvements & Technology Roadmap

---

## Product Overview

The Review Prep Engine is an automated briefing assembly platform built for a 12-person Registered Investment Advisory (RIA) firm managing approximately $380M in assets under management (AUM) across ~200 client households. The system replaces a manual, multi-system review preparation workflow that previously consumed 150 hours of paraplanner time per quarter.

The core product does three things:

1. **Unified Client Profiling** -- Aggregates data from Salesforce CRM, Schwab custodian portals, MoneyGuidePro financial planning software, and internal compliance spreadsheets into a single `ClientHousehold` data model. Before this tool, advisors had to mentally stitch together information from four different systems during a 45-minute meeting.

2. **Automated Briefing Assembly** -- The `ReviewAssembler` module constructs advisor-ready briefing documents organized around what has changed since the last review: life events, AUM movement, goal status, compliance expirations, overdue action items, and suggested conversation starters. This reduced per-client prep time from 45 minutes to 12 minutes.

3. **Engagement Scoring & Attrition Detection** -- The `EngagementScorer` uses a composite of 6 weighted signals (meeting attendance, response time, interaction frequency, AUM trend, portal activity, document compliance) to score client engagement health on a 0-100 scale and flag at-risk households before they leave the firm.

Post-deployment results (first two quarters): action item follow-through improved from 59% to 84%, life event coverage became comprehensive, and 8 at-risk client relationships representing $48M in AUM were identified in Q1 alone.

---

## Current Architecture

### Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Core Logic | Python | 3.11+ | Data models (dataclasses), scoring algorithms, briefing assembly |
| API | FastAPI | 0.115.0 | REST endpoints for dashboard and integrations |
| API Server | Uvicorn | 0.30.0 | ASGI server |
| Validation | Pydantic | 2.10.0 | Request/response serialization and type validation |
| Database | Supabase (PostgreSQL) | -- | Relational schema with RLS, audit logging, real-time subscriptions |
| Orchestration | n8n | -- | CRM daily sync (6 AM), review reminder workflows (Monday 8 AM) |
| Async Jobs | Trigger.dev | -- | Briefing generation (<5s per household), nightly engagement batch scoring |
| Email | React Email + SendGrid | -- | Review reminder and attrition alert email templates (TSX) |
| Dashboard | React + Recharts | -- | Advisor-facing dashboard with upcoming reviews, engagement health, client briefings |
| Deployment | Vercel | -- | Edge functions, serverless functions (1GB memory, 60s timeout) |
| Persistence | JSON Store | Custom | Lightweight file-based persistence for local dev and prototype |
| AI/LLM | Claude Haiku | -- | Briefing assembly and engagement scoring (~1.5M tokens/month) |
| MCP | Model Context Protocol | -- | Tool-based interface for briefing generation, client summaries, notes search |

### Key Components

| File | Lines | Purpose |
|------|-------|---------|
| `src/client_profiler.py` | 824 | Core data model: 13 dataclasses, 7 enums, `ClientHousehold` with 20+ computed properties, `ClientBook` for firm-wide queries |
| `src/review_assembler.py` | 822 | Briefing assembly engine: builds sections (household, life events, portfolio, goals, compliance, action items), generates severity-ranked flags, creates conversation starters, formats text output |
| `src/engagement_scorer.py` | 864 | 6-signal engagement scoring with configurable weights, trend detection, attrition risk classification (low/moderate/high/critical), alert generation |
| `api/app.py` | 509 | FastAPI REST API: 6 endpoints, Pydantic models, CORS, startup data loading |
| `storage/json_store.py` | 483 | JSON persistence: dataclass serialization/deserialization, briefing history, action item tracking, backup/export |
| `dashboard/dashboard.jsx` | 738 | React dashboard: 3 tabs (reviews, engagement, briefing), Recharts visualizations, synthetic data |
| `trigger-jobs/briefing_generation.ts` | 639 | Trigger.dev job: fetches Supabase data, computes position deltas, scores engagement, assembles briefing, saves and notifies |
| `export/briefing_renderer.py` | 365 | Multi-format export: Markdown and professional 2-page text layout |
| `mcp/server.py` | 391 | MCP server: 3 tools (generate_briefing, get_client_summary, search_notes) |
| `supabase/migrations/001_initial_schema.sql` | 682 | Full relational schema: 14 tables, RLS policies, analytics views, audit trails |

### Data Flow

```
Salesforce (CRM) ----> n8n CRM Daily Sync (6 AM) ----> Supabase PostgreSQL
Schwab (Custodian) --/                                        |
                                                              |
                                    Trigger.dev Briefing Job <-+-> Trigger.dev Engagement Batch
                                              |                            |
                                              v                            v
                                    Briefings table              Engagement scores table
                                              |                            |
                                    FastAPI REST API <-------- Dashboard (React)
                                              |
                                    React Email (SendGrid) --> Advisor inbox
```

### Design Decisions Worth Noting

- **Zero-dependency core**: The Python core uses only stdlib dataclasses, enums, and pathlib. No ORM, no external NLP libraries. This was a deliberate choice for compliance auditability and deployment simplicity.
- **Configurable weights**: Engagement scoring weights are configurable via `ScorerConfig`, not hardcoded.
- **Pluggable importers**: CSV column mapping uses a config-object pattern (`SchwabPositionConfig`, `FidelityPositionConfig`) for multi-custodian support.
- **Flag severity rules**: Hardcoded in `review_assembler.py` (e.g., 5% drift threshold on line 205, 12-month plan staleness on line 418). These should be configurable.

---

## Recommended Improvements

### 1. Add Automated Testing Suite

**Problem**: There are zero test files in the codebase. No unit tests, no integration tests, no API tests. For a financial services application handling compliance data, this is a critical gap.

**What to do**:

- Add `pytest` (v8.x) and `pytest-asyncio` (v0.24+) to `requirements.txt`
- Create `tests/` directory with the following structure:
  ```
  tests/
    test_client_profiler.py      # Test computed properties, edge cases (zero AUM, missing dates)
    test_engagement_scorer.py    # Test each signal scoring method, composite calculation, alerts
    test_review_assembler.py     # Test flag generation, conversation starters, briefing format
    test_json_store.py           # Test save/load round-trip fidelity, backup/export
    test_api.py                  # Test all 6 endpoints with httpx.AsyncClient
    conftest.py                  # Shared fixtures (sample households, sample books)
  ```
- **Priority targets**: Test the engagement scoring thresholds in `engagement_scorer.py` (lines 182-191) since these directly affect attrition alerts. Test the flag generation logic in `review_assembler.py` (lines 346-441) since incorrect flags could cause advisors to miss compliance items.
- Add `httpx` (v0.27+) for async API testing with FastAPI's `TestClient`.

**Code reference**: The `if __name__ == "__main__"` blocks in `client_profiler.py` (line 616), `engagement_scorer.py` (line 721), and `review_assembler.py` (line 704) contain usage examples that should be converted into formal test cases.

### 2. Extract Hardcoded Configuration into a Settings Module

**Problem**: Thresholds and business rules are scattered across source files:
- Rebalance drift threshold: 5% hardcoded in `client_profiler.py` line 205
- Plan staleness threshold: 12 months in `review_assembler.py` line 418
- Compliance expiration warning: 60 days in `client_profiler.py` line 256
- Service tier AUM bands: hardcoded in docstrings, not enforced
- Engagement level boundaries: lines 182-191 in `engagement_scorer.py`

**What to do**:

- Create `src/config.py` using Pydantic `BaseSettings` (already in the dependency tree via Pydantic v2.10):
  ```python
  from pydantic_settings import BaseSettings

  class ReviewPrepConfig(BaseSettings):
      rebalance_drift_threshold_pct: float = 5.0
      plan_staleness_months: int = 12
      compliance_warning_days: int = 60
      platinum_aum_min: float = 2_000_000
      gold_aum_min: float = 500_000
      # ... engagement thresholds, scoring weights, etc.

      class Config:
          env_prefix = "RPE_"
  ```
- This allows runtime configuration via environment variables (e.g., `RPE_REBALANCE_DRIFT_THRESHOLD_PCT=7.5`) without code changes, which is critical for multi-tenant deployment.

### 3. Replace JSON File Storage with Proper Database Access

**Problem**: `storage/json_store.py` uses file-based JSON persistence. The Supabase schema exists (`001_initial_schema.sql`) but the Python core does not connect to it. The `JSONStore` class has inherent issues: no concurrent access safety, linear-scan engagement lookups (line 332-346), and no transactional guarantees.

**What to do**:

- Add `supabase` Python client (v2.x, `pip install supabase`) to `requirements.txt`
- Create `storage/supabase_store.py` implementing the same interface as `JSONStore` but backed by Supabase PostgREST:
  ```python
  from supabase import create_client, Client

  class SupabaseStore:
      def __init__(self):
          self.client: Client = create_client(
              os.environ["SUPABASE_URL"],
              os.environ["SUPABASE_SERVICE_ROLE_KEY"]
          )

      def save_household(self, household: ClientHousehold) -> str:
          # Upsert to households table
          ...
  ```
- Keep `JSONStore` as a fallback for local development and testing, selected via environment variable.

### 4. Add Structured Logging and Observability

**Problem**: Error handling uses bare `print()` statements (e.g., `json_store.py` lines 60, 222, 244, 286). The API has no request logging, no performance metrics, and no error tracking.

**What to do**:

- Add `structlog` (v24.x) for structured JSON logging throughout the Python codebase
- Add `sentry-sdk[fastapi]` (v2.x) for error tracking and performance monitoring
- Instrument the FastAPI app:
  ```python
  import sentry_sdk
  sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"), traces_sample_rate=0.1)
  ```
- Add request timing middleware to track briefing generation latency (target: <5s per household)
- Replace all `print(f"Error ...")` calls with `logger.error(...)` with structured context

### 5. Migrate Dashboard from Synthetic Data to Live API

**Problem**: `dashboard/dashboard.jsx` uses a hardcoded `CLIENTS` array (lines 33-207) and `FIRM_STATS` object (lines 209-218). The dashboard is entirely static and does not call the FastAPI backend.

**What to do**:

- Add `fetch()` calls to the API endpoints defined in `api/app.py`:
  - `GET /households` for the client list
  - `GET /households/{id}/briefing` for individual briefings
  - `GET /dashboard/upcoming-reviews` for the reviews tab
- Replace inline styles (currently all components use the `style={{...}}` pattern) with a CSS-in-JS solution or Tailwind CSS for maintainability
- Add loading states, error boundaries, and empty states
- Move the dashboard into a proper Next.js or Vite project structure with routing

### 6. Add PDF Briefing Export

**Problem**: `export/briefing_renderer.py` supports Markdown and plain text output. Advisors at RIA firms overwhelmingly prefer PDF for printing and client-facing materials.

**What to do**:

- Add `weasyprint` (v62.x) or `reportlab` (v4.x) for PDF generation
- Extend `BriefingRenderer` with a `render_pdf()` method that produces a branded, printable 2-page PDF
- Add a `GET /households/{id}/briefing/pdf` endpoint to `api/app.py`
- Include the firm's logo, advisor name, confidentiality footer, and page numbers

### 7. Add API Authentication and Rate Limiting

**Problem**: The FastAPI app has `allow_origins=["*"]` CORS (line 44) and no authentication. Any network-accessible client can read all household data.

**What to do**:

- Add JWT authentication using Supabase Auth tokens:
  ```python
  from fastapi import Depends, Security
  from fastapi.security import HTTPBearer

  security = HTTPBearer()

  async def verify_token(credentials = Security(security)):
      # Verify Supabase JWT
      ...
  ```
- Add `slowapi` (v0.1.9+) for rate limiting:
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  ```
- Lock down CORS to the dashboard origin only
- Add API key authentication for the MCP server and n8n webhook calls

### 8. Improve the Engagement Scoring Model

**Problem**: The engagement scoring model in `engagement_scorer.py` uses fixed thresholds and equal-ish weighting across all signals. Several specific issues:

- Portal activity score defaults to 30 for clients with no data (line 467), which may mask truly disengaged clients who simply don't have portal logins tracked.
- The AUM trend signal (lines 394-445) cannot distinguish between market-driven changes and client-initiated flows when `net_flows` is zero.
- The model has no time-decay: a meeting 179 days ago scores the same as one yesterday.

**What to do**:

- Add time-decay weighting to interaction and meeting signals: recent interactions should count more than older ones
- Add a `data_confidence` field to `EngagementReport` that reflects how many signals had sufficient data
- When portal activity data is unavailable, redistribute its weight (10%) across the other 5 signals rather than defaulting to 30
- Track score velocity (rate of change), not just absolute score and single-period trend

### 9. Add CRM Notes NLP Parsing

**Problem**: Identified in `FUTURE_ENHANCEMENTS.md` as item #2. The firm's Salesforce notes are inconsistent, and ~40% of relevant life events logged in CRM notes never surfaced in review briefings because nobody read through months of notes.

**What to do**:

- Use Claude Haiku (already in the budget at $1,200/month) for structured extraction from CRM notes:
  ```python
  prompt = f"""Extract any life events, action items, or client concerns from
  this advisor note. Return structured JSON:
  {{
    "life_events": [{{ "category": "...", "description": "...", "member": "..." }}],
    "action_items": [{{ "description": "...", "assigned_to": "..." }}],
    "concerns": [{{ "topic": "...", "severity": "..." }}]
  }}

  Note: {note_text}"""
  ```
- This is significantly more robust than keyword matching and leverages the existing LLM budget
- Add a `parsed_notes` field to the `Interaction` dataclass to store extracted structured data
- Feed parsed life events into `ClientHousehold.life_events` automatically

### 10. Fix the `@app.on_event("startup")` Deprecation

**Problem**: `api/app.py` line 200 uses `@app.on_event("startup")`, which is deprecated in FastAPI 0.115+. The modern approach uses lifespan context managers.

**What to do**:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_sample_data()
    yield

app = FastAPI(lifespan=lifespan, ...)
```

---

## New Technologies & Trends

### 1. LLM-Powered Briefing Narratives (Claude 3.5 / Claude 4 Opus)

**What**: Instead of assembling briefings as structured data with text formatting, use an LLM to generate natural-language narrative summaries that read like a paraplanner wrote them.

**Why**: The current briefing output (produced by `_format_briefing()` in `review_assembler.py`, lines 505-649) is functional but reads like a report. Advisors at RIA firms prefer narrative context: "Margaret retired in September and Robert's mother passed in October -- this is a household going through significant transitions. The financial plan predates both events and should be priority one."

**How**: Pass the structured briefing data to Claude's API with a system prompt tuned for wealth management language. The existing `ReviewBriefing` dataclass provides all the structured data; the LLM adds the narrative layer.

**Libraries/Tools**:
- Anthropic Python SDK (`anthropic` v0.39+): https://github.com/anthropics/anthropic-sdk-python
- Claude 3.5 Haiku for cost-efficient briefing narratives (~$0.25/1M input tokens, $1.25/1M output tokens)
- Claude 4 Opus for complex scenario analysis when triggered by high-severity flags

**Reference**: Anthropic's tool use documentation shows how to combine structured data extraction with narrative generation. The MCP server (`mcp/server.py`) already has the architecture for this.

### 2. Vector Search for Advisor Notes (pgvector + Embeddings)

**What**: Replace the keyword-based notes search in the MCP server with semantic vector search using embeddings stored in PostgreSQL.

**Why**: The `NotesSearchEngine` in `mcp/server.py` (lines 119-168) does a basic API-proxied search. Advisors need to find notes like "that conversation about the lake house" or "when did Robert mention his brother's business" -- queries that keyword search cannot handle.

**How**: Use `pgvector` extension in Supabase (already supported natively) to store embeddings of CRM notes, then perform similarity search.

**Libraries/Tools**:
- `pgvector` (v0.7+): PostgreSQL vector similarity extension, natively supported in Supabase. https://github.com/pgvector/pgvector
- Anthropic's `voyage-3` embedding model or OpenAI `text-embedding-3-small` for generating note embeddings
- `vecs` (v0.4+): Supabase's Python client for pgvector operations. https://github.com/supabase/vecs

**Schema addition**:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE meeting_notes ADD COLUMN embedding vector(1536);
CREATE INDEX meeting_notes_embedding_idx ON meeting_notes
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

**Estimated cost**: Embedding 10,000 notes ~$0.02 with `text-embedding-3-small`. Negligible.

### 3. Predictive Attrition Modeling (scikit-learn / XGBoost)

**What**: Replace the rule-based attrition risk in `engagement_scorer.py` with a trained ML model that predicts attrition probability.

**Why**: The current system uses fixed thresholds (`_calculate_attrition_risk()`, lines 590-603): score < 20 = critical, score < 40 = high, etc. A trained model can learn firm-specific patterns (e.g., "clients who decrease their 401k contributions and skip one review have a 73% chance of leaving within 6 months").

**How**: Once 2-3 quarters of engagement scoring data exists (labeled with actual attrition events), train a gradient boosted classifier.

**Libraries/Tools**:
- `scikit-learn` (v1.5+): For baseline logistic regression and feature engineering. https://scikit-learn.org
- `xgboost` (v2.1+): For gradient boosted tree models with better handling of tabular financial data. https://xgboost.readthedocs.io
- `shap` (v0.45+): For model interpretability -- critical in financial services where advisors need to understand *why* a client is flagged. https://github.com/shap/shap

**Features to engineer**:
- Score trajectory (slope of last 3 scoring periods)
- Interaction gap variance (inconsistent contact patterns)
- AUM flow direction change (was adding, now withdrawing)
- Tenure-weighted response time (long-tenured clients who slow down are higher risk)

### 4. Real-Time Custodian Data via Plaid or Schwab API

**What**: Replace CSV imports with real-time custodian API connections for automated portfolio data.

**Why**: The current CSV import workflow (`importers/custodial_import.py`) requires a weekly manual export. This introduces staleness and human error. Real-time data would also improve engagement scoring accuracy by detecting large withdrawals (attrition signal) within hours instead of days.

**Libraries/Tools**:
- **Plaid** (Investments API): https://plaid.com/products/investments/ -- Aggregates data across Schwab, Fidelity, Vanguard, and 12,000+ financial institutions. Cost: $500-2,000/month for RIA use.
- **Schwab Advisor API**: Direct connection for firms custodied at Schwab. Requires developer registration (4-8 week approval). OAuth 2.0 authentication.
- **Yodlee** (Envestnet): https://www.yodlee.com -- Enterprise-grade data aggregation used by many wealth management platforms. Higher cost but more comprehensive.

**Implementation**: Add a `importers/api_import.py` module implementing the same interface as `CustodialImporter` but backed by API calls instead of CSV parsing. Use the adapter pattern so the rest of the codebase does not change.

### 5. Workflow Automation with Temporal or Inngest

**What**: Replace n8n workflows and Trigger.dev jobs with a more robust, code-first workflow engine.

**Why**: The current architecture uses n8n (JSON-defined workflows in `n8n/crm_daily_sync.json` and `n8n/review_reminder.json`) combined with Trigger.dev jobs (TypeScript in `trigger-jobs/`). This creates a split between Python business logic and TypeScript job processing. A unified workflow engine would simplify deployment and debugging.

**Libraries/Tools**:
- **Inngest** (v3.x): https://www.inngest.com -- Event-driven, serverless-friendly workflow engine with Python and TypeScript SDKs. Particularly well-suited for Vercel deployments. Built-in retry, rate limiting, and step functions.
  ```python
  import inngest

  @inngest.function(id="generate-briefing", trigger=inngest.TriggerEvent(event="briefing/requested"))
  async def generate_briefing(step, event):
      household = await step.run("fetch-household", fetch_household, event.data["household_id"])
      scores = await step.run("score-engagement", score_engagement, household)
      briefing = await step.run("assemble-briefing", assemble_briefing, household, scores)
      await step.run("notify-advisor", notify_advisor, briefing)
  ```
- **Temporal** (Python SDK v1.7+): https://temporal.io -- More enterprise-grade, supports long-running workflows, replay debugging, and workflow versioning. Better for on-premises deployment. Heavier infrastructure.
- **Hatchet** (v0.40+): https://hatchet.run -- Newer entrant focused on background job orchestration with a Python-native API.

### 6. Modern React Dashboard with Tanstack and Shadcn/UI

**What**: Modernize the dashboard from a single-file JSX component with inline styles to a component-based architecture with a design system.

**Why**: `dashboard/dashboard.jsx` is 738 lines in a single file with all styles inline (e.g., `style={{ padding: "2px 8px", borderRadius: 4, ... }}`). This is unmaintainable at scale. Adding features like real-time updates, filtering, sorting, and role-based views requires a proper component architecture.

**Libraries/Tools**:
- **Shadcn/UI**: https://ui.shadcn.com -- Not a component library but a collection of copy-paste components built on Radix UI primitives. Fully customizable, Tailwind-based. License-free.
- **Tanstack Table** (v8.x): https://tanstack.com/table -- Headless table library for building sortable, filterable, paginated data tables. Ideal for the household list and action items views.
- **Tanstack Query** (v5.x): https://tanstack.com/query -- Server state management for API data fetching, caching, and real-time updates. Replaces manual `fetch()` + `useState()` patterns.
- **Recharts** (v2.x): Already used. Keep it but wrap in reusable chart components.
- **Tailwind CSS** (v3.4+): https://tailwindcss.com -- Utility-first CSS framework. The current `C = { bg: "#fafaf9", ... }` color system maps directly to Tailwind's stone palette.

### 7. Supabase Realtime for Live Dashboard Updates

**What**: Use Supabase's Realtime feature to push updates to the dashboard when briefings are generated, engagement scores change, or action items are completed.

**Why**: Currently, the dashboard requires a page refresh to see new data. When a paraplanner marks a briefing as "reviewed" or an action item is completed, other users do not see the change until they reload.

**How**: Supabase Realtime broadcasts PostgreSQL changes over WebSocket.

```typescript
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

supabase
  .channel('briefings')
  .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'briefings' }, (payload) => {
    // Update dashboard state in real-time
    updateBriefingStatus(payload.new);
  })
  .subscribe();
```

**Reference**: https://supabase.com/docs/guides/realtime

### 8. Compliance Automation with RegTech Tools

**What**: Integrate automated compliance checking for SEC/FINRA requirements using specialized regulatory technology.

**Why**: The current compliance tracking in `client_profiler.py` (`ComplianceDocument` class, lines 237-262) tracks document expiration dates manually. Wealth management compliance requirements evolve frequently, and manual tracking is error-prone.

**Libraries/Tools**:
- **ComplySci / NRS**: Enterprise compliance platforms with APIs for RIA regulatory requirements tracking
- **SmartRIA**: https://www.smartria.com -- Compliance management platform specifically for RIAs. Offers API access for automated compliance status checking.
- Custom approach: Build a compliance rules engine using `pydantic` models that encode SEC/FINRA requirements:
  ```python
  class ComplianceRule(BaseModel):
      rule_id: str
      regulation: str  # "SEC Rule 206(4)-7", "FINRA Rule 3110"
      document_type: DocumentType
      renewal_period_months: int
      grace_period_days: int
      auto_escalate: bool
  ```

### 9. Meeting Transcription and Action Item Extraction

**What**: Use AI meeting transcription to automatically extract action items, life events, and discussion topics from review meetings.

**Why**: The current system relies on advisors manually entering action items post-meeting into the `ActionItem` dataclass. The README notes that 41% of action items were never followed up on pre-deployment. Automatic extraction from meeting recordings would capture everything discussed.

**Libraries/Tools**:
- **AssemblyAI** (v0.35+): https://www.assemblyai.com -- Speech-to-text with built-in summarization, entity detection, and action item extraction. Has a Python SDK (`assemblyai`). Cost: $0.37/hour of audio.
- **Deepgram** (v3.x): https://deepgram.com -- Real-time transcription with speaker diarization (important for identifying which household member said what). Python SDK: `deepgram-sdk`. Cost: $0.0043/minute.
- **Fireflies.ai**: https://fireflies.ai -- Meeting recording and transcription with built-in action item detection and CRM integration (supports Salesforce).

**Integration point**: Add a `POST /meetings/{id}/transcription` endpoint that accepts audio, transcribes it, extracts action items using Claude, and populates the `ActionItem` records automatically.

### 10. Multi-Tenant Architecture for Productization

**What**: Restructure the application for multi-tenant SaaS deployment to serve multiple RIA firms.

**Why**: The README notes the product could be priced at $500-1,500/month targeting $3-5M ARR at 400 firms. The current codebase is single-tenant (one firm's data, one set of configurations).

**How**: The Supabase schema already includes `organization_id` in all tables and RLS policies enforce advisor-level data segregation. The remaining work is:
- Add organization-level configuration (scoring weights, flag thresholds, branding)
- Add onboarding workflow for new firms (CRM connection setup, custodian API authorization)
- Implement organization-scoped API keys
- Add billing integration (Stripe Billing for subscription management)

**Libraries/Tools**:
- `stripe` Python SDK (v10.x): https://github.com/stripe/stripe-python -- For subscription billing, usage metering, and invoicing
- Supabase multi-tenant patterns using RLS with `organization_id` (already partially implemented in the schema)

---

## Priority Roadmap

### P0 -- Critical (Do Immediately)

| # | Improvement | Effort | Impact | Reference |
|---|------------|--------|--------|-----------|
| 1 | **Add automated test suite** | 1-2 weeks | Prevents regressions in financial calculations, compliance flag logic, and engagement scoring. Zero tests in a compliance-regulated application is a liability. | Section 1 |
| 2 | **Fix API authentication** | 3-5 days | The API currently exposes all client financial data with no authentication (`allow_origins=["*"]`). This is a security vulnerability. | Section 7 |
| 3 | **Fix `@app.on_event("startup")` deprecation** | 1 hour | FastAPI 0.115+ deprecation. Simple fix, prevents future breakage. | Section 10 |
| 4 | **Add structured logging** | 2-3 days | Replace `print()` error handling with structured logging. Essential for debugging production issues. | Section 4 |

### P1 -- High Priority (Next Sprint)

| # | Improvement | Effort | Impact | Reference |
|---|------------|--------|--------|-----------|
| 5 | **Extract configuration into settings module** | 2-3 days | Enables per-firm customization of thresholds without code changes. Unblocks multi-tenant deployment. | Section 2 |
| 6 | **Connect dashboard to live API** | 1-2 weeks | The dashboard is currently a static prototype. Must use real API data to be production-ready. | Section 5 |
| 7 | **CRM notes NLP parsing with Claude** | 1-2 weeks | Catches the 40% of life events buried in Salesforce notes. Uses existing LLM budget. | Section 9 |
| 8 | **Replace JSON storage with Supabase client** | 1 week | Enables concurrent access, proper queries, and transactional guarantees. Schema already exists. | Section 3 |

### P2 -- Medium Priority (Next Quarter)

| # | Improvement | Effort | Impact | Reference |
|---|------------|--------|--------|-----------|
| 9 | **Add PDF briefing export** | 1 week | Advisors need printable briefings for meetings. | Section 6 |
| 10 | **LLM-powered briefing narratives** | 2 weeks | Transforms data reports into advisor-friendly prose. | New Tech #1 |
| 11 | **Vector search for advisor notes** | 2 weeks | Enables semantic search across years of meeting notes. | New Tech #2 |
| 12 | **Engagement scoring improvements** (time-decay, confidence, velocity) | 1-2 weeks | More accurate attrition detection with fewer false positives. | Section 8 |
| 13 | **Modern dashboard with Shadcn/UI + Tanstack** | 3-4 weeks | Scalable component architecture for adding features. | New Tech #6 |
| 14 | **Supabase Realtime for live dashboard** | 1 week | Eliminates manual refresh, improves multi-user workflow. | New Tech #7 |

### P3 -- Strategic (Next 6 Months)

| # | Improvement | Effort | Impact | Reference |
|---|------------|--------|--------|-----------|
| 15 | **Predictive attrition modeling** | 4-6 weeks | ML-based prediction vs. rule-based thresholds. Requires 2-3 quarters of scoring data first. | New Tech #3 |
| 16 | **Real-time custodian API integration** | 4-6 weeks | Eliminates manual CSV exports. Enables same-day detection of large withdrawals. Requires Schwab/Plaid API approval. | New Tech #4 |
| 17 | **Meeting transcription and auto-extraction** | 3-4 weeks | Automatically captures action items from meeting recordings. | New Tech #9 |
| 18 | **Workflow consolidation** (Inngest or Temporal) | 2-3 weeks | Unifies n8n + Trigger.dev into a single code-first workflow engine. | New Tech #5 |
| 19 | **Compliance automation** | 4-6 weeks | Encodes SEC/FINRA rules as configurable policies. | New Tech #8 |
| 20 | **Multi-tenant SaaS architecture** | 6-8 weeks | Productization for $3-5M ARR at 400 RIA firms. | New Tech #10 |

---

## Implementation Notes

### Dependency Additions for P0-P1

Add to `requirements.txt`:

```
# Testing
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.27.2

# Logging & Monitoring
structlog==24.4.0
sentry-sdk[fastapi]==2.19.2

# Configuration
pydantic-settings==2.7.1

# Database
supabase==2.11.0

# LLM (for CRM notes parsing)
anthropic==0.39.0
```

### Key Code Changes for P0

1. **`api/app.py` line 200**: Replace `@app.on_event("startup")` with lifespan context manager
2. **`api/app.py` line 44**: Change `allow_origins=["*"]` to the dashboard URL
3. **`api/app.py`**: Add JWT verification dependency to all endpoints
4. **`storage/json_store.py`**: Replace all `print(f"Error ...")` with `logger.error(...)`
5. **`src/engagement_scorer.py` line 850**: Replace emoji in alert output with text-based severity indicators

### Metrics to Track

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Review prep time per client | 12 min | 8 min | Paraplanner survey |
| Action item follow-through | 84% | 92% | `action_items` table completion rate |
| Life event coverage | ~60% | 95% | Compare CRM notes parsed vs. briefing events |
| At-risk client detection lead time | Unknown | 90 days before attrition | Retroactive analysis |
| Briefing generation latency | <5s | <3s | API endpoint timing |
| Engagement scoring accuracy | Rule-based | F1 > 0.80 | ML model evaluation (P3) |
| API response time (p95) | Unknown | <500ms | Sentry performance monitoring |

---

*Document generated from code analysis of the review-prep-engine repository. All file paths and line numbers reference the current codebase.*
