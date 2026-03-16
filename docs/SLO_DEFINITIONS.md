# Review Prep Engine - SLO Definitions

## SLO 1: Preparation Time SLA (Client Satisfaction / Time to Value)
**Target:** 95% of review prep completed within 12 minutes per client
**Error Budget:** 5% of preps taking >12 minutes per week
**Burn rate Alert:** >40% of weekly time budget consumed in 24 hours

### Rationale
The core value is prep time reduction from 45 min → 12 min. A 95% target on 12-minute completion ensures almost all client reviews are prepared in time for advisors to deliver on-call insights (advisor has 30-60 min prep before client call). The 5% error budget accommodates edge cases (unusually complex portfolios, missing data). Missing the 12-minute SLA doesn't ruin the call, but makes advisors less prepared and reduces client value. This is the primary success metric and must be monitored weekly.

### Measurement
- Count: Review prep tasks completed within 12 minutes vs. total prep tasks
- Success: Prep report delivered in <12 minutes from request
- Failure: Prep report takes >12 minutes (queued, data latency, computation delay)
- Burn rate threshold: If >40% of weekly budget in 24 hours, investigate bottleneck (data freshness, compute throughput)

---

## SLO 2: Data Freshness (Preparation Accuracy)
**Target:** 99% of portfolio data in prep reports is current (updated within 24 hours of report generation)
**Error Budget:** 1% of data >24 hours stale per week
**Burn rate Alert:** >40% of weekly freshness budget consumed in 24 hours

### Rationale
Advisors prepare for client calls using portfolio data. If data is stale (>24 hours old), advisors may discuss outdated holdings, values, or risk scores—undermining credibility. A 99% freshness target (data <24 hours old) ensures prep reports reflect nearly-current portfolio state. The 1% error budget allows for occasional data feeds lagging >24 hours without breaking the SLA (e.g., quarterly update delayed). This prevents advisors from being surprised by out-of-date information during calls.

### Measurement
- Count: Portfolio data in prep report timestamp vs. current time (100% of reports)
- Success: Data in report is <24 hours old
- Failure: Data in report is >24 hours old (stale)
- Burn rate threshold: If >40% of weekly budget in 24 hours, check data feed lag (likely market data delay)

---

## SLO 3: Engagement Scoring Accuracy (Advisor Decision Support)
**Target:** 90% of engagement scores match advisor's manual assessment (inter-rater agreement)
**Error Budget:** 10% of scores diverge from advisor judgment per week
**Burn rate Alert:** >30% of weekly accuracy budget sustained >48 hours

### Rationale
Engagement scoring (predicting which clients to contact, which deals to surface) is subjective. The 90% agreement target with advisors' manual assessments ensures the scoring model is trustworthy enough to guide advisor actions (e.g., "prioritize these 5 clients for Q2 reviews"). Lower accuracy (<85%) risks advisors ignoring the system; higher accuracy targets (>95%) are unattainable for subjective judgment. Weekly validation with a sample of advisors keeps the model calibrated.

### Measurement
- Count: Engagement scores assigned by model vs. advisor manual rating on sample (5% of weekly reports)
- Success: Score matches advisor rating (±1 tier, e.g., "High" vs. "Medium")
- Failure: Score diverges significantly (e.g., model says "High", advisor says "Low")
- Burn rate threshold: If >30% of weekly error budget in 48 hours, trigger model retraining on recent advisor feedback

---

## SLO 4: Plaintext Financial Data Exposure Prevention (Security/Compliance)
**Target:** 100% of sensitive financial data (account numbers, SSN, transaction details) are masked/encrypted in all system outputs
**Error Budget:** 0% tolerance for unencrypted PII leakage
**Burn rate Alert:** Any unencrypted PII in production system = incident

### Rationale
Wealth management involves highly sensitive data (client SSNs, account balances, transaction history). GLBA and SOX compliance require encrypted storage and transmission. A 100% masking rate (0% error budget) is mandatory—*any* leak is a compliance violation and brand risk. This is asymmetric: 99% encryption means 1% of sensitive data is exposed, which is unacceptable. Unlike performance SLOs, there's no acceptable error budget.

### Measurement
- Count: Prep reports checked for unencrypted PII (100% of reports)
- Success: All SSNs masked; all account numbers masked; only summary balances shown (not transaction history)
- Failure: Any unencrypted PII found in report output
- Burn rate threshold: Any PII exposure = P1 security incident; immediate escalation

---

## SLO 5: Report Generation Reliability (System Uptime)
**Target:** 99.5% of prep report requests complete successfully (no errors)
**Error Budget:** 0.5% of requests fail per week
**Burn rate Alert:** >50% of weekly failure budget consumed in 24 hours

### Rationale
Advisors rely on prep reports to serve clients. Failed requests (errors, crashes, timeouts) block work and force manual fallbacks. A 99.5% success target ensures almost all requests complete; the 0.5% error budget allows for rare infrastructure hiccups (database connection timeout, service crash). This protects the business from losing advisor productivity due to system failures.

### Measurement
- Count: Successful prep report completions vs. total requests
- Success: Report generated and delivered in <12 minutes
- Failure: Request fails (error returned, timeout after 30s, 500 error)
- Burn rate threshold: If >50% of weekly budget in 24 hours, page SRE; investigate infrastructure

---

## Error Budget Governance
- **Review Cadence:** Daily check on prep time SLA; weekly check on data freshness and engagement accuracy
- **Escalation:** If prep time SLA burns >40% budget by day 3, allocate optimization sprint (likely data latency issue)
- **Data quality audits:** Weekly spot-check of 10 reports; verify data is current and engagement scores reasonable
- **Security validation:** Monthly check for PII exposure; any findings require immediate remediation + root cause
- **Feature freeze:** If data freshness drops <98%, pause new features; focus on data feed reliability

