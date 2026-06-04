# data/pipeline_code/gold_aggregation.py
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count, min, max, avg, current_date, when, lit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoldAggregation")

def get_spark():
    return SparkSession.builder.appName("GoldAggregation").getOrCreate()

def run_gold_aggregation(spark):
    """
    Reads Silver tables and aggregates them to generate analytical reports.
    """
    logger.info("Starting Gold aggregation pipeline.")
    
    # ── 1. Daily Revenue Aggregation by Region & Product Category ────────────
    # Reads silver.orders joined with silver.products (conceptually)
    logger.info("Calculating regional revenue metrics.")
    silver_orders = spark.read.table("silver.orders")
    
    daily_revenue = silver_orders \
        .filter(col("status") == "completed") \
        .groupBy("order_date", "region") \
        .agg(
            sum("total_amount").alias("gross_revenue_usd"),
            # Assume 10% average tax/discount for net revenue
            (sum("total_amount") * 0.90).alias("net_revenue_usd"),
            count("order_id").alias("order_count")
        ) \
        .withColumnRenamed("order_date", "report_date")
        
    logger.info("Writing results to gold.daily_revenue table.")
    daily_revenue.write.format("delta").mode("overwrite").saveAsTable("gold.daily_revenue")

    # ── 2. Unified Customer 360 View ──────────────────────────────────────────
    # Combines profile information, order counts, and behavior summaries
    logger.info("Building Customer 360 analytical profile.")
    silver_customers = spark.read.table("silver.customers").filter("is_current = true")
    
    customer_metrics = silver_orders \
        .groupBy("customer_id") \
        .agg(
            sum("total_amount").alias("total_lifetime_value"),
            count("order_id").alias("total_orders"),
            max("order_date").alias("last_order_date")
        )
        
    customer_360 = silver_customers.alias("cust") \
        .join(customer_metrics.alias("metrics"), col("cust.customer_id") == col("metrics.customer_id"), "left_outer") \
        .select(
            col("cust.customer_id"),
            col("cust.region"),
            col("cust.tier"),
            col("metrics.total_lifetime_value"),
            col("metrics.total_orders"),
            col("metrics.last_order_date"),
            # Placeholder for ML churn model risk score (with timeout safety / null fallback)
            when(col("cust.tier") == "GOLD", 0.15) \
            .when(col("cust.tier") == "SILVER", 0.35) \
            .when(col("cust.tier") == "BRONZE", 0.65) \
            .otherwise(0.0).alias("churn_risk_score")
        )
        
    logger.info("Writing results to gold.customer_360 table.")
    customer_360.write.format("delta").mode("overwrite").saveAsTable("gold.customer_360")
    logger.info("Gold aggregation complete.")

if __name__ == "__main__":
    spark = get_spark()
    run_gold_aggregation(spark)
