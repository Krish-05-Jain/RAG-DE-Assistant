# Bronze Ingestion Pipeline

## Overview
The Bronze layer is the raw data landing zone. All source data arrives here unchanged — a faithful copy of what upstream systems sent us. This immutability is critical for audit, replay, and schema evolution.

## Data Sources

| Source System | Connector | Load Type | Schedule |
|---------------|-----------|-----------|----------|
| Salesforce CRM | REST API (bulk) | Incremental (updated_at) | Every 15 min |
| PostgreSQL ERP | JDBC | Full Snapshot | Nightly 01:00 UTC |
| Kafka Event Bus | Kafka Consumer | Streaming | Continuous |
| S3 Data Dump | S3 Prefix Scan | Incremental (file mtime) | Hourly |

## Retry Strategy

The Bronze ingestion pipeline uses an **exponential backoff** retry strategy:

- **Max retries**: 3
- **Initial delay**: 30 seconds
- **Backoff multiplier**: 2× (30s → 60s → 120s)
- **Dead-letter queue**: Failed messages are routed to `s3://bronze-dlq/` with full metadata preserved.
- **Circuit breaker**: After 5 consecutive failures, the pipeline pauses for 10 minutes before resuming.

## Idempotency

Every Bronze load is idempotent via:
1. **Watermark tracking** — `last_ingested_at` stored in the control table `meta.pipeline_watermarks`.
2. **Upsert semantics** — Delta Lake `MERGE INTO` prevents duplicate rows.
3. **Partition pruning** — Data is partitioned by `ingestion_date` to isolate re-runs.

## Schema Handling

Bronze tables store data **as-is** with two added metadata columns:
- `_ingested_at` — UTC timestamp when the row landed in Bronze.
- `_source_system` — String identifier of the originating system.

No schema enforcement at Bronze. Schema drift is logged but not rejected.

## Common Failure Modes

1. **API rate limit hit** — Salesforce throttles at 100k API calls/day. Monitor `REMAINING_API_CALLS`.
2. **JDBC connection timeout** — PostgreSQL ERP goes offline for maintenance windows (Tue 02:00–04:00 UTC). Skip and backfill.
3. **Malformed JSON in Kafka** — Dead-letter immediately, alert on-call via PagerDuty.
4. **S3 permission denied** — Usually an IAM role rotation issue. Rotate credentials and retry.

## Monitoring

- **Dashboard**: Grafana `Bronze Ingestion Health` panel
- **Alerts**: PagerDuty for failure rate > 2 consecutive runs
- **SLO**: All source data must be in Bronze within 30 minutes of generation
