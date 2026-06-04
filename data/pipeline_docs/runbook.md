# Operational Runbook — Data Engineering Pipelines

## On-Call Responsibilities

**Primary**: Data Engineering on-call (rotation via PagerDuty)  
**Escalation Path**: DE Lead → Head of Data → VP Engineering

---

## Common Failure Modes & Remediation

### 1. Bronze Ingestion Timeout

**Symptoms**: `TimeoutError` in Spark logs, Bronze pipeline stuck in RUNNING state > 30 min.

**Steps**:
1. Check Spark UI: `http://spark-master:4040`
2. Kill the stuck job: `spark.sparkContext.cancelAllJobs()`
3. Check source API status (Salesforce status page / ERP ping).
4. If source is up, restart pipeline from last watermark:
   ```bash
   python -m pipelines.bronze.ingest --resume-from-watermark
   ```
5. If source is down, create P2 incident and set pipeline to PAUSED.

### 2. Silver Schema Violation

**Symptoms**: Schema validation alert fires; `meta.schema_violations` has new rows.

**Steps**:
1. Query violations: `SELECT * FROM meta.schema_violations WHERE date = CURRENT_DATE ORDER BY created_at DESC LIMIT 20;`
2. Identify the offending column and source system.
3. Check if this is a new column (schema evolution) or a type change.
4. For new column: Update `schema_contracts/silver_schema.yaml` and re-run Silver.
5. For type change: Raise P1 with the upstream team.

### 3. Gold SLO Breach

**Symptoms**: Gold table not refreshed by target time; BI dashboards show stale data.

**Steps**:
1. Check Gold pipeline logs: `kubectl logs -n data-pipelines -l app=gold-pipeline`
2. If Silver is also stale, fix Silver first (Gold depends on Silver).
3. Manually trigger Gold refresh: `airflow dags trigger gold_aggregation_pipeline`
4. Notify stakeholders via Slack `#data-incidents` channel.
5. Document in post-mortem if SLO missed by > 2 hours.

### 4. Data Quality Alert — Null Rate Spike

**Symptoms**: Null percentage > 2% on a non-nullable column.

**Steps**:
1. Run quality check: `python -m tools.quality_checker --table <table_name>`
2. Identify the source: check Bronze raw data for nulls.
3. If source nulls: Alert upstream team, quarantine affected partitions.
4. If transformation bug: Hotfix Silver transformation rule, re-process affected date partition.

### 5. Row Count Anomaly

**Symptoms**: Gold row count deviates > 15% from rolling average.

**Steps**:
1. Compare row counts by partition: `SELECT report_date, COUNT(*) FROM gold.daily_revenue GROUP BY 1 ORDER BY 1 DESC LIMIT 7;`
2. Check if upstream data volume changed legitimately (e.g., campaign spike, data backfill).
3. If legitimate: Update baseline in `meta.row_count_baselines`.
4. If anomaly: Investigate Bronze source for missing/duplicate data.

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| DE On-Call | Rotation | PagerDuty |
| Data Lead | Team Lead | Slack @data-lead |
| Platform Ops | Infra Team | Slack #platform-ops |
| BI Stakeholders | Analytics | Slack #analytics |

---

## Useful Commands

```bash
# Check pipeline status
python -m app.agents.tools.health_monitor

# Trigger ingestion
python -m app.rag.ingestion

# Run quality check on a table
python -m app.agents.tools.quality_checker orders

# Start MCP server
uvicorn app.mcp.server:app --host 0.0.0.0 --port 8080

# Launch Streamlit app
streamlit run app/main.py
```
