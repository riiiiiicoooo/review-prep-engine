# Review Prep Engine - Capacity Plan

## Executive Summary
Review Prep Engine automates client review preparation for wealth managers. This plan quantifies infrastructure and team capacity for current state, 2x growth, and 10x growth scenarios.

---

## Current State (Q1 2026)

### Usage Metrics
- **Active Advisors:** 150
- **Prep Reports/Day:** 600 (4 per advisor average)
- **Average Prep Time:** 12 minutes (target maintained)
- **Data Sources:** 8 (market feeds, portfolio systems, client accounts, risk models, CRM, tax data, performance analytics, compliance)
- **Data Freshness:** 99% of data <24 hours old
- **Monthly Preps:** ~18,000 (600 × 30 days)

### Infrastructure
| Component | Current | Monthly Cost |
|-----------|---------|--------------|
| **Web/API Servers** | 3 instances (t3.large) | $432 |
| **Report Generation (compute)** | 2 × c5.2xlarge (report assembly) | $1,056 |
| **Data Pipeline** | Airflow + 2 × t3.xlarge | $576 |
| **Database (PostgreSQL)** | db.r5.xlarge (4 vCPU, 32 GB) | $2,800 |
| **Cache (Redis)** | 5 GB (engagement scores, portfolio summaries) | $450 |
| **Object Storage (reports)** | 200 GB (PDF archives) | $4.60 |
| **Data Warehousing** | Redshift RA3 node | $3,600 |
| **Monitoring/Logging** | CloudWatch + DataDog | $600 |
| **Total Monthly** | | **$9,519** |

### Team Capacity
| Role | Count | Utilization |
|------|-------|-------------|
| **Backend Engineers** | 2 | 80% |
| **Data Engineers** | 1 | 75% |
| **ML Engineer (engagement scoring)** | 0.5 | 70% |
| **SRE/DevOps** | 1 | 70% |
| **Product Manager** | 1 | 85% |

---

## 2x Growth Scenario (12 months forward)
**Assumption:** 300 advisors, 1,200 preps/day, avg prep time 11 min, 8 data sources

### What Breaks First
1. **Data Pipeline Latency:** Ingesting 2x data from 8 sources takes >4 hours; data becomes >24 hours stale
2. **Report Generation Throughput:** Single compute cluster can't handle 1,200 concurrent prep requests; queue backs up
3. **Database Query Latency:** Advisor-level portfolio queries become slow; engagement score lookups delayed
4. **Team Scalability:** Data engineering team can't maintain 8 data sources; SLA on freshness slips

### Required Infrastructure Changes
| Component | Current → 2x | Incremental Cost |
|-----------|--------------|-----------------|
| **Web/API Servers** | 3 × t3.large → 5 × t3.xlarge | +$576/month |
| **Report Generation** | 2 × c5.2xlarge → 4 × c5.4xlarge (parallel jobs) | +$2,112/month |
| **Data Pipeline** | Airflow + 2 × t3.xlarge → Airflow + 4 × t3.xlarge + Spark cluster | +$1,728/month |
| **Database** | r5.xlarge → r6i.2xlarge + 1 read replica | +$3,200/month |
| **Cache** | 5 GB Redis → 12 GB Redis Cluster | +$450/month |
| **Data Warehouse** | RA3 1-node → RA3 3-node (for concurrent queries) | +$3,600/month |
| **Total Infrastructure @ 2x** | | **$20,886/month** (+120%) |

### Team Additions @ 2x
- +1 Data Engineer (manage 8 data sources + SLA)
- +0.5 Backend Engineer (scalability/caching)
- +1 SRE (multi-region readiness)
- **Cost:** ~$280K/year all-in

---

## 10x Growth Scenario (24 months forward)
**Assumption:** 1,500 advisors, 6,000 preps/day, avg prep time 10 min, 15 data sources

### What Breaks First
1. **Data Integration Complexity:** 15 data sources with different latencies/formats become unmaintainable; custom integration for each
2. **Real-Time Personalization:** Prep reports must be truly personalized (per-advisor preferences, role-based data); current batch approach insufficient
3. **Regulatory Compliance at Scale:** Managing PII/compliance across 15 data sources becomes critical; any leak triggers audit
4. **Global Expansion:** Advisors in multiple regions require localized prep (tax rules, currencies, compliance frameworks)

### Required Infrastructure Changes
| Component | Current → 10x | Incremental Cost |
|-----------|--------------|-----------------|
| **Web/API Tier** | 3 × t3.large → 20 × t3.2xlarge (multi-region) | +$2,880/month |
| **Report Generation** | 2 × c5.2xlarge → 40 × c5.xlarge (distributed, serverless) | +$6,800/month |
| **Data Pipeline** | Airflow → Kafka + dbt (streaming + transformations) | +$2,500/month |
| **Database** | r5.xlarge → r6i.3xlarge + 8 read replicas (regional) | +$8,000/month |
| **Cache** | 5 GB → 50 GB Redis Cluster (distributed) | +$1,800/month |
| **Data Warehouse** | RA3 1-node → BigQuery (serverless, multi-region) | +$5,000/month |
| **Real-Time Personalization** | 0 → ML feature store (Feast) for ad-hoc personalization | +$1,500/month |
| **Regional Compliance** | 0 → Compliance management system (audit logging, PII masking per region) | +$2,000/month |
| **Monitoring Enterprise** | DataDog → Datadog Enterprise + custom compliance dashboards | +$1,500/month |
| **Total Infrastructure @ 10x** | | **$49,480/month** (+420%) |

### Team Scaling @ 10x
| Role | Current → 10x | Notes |
|---|---|---|
| **Backend Engineers** | 2 → 8 (personalization, caching, multi-region) | Domain-driven: prep engine, integration, analytics |
| **Data Engineers** | 1 → 6 (15 data sources, real-time sync, compliance) | Each data source has dedicated engineer + QA |
| **ML/Personalization** | 0.5 → 3 (engagement scoring, recommendation models, A/B testing) | Continuous experimentation on advisor experience |
| **SRE/DevOps** | 1 → 4 (multi-region, incident response, compliance audits) | 24/7 coverage across US/EU/APAC |
| **Product Manager** | 1 → 2 (core PM + regional/compliance specialist) | Navigate multi-region regulatory complexity |
| **Data Quality** | 0 → 2 (validate freshness for 15 sources, SLA monitoring) | Ensure 99% freshness across all sources |
| **Security/Compliance** | 0 → 1 FTE (PII masking, audit logs, regulatory alignment) | Manage GLBA, SOX, GDPR, regional compliance |
| **Total Cost** | ~$550K/year → ~$2.2M/year | +300% headcount for 10x advisors |

---

## Cost Optimization Timeline

### Phase 1: Current → 2x (Months 0-6)
1. **Report Caching:** Cache engagement scores and portfolio summaries (reduce computation by 30%)
2. **Data Source Prioritization:** Identify top 3 sources by volume; optimize ingestion (reduce pipeline latency by 40%)
3. **Incremental Updates:** Only fetch changed data from sources (vs. full refresh); reduce ETL time by 50%

### Phase 2: 2x → 5x (Months 6-12)
1. **Real-Time Data Streaming:** Move from batch ETL (hourly) to streaming (continuous) for high-frequency sources
2. **Advisor Segmentation:** Batch prep generation by advisor cohorts (allows better resource scheduling)
3. **Serverless Report Gen:** Use Lambda for lightweight preps (vs. always spinning up compute)

### Phase 3: 5x → 10x (Months 12-24)
1. **Feature Store:** Implement centralized ML feature store (reuse precomputed features across models)
2. **Heterogeneous Computing:** Use GPU for complex engagement scoring; CPU for simple report assembly
3. **Multi-Region Compliance:** Deploy regionally to meet data residency requirements (vs. single-region + replication)

---

## Monitoring & Decision Gates

### Weekly Metrics
- Prep time SLA: Alert if >95% exceed 12 min
- Data freshness: Alert if <99% of data <24 hours old
- Report success rate: Alert if <99.5%
- Engagement score accuracy: Alert if <90% match advisor assessment

### Monthly Decision Gates
| Metric | Threshold | Action |
|--------|-----------|--------|
| Prep time | >12 min × 50% of requests | Optimize data queries or report assembly |
| Data freshness | <98% × 1 week | Investigate data feed lag; escalate to source provider |
| Pipeline lag | >4 hours × 2 days | Increase pipeline concurrency or add compute |
| Engagement accuracy | <88% × 2 weeks | Retrain model on advisor feedback |
| PII exposure | >0 incidents | Immediate investigation; strengthen masking logic |
| Report failures | >1% × 1 day | Incident investigation; improve robustness |

