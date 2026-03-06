# Production Readiness Checklist

Assessment of the Review Prep Engine's readiness for production deployment. Items marked `[x]` are implemented in the current codebase. Items marked `[ ]` are not yet implemented and should be addressed before or during production rollout.

---

## Security

### Authentication & Authorization
- [x] Row-Level Security (RLS) enabled on all Supabase tables (households, accounts, positions, briefings, action_items, engagement_scores, meetings, meeting_notes, advisors, audit_logs)
- [x] RLS policies enforce advisor-to-household access scoping (advisors only see their assigned households)
- [x] Role-based access control via `advisor_role` enum (advisor, compliance, admin) with escalated access for compliance and admin roles
- [x] Supabase Auth integration for user identity (`auth.uid()` used in all RLS policies)
- [x] Service role key separated from anon key in environment configuration
- [ ] Multi-factor authentication (MFA) enforcement for advisor accounts
- [ ] Session timeout and idle logout configuration
- [ ] API rate limiting on Supabase REST endpoints
- [ ] OAuth token rotation for Salesforce and custodian API credentials

### Secrets Management
- [x] `.env.example` documents all required secrets with placeholder values
- [x] `.gitignore` excludes `.env` file from version control
- [ ] Secrets stored in a vault (e.g., AWS Secrets Manager, HashiCorp Vault) rather than environment variables
- [ ] Automated secret rotation for API keys (Salesforce, Schwab, Fidelity, SendGrid, Trigger.dev)
- [ ] JWT secret is cryptographically generated (currently placeholder in `.env.example`)

### Data Protection
- [x] SSN field in household_members table is designated as encrypted (`ssn_encrypted TEXT`)
- [x] Briefing renderer marks output as "CONFIDENTIAL - FOR ADVISOR USE ONLY"
- [x] Audit log captures IP address for all actions
- [ ] Encryption at rest for Supabase database (depends on Supabase plan configuration)
- [ ] TLS enforcement for all API connections (Supabase, Salesforce, custodian APIs)
- [ ] PII data masking in application logs (client names, account numbers, SSNs)
- [ ] Data classification labels on database columns containing PII
- [ ] Client data anonymization for non-production environments

### Input Validation
- [x] Zod schema validation on Trigger.dev briefing generation payload (`BriefingGenerationPayloadSchema`)
- [x] CSV importers include try/except error handling with row-level skip on parse failure
- [ ] Input sanitization on all user-facing API endpoints
- [ ] SQL injection prevention audit (n8n workflow string interpolation into Supabase queries)
- [ ] File upload validation for CSV importers (size limits, content type checks)

---

## Reliability

### High Availability & Failover
- [ ] Multi-region Supabase deployment or read replicas
- [ ] n8n workflow engine deployed with redundancy (not a single instance)
- [ ] Trigger.dev job queue with dead-letter queue for failed jobs
- [ ] Health check endpoints for all services (API, n8n, Trigger.dev)
- [ ] Circuit breaker pattern for external API calls (Salesforce, Schwab, Fidelity)

### Data Integrity
- [x] Foreign key constraints with ON DELETE CASCADE/SET NULL/RESTRICT across all Supabase tables
- [x] UNIQUE constraints on critical columns (advisor email, household+custodian_account pair)
- [x] `updated_at` triggers on all mutable tables via `update_timestamp()` function
- [x] UUID primary keys via `uuid_generate_v4()` extension
- [ ] Database migration versioning system (only `001_initial_schema.sql` exists, no migration runner configured)
- [ ] Transactional consistency for multi-table writes (briefing + engagement score + household update)
- [ ] Idempotency enforcement on n8n workflow reruns

### Backup & Recovery
- [x] `JSONStore.backup_data()` creates timestamped ZIP archives of all file-based data
- [x] `JSONStore.export_household_data()` exports complete household data to a single JSON file
- [ ] Automated Supabase database backups on a schedule
- [ ] Point-in-time recovery (PITR) configuration for Supabase
- [ ] Backup verification testing (restore from backup and validate data integrity)
- [ ] Documented disaster recovery runbook with RTO/RPO targets

### Error Handling
- [x] Trigger.dev jobs log errors to `sync_logs` table on failure with error message capture
- [x] n8n workflows configured with `errorHandler: "Continue"` to prevent full workflow abort on node failure
- [x] n8n review reminder workflow sends error alert email to ops team on workflow failure
- [x] Engagement batch job uses `Promise.allSettled` so individual household scoring failures do not block the batch
- [x] CSV importers skip malformed rows with warning output rather than aborting the import
- [ ] Retry logic with exponential backoff for Salesforce and custodian API calls
- [ ] Dead-letter queue for permanently failed jobs
- [ ] Structured error classification (transient vs. permanent failures)

---

## Observability

### Logging
- [x] Trigger.dev structured logging with `logger.info`, `logger.warn`, `logger.error` throughout briefing generation and engagement batch jobs
- [x] Sync completion records written to `sync_logs` table with status, record counts, error messages, and timing metadata
- [x] n8n workflow nodes include descriptive `note` fields documenting their purpose
- [x] LOG_LEVEL environment variable configured (debug, info, warn, error)
- [ ] Centralized log aggregation (ELK, Datadog Logs, or CloudWatch)
- [ ] Structured JSON logging format across all services
- [ ] Request correlation IDs for tracing across n8n -> Trigger.dev -> Supabase

### Metrics
- [x] Engagement batch job reports processing time (`elapsed_ms`), success/failure counts, and cohort distribution
- [x] Sync logs capture `records_processed` and `records_failed` counts
- [x] Dashboard displays firm-wide metrics (total households, AUM, reviews due, overdue action items, compliance issues)
- [ ] Application performance monitoring (APM) integration (Sentry DSN is in `.env.example` but no SDK integration in code)
- [ ] Custom Datadog/Prometheus metrics for briefing generation latency, engagement score distribution, API response times
- [ ] SLA monitoring for CRM sync freshness (alert if `crm_last_sync` exceeds threshold)

### Tracing
- [ ] Distributed tracing across n8n workflows, Trigger.dev jobs, and Supabase queries
- [ ] OpenTelemetry instrumentation
- [ ] Trace context propagation in async job payloads

### Alerting
- [x] Attrition risk alerts generated when engagement score drops below thresholds (email template implemented in `emails/attrition_alert.tsx`)
- [x] At-risk household identification in engagement batch job with compliance officer notification logic
- [x] n8n error alert email sent to ops team on workflow failure
- [ ] PagerDuty or OpsGenie integration for critical alerts
- [ ] Alerting on sync_logs failure rate exceeding threshold
- [ ] Dashboard notification for overdue CRM syncs
- [ ] Alert fatigue management (deduplication, snooze, escalation policies)

---

## Performance

### Caching
- [ ] Supabase query result caching for frequently accessed household profiles
- [ ] Dashboard data caching (firm-wide metrics do not need real-time refresh)
- [ ] Briefing content caching to avoid regeneration on page reload
- [ ] Redis or in-memory cache layer for engagement scores

### Connection Management
- [ ] Database connection pooling configuration for Supabase (PgBouncer settings)
- [ ] HTTP connection reuse for Salesforce and custodian API clients
- [ ] n8n connection pool limits for parallel workflow executions

### Batch Processing
- [x] Engagement batch job processes households in configurable chunks (default batchSize: 100)
- [x] Concurrency limit set on engagement batch job (`concurrencyLimit: 10`)
- [x] Inter-chunk delay (100ms) to avoid rate limiting
- [x] Configurable processing limits via environment variables (`MAX_HOUSEHOLDS_PER_RUN`, `MAX_POSITIONS_PER_ACCOUNT`)
- [ ] Parallel position fetching optimization (currently sequential per account in briefing generation)

### Load Testing
- [ ] Load testing with realistic data volumes (200+ households, 1000+ positions)
- [ ] Performance benchmarks for briefing generation latency
- [ ] Stress testing for batch engagement scoring at scale
- [ ] Database query performance profiling with EXPLAIN ANALYZE on critical queries

### Frontend Performance
- [ ] Dashboard bundle size optimization (React, Recharts are loaded from CDN)
- [ ] Dashboard data pagination for large client books
- [ ] Lazy loading for engagement radar charts and expanded card content

---

## Compliance

### SEC / Regulatory
- [x] Compliance document tracking with expiration dates and renewal periods (IPS, RTQ, ADV Part 2, financial plan, beneficiary designations)
- [x] Compliance status classification (current, expiring_soon, action_required) with automated flag generation
- [x] Briefing flags for expired or missing compliance documents with HIGH severity
- [x] Financial plan staleness detection (flags plans older than 12 months)
- [x] Service tier definitions with review frequency commitments (Platinum: quarterly, Gold: semi-annual, Silver: annual)
- [ ] SEC Rule 206(4)-7 compliance program documentation
- [ ] Automated ADV Part 2 delivery tracking and confirmation
- [ ] Client suitability documentation linked to risk tolerance questionnaire status
- [ ] Regulatory change monitoring and impact assessment process

### Audit Trail
- [x] `audit_logs` table with actor, action, resource type, resource ID, changes (JSONB), IP address, and timestamp
- [x] `sync_logs` table recording every CRM sync, briefing generation, and engagement batch run with status and error details
- [x] Audit log access restricted to admin and compliance roles via RLS policy
- [x] Briefing access tracking (`briefing_accessed`, `briefing_accessed_at` columns)
- [x] Action item status history tracking via `ActionItemTracker` with timestamped transitions
- [ ] Audit log retention policy (7-year minimum for SEC compliance)
- [ ] Audit log tamper protection (append-only, no UPDATE/DELETE policies)
- [ ] Audit report generation tooling for regulatory examinations

### Data Retention
- [ ] Data retention policy defined and documented (client data, briefings, engagement scores, sync logs)
- [ ] Automated data archival for records exceeding retention period
- [ ] Client data deletion workflow for terminated relationships (right to deletion)
- [ ] Engagement score history pruning (currently unbounded growth in `engagement_scores` table)
- [ ] Briefing archival strategy (current `briefings` table grows indefinitely)

### Data Privacy
- [ ] Privacy policy documentation for client data handling
- [ ] Data processing agreement (DPA) template for custodian API integrations
- [ ] CCPA/state privacy law compliance assessment
- [ ] Data inventory mapping (what PII is stored, where, and for how long)
- [ ] Privacy impact assessment for engagement scoring (profiling under privacy regulations)

---

## Deployment

### CI/CD Pipeline
- [x] Dockerfile present for containerized deployment
- [x] Docker Compose configuration for local development
- [x] Vercel deployment configuration (`vercel.json`) for API and dashboard
- [x] Makefile with build targets
- [ ] Automated test suite (unit tests, integration tests) -- no test files present in codebase
- [ ] CI pipeline (GitHub Actions, CircleCI) for automated testing and deployment
- [ ] Linting and type checking in CI (pylint, mypy for Python; ESLint, TypeScript for frontend)
- [ ] Automated security scanning (Snyk, Dependabot for dependency vulnerabilities)

### Deployment Strategy
- [ ] Blue-green or canary deployment configuration
- [ ] Feature flags for gradual rollout (environment variables exist but no runtime flag evaluation)
- [ ] Rollback procedure documented and tested
- [ ] Database migration strategy for zero-downtime deployments
- [ ] Environment parity (development, staging, production) with separate Supabase projects

### Infrastructure as Code
- [ ] Supabase project configuration managed via CLI or Terraform
- [ ] n8n workflow deployment automation (currently manual JSON import)
- [ ] Trigger.dev job deployment automation
- [ ] SendGrid template versioning and deployment

### Monitoring & Operations
- [x] Feature flags defined in `.env.example` for toggling CRM sync, custodian sync, briefing generation, engagement scoring, attrition alerts, and email notifications
- [x] Configurable timeouts for sync and briefing generation (`SYNC_TIMEOUT_SECONDS`, `BRIEFING_TIMEOUT_SECONDS`)
- [x] Email rate limiting configuration (`EMAIL_RATE_LIMIT`)
- [ ] Runbook for common operational scenarios (CRM sync failure, stale data, manual briefing regeneration)
- [ ] On-call rotation and escalation procedures
- [ ] Capacity planning documentation for household growth projections
- [ ] SLA definitions for briefing generation latency and data freshness
