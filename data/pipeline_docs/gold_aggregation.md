# Gold Aggregation Pipeline

## Overview
The Gold layer contains business-ready aggregations and materialized views consumed directly by BI tools, dashboards, and stakeholder reports. Gold tables are the single source of truth for business metrics.

## Business Metrics

### Revenue Metrics
- **`gold.daily_revenue`**: Gross/net revenue by day, region, and product category.
- **`gold.mrr_churn`**: Monthly Recurring Revenue and churn rate (SaaS metrics).
- **`gold.cohort_revenue`**: Revenue cohort analysis by customer signup month.

### Operational Metrics
- **`gold.pipeline_kpis`**: ETL success rates, SLA adherence, data freshness.
- **`gold.sla_scorecard`**: Weekly SLA compliance per data product.

### Customer Metrics
- **`gold.customer_360`**: Unified customer view joining orders, events, and support tickets.
- **`gold.ltv_segments`**: Customer lifetime value segmentation (Platinum/Gold/Silver/Bronze tiers).

## Partitioning Strategy

Gold tables are partitioned for BI performance:
- Time-series tables: partition by `report_date` (daily granularity).
- Dimensional tables: no partition, fully cached in BI layer.
- Cluster keys: `customer_id`, `product_id` for join optimization.

## Materialized Views

Three high-frequency queries are materialized:
1. **Executive Dashboard** — Refreshed every 15 minutes.
2. **Sales Funnel** — Refreshed every hour.
3. **Customer 360** — Refreshed nightly (full recompute).

## Refresh Schedule

| Table | Schedule | Duration | SLO |
|-------|----------|----------|-----|
| gold.daily_revenue | 06:00 UTC | ~15 min | Available by 07:00 UTC |
| gold.mrr_churn | 1st of month, 08:00 UTC | ~45 min | Available by 10:00 UTC |
| gold.customer_360 | 03:00 UTC nightly | ~90 min | Available by 06:00 UTC |
| gold.pipeline_kpis | Every 30 min | ~5 min | Available within 35 min |

## Data Quality Expectations

Gold tables enforce stricter DQ rules:
- Zero null tolerance on key metric columns (`revenue_usd`, `customer_id`).
- Revenue values must be positive (no negative revenue in Gold).
- Row count must be within ±10% of previous day (anomaly detection).
- Cross-table reconciliation: Gold revenue ≈ Silver orders revenue within 0.01%.
