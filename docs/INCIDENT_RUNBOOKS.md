# Review Prep Engine - Incident Runbooks

---

## Incident 1: Plaintext Financial Data Exposure in Prep Report

### Context
On March 15, an advisor requests a prep report for a VIP client. The system generates the report successfully, but—due to a bug in the masking logic—the report contains the client's full SSN (123-45-6789) and account number (ACC-012345678) in plaintext. The advisor prints the report and leaves it on their desk. A cleaner finds the document and alerts compliance.

### Detection
- **Alert:** Manual discovery OR automated PII scan detects unmasked data in system outputs
- **Symptoms:**
  - Compliance finds unmasked SSN/account number in physical report
  - Audit logs show report was generated with PII exposure
  - System didn't flag the issue (masking validation failed)

### Diagnosis (30 minutes)

**Step 1: Validate PII exposure**
```sql
-- Check if masking logic was applied
SELECT
  prep_report_id,
  client_ssn,
  client_account_number,
  created_at,
  masked_flag
FROM prep_reports
WHERE created_at >= NOW() - INTERVAL 1 DAY
  AND masked_flag = FALSE;

-- Result: Report #12345 has masked_flag=FALSE (BUG!)
-- SSN: 123-45-6789 (UNMASKED)
-- Account: ACC-012345678 (UNMASKED)
```

**Step 2: Identify root cause**
```python
# Review masking logic
# File: report_generator.py, function: mask_pii()

def mask_pii(data):
    if data.get('client_type') == 'VIP':
        # BUG: Return unmasked data for VIPs (debugging code left in!)
        return data
    else:
        # Mask SSN and account numbers
        data['ssn'] = 'XXX-XX-' + data['ssn'][-4:]
        data['account'] = 'ACC-XXXX-' + data['account'][-4:]
        return data

# The condition for VIP clients was never masked due to debug code!
```

**Step 3: Scope the exposure**
```sql
-- Find all reports generated with masked_flag=FALSE
SELECT
  COUNT(*) as affected_reports,
  COUNT(DISTINCT advisor_id) as advisors_affected,
  COUNT(DISTINCT client_id) as clients_affected,
  MIN(created_at) as earliest_exposure
FROM prep_reports
WHERE masked_flag = FALSE;

-- Result: 12 reports affected (past 2 weeks)
--         5 advisors
--         8 clients
--         Earliest: March 1
```

### Remediation

**Immediate (0-10 min): Contain the breach**
1. **Disable report generation** (until masking is fixed):
   ```bash
   kubectl set env deployment/report-generator PAUSE_GENERATION=true
   ```

2. **Identify and collect exposed reports:**
   ```sql
   -- List all exposed reports
   SELECT prep_report_id, advisor_id, client_id, created_at
   FROM prep_reports
   WHERE masked_flag = FALSE
   ORDER BY created_at DESC;
   ```

3. **Alert affected advisors:**
   ```python
   for report in exposed_reports:
       send_alert_to_advisor(
           advisor_id=report.advisor_id,
           message=f"PII exposure in report {report.id}. Please secure physical copies and contact compliance."
       )
   ```

**Short-term (10-30 min): Fix masking logic**
```python
# Remove VIP exemption (dangerous debug code)
def mask_pii(data):
    # ALWAYS mask SSN and account numbers (no exceptions)
    data['ssn'] = 'XXX-XX-' + data['ssn'][-4:]
    data['account'] = 'ACC-XXXX-' + data['account'][-4:]
    data['balance'] = '$XXX,XXX.XX'  # Also mask balances
    return data

# Add validation
def validate_report_pii(report_data):
    # Check for unmasked patterns
    if re.search(r'\d{3}-\d{2}-\d{4}', report_data):  # SSN pattern
        raise ValueError("Unmasked SSN detected!")
    if re.search(r'ACC-\d{9}', report_data):  # Account pattern
        raise ValueError("Unmasked account number detected!")
    return True
```

**Root cause remediation (1-2 hours):**

1. **Add automated PII scanning to report generation:**
   ```python
   def generate_report(prep_request):
       report = assemble_report(prep_request)

       # Validate no PII in output
       pii_scan = scan_for_pii(report.content)
       if pii_scan.found_pii:
           alert.critical(f"PII found in report: {pii_scan.patterns}")
           raise ValueError("Report generation failed: PII exposure detected")

       return report
   ```

2. **Update testing to explicitly check for PII:**
   ```python
   # Test: Ensure SSN/account numbers are always masked
   def test_ssn_masking():
       test_report = generate_report(client_with_ssn='123-45-6789')
       assert 'XXX-XX-6789' in test_report.content
       assert '123-45-6789' not in test_report.content

   def test_account_masking():
       test_report = generate_report(account='ACC-012345678')
       assert 'ACC-XXXX-5678' in test_report.content
       assert '012345678' not in test_report.content
   ```

3. **Implement PII masking in database layer:**
   ```sql
   -- Create view that automatically masks PII
   CREATE VIEW clients_masked AS
   SELECT
     id,
     name,
     'XXX-XX-' || SUBSTR(ssn, -4) as ssn_masked,
     'ACC-XXXX-' || SUBSTR(account, -4) as account_masked
   FROM clients;

   -- Use this view in reports (ensures masking at source)
   ```

4. **Compliance validation before report delivery:**
   ```python
   def final_pii_check_before_delivery(report):
       # Scan report for any PII patterns one final time
       if has_pii(report):
           notify_compliance()
           don_not_deliver_report()
           raise ComplianceError("PII found; report blocked")

       return True  # Safe to deliver
   ```

**Re-enable report generation:**
```bash
kubectl set env deployment/report-generator PAUSE_GENERATION=false
```

### Communication Template

**Internal (Slack #security-incidents)**
```
CRITICAL: PII Exposure in Prep Reports
Severity: P1 (Compliance Violation + Regulatory Risk)
Duration: March 1-15 (identified March 15)
Affected: 12 reports, 8 clients, 5 advisors

Root Cause: Masking logic had debug code that exempted VIP clients from PII masking (SSN, account numbers exposed).

Actions:
1. Immediately paused report generation
2. Removed VIP exemption from masking logic
3. Fixed all 12 exposed reports (deleted and regenerated with masking)
4. Added automated PII scanning to prevent recurrence
5. Notified all affected advisors and clients

Resolution: Reports redeployed with masking validation by 14:30 UTC.

Next: Legal/Compliance will conduct breach notification assessment.

Assigned to: [SECURITY_LEAD], [COMPLIANCE]
```

**Regulatory Notification (Email to Compliance Officer)**
```
Subject: Data Security Incident - PII Exposure in Prep Reports

We identified an unintended exposure of personally identifiable information (SSN, account numbers) in 12 client prep reports generated between March 1-15, 2026.

Scope: 8 clients affected; 12 reports contained unmasked PII; ~24 physical copies distributed to 5 advisors.

Root Cause: Software bug in data masking function (debug code exempted certain client types).

Remediation:
- All affected reports have been regenerated with proper masking
- Masking logic updated and tested
- Automated PII validation added to prevent recurrence
- Physical reports collected from advisors

Risk Assessment: Low (only internal advisors and compliance staff had access; no client-facing systems impacted; no evidence of unauthorized access).

Next Steps: Legal to assess breach notification requirements under GLBA/state laws.

Incident Timeline: Mar 1-15 (occurrence), Mar 15 10:00 (detected), Mar 15 14:30 (remediated).
```

### Postmortem Questions
1. Why was debug code left in production (VIP exemption)?
2. Why didn't automated PII scanning catch this?
3. Should we implement mandatory code review for masking logic?

---

## Incident 2: Data Freshness SLA Miss (Stale Portfolio Data)

### Context
On March 16 at 9 AM, a wealth advisor prepares a client review using the Review Prep Engine. The report shows the client's portfolio with data from March 13 (3 days stale). The client has made significant rebalancing trades on March 14-16, but the prep report doesn't reflect them. The advisor discusses Q1 performance based on outdated holdings; the client is confused and frustrated.

### Detection
- **Alert:** Data freshness monitoring detects >1% of data >24 hours old, OR manual advisor complaint
- **Symptoms:**
  - Prep report data timestamp shows March 13
  - Current date is March 16 (72+ hours stale)
  - Data freshness monitoring shows <97% (below 99% SLA)

### Diagnosis (15 minutes)

**Step 1: Identify stale data source**
```sql
-- Check data freshness
SELECT
  data_source,
  MAX(data_timestamp) as latest_data,
  NOW() - MAX(data_timestamp) as age_hours,
  COUNT(*) as record_count
FROM portfolio_data_audit
WHERE created_at >= NOW() - INTERVAL 7 DAYS
GROUP BY data_source
ORDER BY age_hours DESC;

-- Result:
-- portfolio_system: Latest March 13 14:00 UTC (48+ hours old)
-- market_feeds: Latest March 16 08:00 UTC (fresh)
-- risk_models: Latest March 15 17:00 UTC (16+ hours old)
```

**Step 2: Identify root cause**
```bash
# Check data pipeline logs
tail -200 /var/log/airflow/portfolio_system_sync.log

# Output:
# 2026-03-14 09:00:00 Starting portfolio data sync
# 2026-03-14 09:15:00 API connection timeout (no response)
# 2026-03-14 09:30:00 Retrying... timeout again
# 2026-03-14 10:00:00 Giving up; no new data available
# 2026-03-15 09:00:00 Starting sync... still timing out
# 2026-03-16 09:00:00 Sync still failing; using stale data

# Root cause: Portfolio system API is down!
```

**Step 3: Verify impact**
```sql
-- How many reports were generated with stale data?
SELECT
  COUNT(*) as stale_reports,
  COUNT(DISTINCT advisor_id) as advisors_affected,
  COUNT(DISTINCT client_id) as clients_affected
FROM prep_reports
WHERE portfolio_data_timestamp < NOW() - INTERVAL 24 HOURS
  AND created_at >= NOW() - INTERVAL 3 DAYS;

-- Result: 142 stale reports generated
```

### Remediation

**Immediate (0-5 min): Alert advisors**
```python
# Send urgent alert to all advisors with stale reports
alert_advisors(
    subject="Portfolio Data Alert: Please refresh reports",
    message="""
    Recent prep reports contain portfolio data from March 13 (now 3 days old).
    Client trades on March 14-16 are NOT included.

    Please regenerate reports NOW to get current data.
    """,
    severity="HIGH"
)
```

**Short-term (5-30 min): Restore data pipeline**
```bash
# Check portfolio system API status
curl -I https://portfolio-api.internal/health
# Response: 503 Service Unavailable

# Contact portfolio system team
# Status: API database is down; estimated recovery 30 min

# Temporary workaround: Use cached portfolio data (24h old, not stale but not ideal)
kubectl set env deployment/data-pipeline \
  USE_CACHED_PORTFOLIO=true \
  CACHE_MAX_AGE_HOURS=48
```

**Root cause remediation (30 min - 2 hours):**

1. **Add alerting for data pipeline failures:**
   ```python
   def monitor_data_freshness():
       for source in ['portfolio_system', 'market_feeds', 'risk_models']:
           last_sync = get_last_successful_sync(source)
           age_hours = (now() - last_sync).total_seconds() / 3600

           if age_hours > 24:
               alert.error(f"{source} data is stale ({age_hours}h old)")
           if age_hours > 12:
               alert.warn(f"{source} data is getting stale ({age_hours}h old)")
   ```

2. **Implement circuit breaker for data pipeline:**
   ```python
   @circuit_breaker(
       failure_threshold=3,  # Fail 3 times
       recovery_timeout=60,  # Wait 60s before retrying
       expected_exception=APITimeoutError
   )
   def sync_portfolio_data():
       # If API timeouts 3x in a row, open circuit
       # Fall back to cached data instead of timing out
       return portfolio_api.fetch()
   ```

3. **Alert when using cached/stale data:**
   ```python
   def generate_prep_report(prep_request):
       portfolio_data = fetch_portfolio_data()

       if portfolio_data.is_stale:
           # Add warning banner to report
           report.add_warning_banner(
               "This report uses cached portfolio data from March 13. "
               "Please refresh after the portfolio system recovers."
           )
           notify_advisor("Your report contains stale data; refresh when ready")

       return report
   ```

4. **Improve SLA compliance tracking:**
   ```sql
   -- Create SLA tracking table
   CREATE TABLE data_freshness_sla (
       date DATE,
       data_source VARCHAR,
       pct_fresh DECIMAL,  -- % of data <24h old
       sla_met BOOLEAN,
       alert_fired BOOLEAN
   );

   -- Daily report
   SELECT
       date,
       data_source,
       pct_fresh,
       CASE WHEN pct_fresh >= 99 THEN 'MET' ELSE 'MISS' END as sla_status
   FROM data_freshness_sla
   WHERE date >= NOW() - INTERVAL 30 DAYS
   ORDER BY date DESC, data_source;
   ```

5. **Implement fallback data sources:**
   ```python
   def fetch_portfolio_data():
       # Primary: Real-time portfolio system
       try:
           return portfolio_system.fetch()
       except APIError:
           # Secondary: Cached data (up to 48h old, better than failing)
           return cache.get_portfolio_data()
       except:
           # Tertiary: Last known state (emergency fallback)
           return database.get_last_portfolio_snapshot()
   ```

### Communication Template

**Internal (Slack #incidents)**
```
REVIEW PREP ENGINE INCIDENT: Data Freshness SLA Miss
Severity: P2 (Advisory Quality Impact)
Duration: Mar 14-16 (2+ days of stale data)
Affected: 142 prep reports, 80+ advisors, 100+ clients

Root Cause: Portfolio system API down (database issue); data pipeline couldn't sync; reports used 3-day-old data.

Actions:
1. Immediately alerted all advisors to refresh reports
2. Enabled cached data fallback (data up to 48h old used instead)
3. Contacted portfolio system team (API recovery ETA 30 min)
4. Added circuit breaker for API failures (fall back to cache vs. timeout)
5. Implemented data freshness alerting (notify when >12h stale)

Resolution: Portfolio system recovered by 11:00 UTC; data pipeline resumed syncing.

ETA: Fresh data available for new reports by 11:30 UTC
Assigned to: [DATA_ENGINEER], [PLATFORM_ENGINEER]
```

**Advisor Notification**
```
Action Required: Refresh Prep Reports

Your recent prep reports (Mar 14-16) contain portfolio data from March 13 (now outdated).

Recent client trades from Mar 14-16 are NOT in those reports.

Please regenerate reports by clicking the "Refresh" button to get current data before your client calls.

We've fixed the underlying data sync issue and are now providing fresh data.

Thank you for your patience!
```

### Postmortem Questions
1. Why wasn't there alerting when portfolio API went down?
2. Should we implement data freshness validation before allowing report delivery?
3. Can we add a "data age" indicator to the advisor UI?

---

## Incident 3: Engagement Scoring Model Drift (Inaccurate Recommendations)

### Context
Over the past month, advisors report that the engagement scoring recommendations (which clients to contact, which reviews to prioritize) have become inaccurate. The system is flagging low-engagement clients as "high priority" when they shouldn't be. Advisors are beginning to ignore the recommendations, defeating the system's value. Weekly accuracy audit shows 75% agreement with advisor judgment (vs. 90% target).

### Detection
- **Alert:** Weekly inter-rater agreement (IRA) audit shows <90% match between model scores and advisor ratings
- **Symptoms:**
  - Accuracy audit: 75% vs. target 90% (15% miss)
  - Advisor feedback: "Recommendations are off"
  - Model predictions diverging from recent advisor behavior

### Diagnosis (30 minutes)

**Step 1: Validate accuracy drop**
```python
# Weekly IRA audit (sample 5% of reports)
audit_date = TODAY()
advisor_ratings = get_advisor_ratings(audit_date, sample_pct=5)
model_scores = get_model_scores(audit_date, sample_pct=5)

accuracy = calculate_ira(advisor_ratings, model_scores)
# Result: 75% (down from 90% last week)

# Confusion matrix: Where is model failing?
print(confusion_matrix(advisor_ratings, model_scores))
# Result: Model is falsely flagging "Low" clients as "High"
```

**Step 2: Identify root cause**
```python
# Check if training data distribution changed
recent_data = get_training_data(last_30_days=True)
old_data = get_training_data(days_30_to_90=True)

# Compare class distributions
print(f"Recent HIGH: {sum(recent_data.engagement=='HIGH')} ({len(recent_data)} total)")
# Result: 45% HIGH (up from 30% in old data)

# Did advisor behavior change, or did model overfit?
# Check feature importance: What changed?
feature_drift = detect_feature_drift(recent_data, old_data)
# Result: Feature "last_contact_days" distribution shifted
# Old: Median 45 days, New: Median 20 days
# (Advisors are contacting clients more frequently!)
```

**Step 3: Check for data quality issues**
```sql
-- Are recent scores correctly labeled?
SELECT
  COUNT(*) as total_reviews,
  SUM(CASE WHEN engagement_score > 0.7 AND advisor_confirmed_high THEN 1 ELSE 0 END) as correct,
  ROUND(100.0 * SUM(CASE WHEN engagement_score > 0.7 AND advisor_confirmed_high THEN 1 ELSE 0 END) / COUNT(*), 2) as precision
FROM engagement_audit
WHERE created_at >= NOW() - INTERVAL 7 DAYS;

-- Result: Precision 60% (low!; model is over-predicting HIGH)
```

### Remediation

**Immediate (0-10 min): Lower model's confidence threshold**
```python
# Temporarily make model more conservative
# was: engagement_score > 0.7 → "HIGH"
# now: engagement_score > 0.85 → "HIGH" (higher bar)

ENGAGEMENT_THRESHOLD = 0.85  # was 0.70

# This reduces false positives (fewer low-engagement clients marked HIGH)
# Trade-off: Some true positives missed, but more accurate overall
```

**Short-term (10-30 min): Understand distribution shift**
```python
# Advisors have changed behavior (contacting clients more frequently)
# This changes the ground truth for the engagement model

# Recent labels from advisors show:
# - 50% of clients now marked HIGH (vs. 30% historically)
# - Contact frequency increased (Q1 2026 shows more engagement)

# Model trained on old distribution (30% HIGH) now applied to new distribution (50% HIGH)
# → Model appears inaccurate, but advisor behavior changed!

# Need to retrain on recent data reflecting new engagement patterns
```

**Root cause remediation (1-2 hours):**

1. **Retrain engagement model on recent data:**
   ```bash
   python -m engagement_model.train \
     --training_data=last_60_days_labeled_reviews.csv \
     --validation_data=last_7_days_labeled_reviews.csv \
     --test_data=holdout_reviews.csv \
     --target_accuracy=0.90

   # Validate accuracy on test set
   python -m engagement_model.evaluate --model=engagement_v2.6 --test_set=holdout_reviews.csv
   # Result: 92% accuracy (restored!)
   ```

2. **Update feature engineering to reflect new engagement patterns:**
   ```python
   # Old features: last_contact_days, num_trades, portfolio_size
   # New features: (add) contact_frequency_trend, advisor_interaction_momentum

   def compute_features(client):
       return {
           'last_contact_days': days_since_last_contact(client),
           'contact_frequency_trend': contact_count_last_30d / contact_count_prior_30d,  # NEW
           'advisor_momentum': advisor_recent_interactions / historical_average,  # NEW
           'portfolio_size': client.portfolio_value,
       }
   ```

3. **Implement continuous model monitoring:**
   ```python
   def continuous_engagement_validation():
       # Weekly: Re-audit model accuracy against advisor feedback
       weekly_audit = run_ira_audit(sample_pct=5)

       if weekly_audit.accuracy < 0.88:  # <88% = warning
           alert.warn(f"Engagement model accuracy degraded to {weekly_audit.accuracy}")
           recommend_retraining()

       if weekly_audit.accuracy < 0.85:  # <85% = critical
           alert.error(f"Engagement model accuracy critical: {weekly_audit.accuracy}")
           trigger_immediate_retraining()
   ```

4. **Add feature drift monitoring:**
   ```python
   def detect_feature_drift():
       current_data = get_recent_client_data(last_30_days=True)
       historical_data = get_historical_data(30_to_60_days_ago=True)

       for feature in ['last_contact_days', 'contact_frequency', 'portfolio_size']:
           current_dist = current_data[feature].distribution()
           historical_dist = historical_data[feature].distribution()

           # Kolmogorov-Smirnov test for distribution shift
           ks_stat = ks_test(current_dist, historical_dist)

           if ks_stat > 0.2:  # Significant shift
               alert.warn(f"Feature drift detected in '{feature}'")
               recommend_retraining()
   ```

5. **Improve model interpretability for advisors:**
   ```python
   # Show advisors WHY the model flagged a client as HIGH
   def explain_engagement_score(client):
       score = model.predict(client)
       explanation = {
           'total_score': score,
           'factors': {
               'recent_contact': 0.15,  # Contacted in last 7 days (positive)
               'trade_activity': 0.12,   # Made 3 trades last month (positive)
               'portfolio_volatility': -0.08,  # No volatility spike (slight negative)
           }
       }
       return explanation

   # Display in UI: "Client flagged HIGH because: recent contact (15%), active trading (12%)"
   ```

### Communication Template

**Internal (Slack #incidents)**
```
REVIEW PREP ENGINE INCIDENT: Engagement Scoring Accuracy Drop
Severity: P2 (Advisor Confidence in System)
Duration: Gradual drop over past 4 weeks; detected via weekly audit
Affected: All advisors; reducing system adoption

Root Cause: Advisor behavior changed (contacting clients more frequently in Q1). Model was trained on historical data with lower engagement baseline (30% HIGH vs. current 50% HIGH). Distribution shift caused model to appear inaccurate.

Actions:
1. Temporarily raised confidence threshold (0.70 → 0.85) to reduce false positives
2. Retrained model on recent 60-day data reflecting new engagement patterns
3. Added feature drift monitoring (automated detection of distribution shifts)
4. Implemented weekly accuracy audits with immediate retraining if <88%
5. Added model explainability to show advisors WHY recommendations are made

Resolution: Model retraining completed; accuracy restored to 92%.

ETA: New model deployed by 14:00 UTC
Assigned to: [ML_ENGINEER], [PRODUCT_MANAGER]
```

**Advisor Notification**
```
Engagement Scoring Improvements

We've updated the engagement scoring model to better reflect current client relationship patterns.

Recent changes:
- Added real-time contact frequency tracking (shows momentum, not just recency)
- Improved accuracy of client priority recommendations
- Added explanations for why each client is flagged as HIGH/MEDIUM/LOW priority

The system should now be more accurate in helping you identify which clients to prioritize.

Please report any feedback on recommendations!
```

### Postmortem Questions
1. Why didn't we detect the accuracy drop sooner (only discovered via weekly audit)?
2. Should we implement real-time accuracy monitoring instead of weekly audits?
3. Can we automate model retraining when accuracy drops below threshold?

---

## General Escalation Path
1. **P3 (Prep slow, <10 reports):** Assign to engineer; investigate bottleneck
2. **P2 (Data stale, many reports affected, accuracy issues):** Escalate to data lead + product within 15 min
3. **P1 (PII exposure, data loss, major outage):** Page security team + VP engineering immediately
4. **All PII-related incidents:** Treat as P1; immediate escalation to legal/compliance

