# Architecture Decision Records (ADRs)

## ADR-001: Medallion Architecture (Bronze-Silver-Gold)

**Status**: Accepted  
**Date**: 2024-01-15

**Context**: We need a scalable, auditable data lake architecture that supports both streaming and batch ingestion.

**Decision**: Adopt the Medallion (Bronze-Silver-Gold) architecture.

**Rationale**:
- **Bronze** preserves raw data for full replay capability.
- **Silver** provides a clean, consistent analytical layer.
- **Gold** delivers business-ready metrics with BI-friendly structures.
- Industry standard with broad ecosystem support (Delta Lake, dbt).

**Consequences**: Extra storage cost for multi-layer copies. Accepted trade-off for auditability and decoupling.

---

## ADR-002: Delta Lake as Storage Format

**Status**: Accepted  
**Date**: 2024-01-20

**Decision**: Use Delta Lake (`.delta`) over Parquet for all managed tables.

**Rationale**:
- ACID transactions prevent partial writes from corrupting tables.
- Time travel enables point-in-time recovery and audit.
- Schema evolution support without full table rewrites.
- Unified batch + streaming reads via Delta streaming source.

---

## ADR-003: Monitoring and Alerting Stack

**Status**: Accepted  
**Date**: 2024-02-01

**Decision**: Prometheus + Grafana for metrics; PagerDuty for on-call alerts.

**Rationale**:
- Prometheus pull model fits our Kubernetes-hosted Spark jobs.
- Grafana dashboards provide real-time visibility for the DE team.
- PagerDuty integrates with our existing incident management process.

**Alert thresholds**:
- P1 (immediate): Pipeline failure after 2 retries.
- P2 (within 1hr): SLO breach on any Gold table.
- P3 (next business day): Data quality violation count > 1% of rows.

---

## ADR-004: Retry Strategy

**Status**: Accepted

**Decision**: Exponential backoff with circuit breaker.

**Parameters**:
- Max retries: 3
- Base delay: 30 seconds
- Multiplier: 2×
- Circuit breaker threshold: 5 consecutive failures → 10-minute pause.

---

## ADR-005: PII Data Governance

**Status**: Accepted

**Decision**: Tag PII columns in the data catalogue; apply masking at Silver layer.

**PII column policy**:
- Bronze: Raw PII stored (no masking — needed for replay).
- Silver: Email and phone masked to `email_hash` and `phone_last4`.
- Gold: No PII in aggregations. Aggregated by cohort/segment, not individual.
- Access control: PII Silver tables restricted to `data-engineering` and `compliance` roles.
