# Silver Transformation Pipeline

## Overview
The Silver layer transforms raw Bronze data into cleaned, deduplicated, and schema-enforced datasets. Silver is the analytical foundation — all downstream Gold aggregations and ML features read from Silver.

## Cleaning Rules

### Null Handling
- Numeric nulls → replaced with column median (computed on 30-day window).
- String nulls → replaced with `"UNKNOWN"` sentinel value.
- Critical PII fields (email, phone) with nulls → row quarantined to `silver.quarantine` table.

### Deduplication
Deduplication uses a composite primary key strategy:
- **Orders**: `(order_id, source_system)` — latest `updated_at` wins.
- **Customers**: `(customer_id)` — SCD Type 2 applied (history preserved).
- **Events**: `(event_id, event_timestamp)` — exact match deduplicated.

### Data Type Enforcement
All columns cast to canonical types defined in `schema_contracts/silver_schema.yaml`:
- Timestamps → UTC ISO-8601
- Monetary amounts → `DECIMAL(18, 4)`
- IDs → `VARCHAR(64)`

## SCD Type 2 Handling

Customer dimension uses Slowly Changing Dimension Type 2:
- New version created when: `email`, `phone`, `address`, or `tier` changes.
- `effective_from` set to change timestamp.
- `effective_to` set to `9999-12-31` for current record.
- `is_current` flag maintained for fast filtering.

## Schema Enforcement

Schema validation runs on every Silver write:
1. Great Expectations suite `silver_expectations.json` checked.
2. Column count, types, and allowed value ranges validated.
3. Violations logged to `meta.schema_violations` and alert sent.
4. Pipeline continues but violating rows are quarantined.

## Performance

- Spark AQE (Adaptive Query Execution) enabled.
- Z-ordering on `customer_id` for range query optimization.
- Bloom filters on `order_id` columns.
- Target file size: 256 MB per partition.

## Output Tables

| Table | Rows (avg) | Partitioned By | SLO |
|-------|------------|----------------|-----|
| silver.orders | 500K/day | order_date | < 2hr after Bronze |
| silver.customers | 2M (total) | region | < 3hr after Bronze |
| silver.events | 5M/day | event_date | < 1hr after Bronze |
| silver.products | 100K (total) | category | < 4hr after Bronze |
