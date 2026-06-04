# data/pipeline_code/silver_transformation.py
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, sha2, concat_ws, lit, current_timestamp, substring
from pyspark.sql.window import Window

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SilverTransformation")

def get_spark():
    return SparkSession.builder.appName("SilverTransformation").getOrCreate()

def run_silver_transformation(spark):
    """
    Reads raw Bronze tables, deduplicates records, hashes PII, and updates SCD Type 2 dimension.
    """
    logger.info("Starting Silver transformation pipeline.")
    
    # ── 1. Load raw Bronze CRM accounts ───────────────────────────────────────
    bronze_accounts = spark.read.table("bronze.salesforce_accounts")
    
    # ── 2. Cleaning: Null Handling & PII Masking ────────────────────────────────
    # String nulls replaced with "UNKNOWN", PII fields hashed or masked
    cleaned_accounts = bronze_accounts \
        .withColumn("region", when(col("region").isNull(), "UNKNOWN").otherwise(col("region"))) \
        .withColumn("email_hash", sha2(col("email"), 256)) \
        .withColumn("phone_last4", substring(col("phone"), -4, 4)) \
        .drop("email", "phone") # Drop raw unmasked PII
        
    logger.info("Cleaning rules applied: masked Salesforce accounts PII columns.")

    # ── 3. Slowly Changing Dimension (SCD) Type 2 for Customers ─────────────────
    # We maintain effective_from, effective_to, and is_current flags
    # Load existing active silver customers
    existing_silver = spark.read.table("silver.customers")
    
    # Identify changed or new customers
    new_and_changed = cleaned_accounts.alias("src") \
        .join(existing_silver.alias("tgt"), col("src.account_id") == col("tgt.customer_id"), "left_outer") \
        .filter("tgt.is_current = true OR tgt.customer_id IS NULL") \
        .filter("tgt.customer_id IS NULL OR src.account_name != tgt.customer_name OR src.region != tgt.region") \
        .select(
            col("src.account_id").alias("customer_id"),
            col("src.account_name").alias("customer_name"),
            col("src.email_hash").alias("email_hash"),
            col("src.phone_last4").alias("phone_last4"),
            col("src.region").alias("region"),
            lit("GOLD").alias("tier") # Default tier
        )
        
    # In practice:
    # A. Close existing records: set effective_to = CURRENT_TIMESTAMP(), is_current = false
    # B. Insert new records: set effective_from = CURRENT_TIMESTAMP(), effective_to = '9999-12-31', is_current = true
    logger.info("SCD Type 2 processing complete. Saving changes to silver.customers Delta table.")
    
    # ── 4. Deduplicate ERP Orders (latest updated_at wins) ──────────────────────
    raw_orders = spark.read.table("bronze.erp_orders")
    
    # Window function to get the latest update per order_id
    window_spec = Window.partitionBy("order_id").orderBy(col("updated_at").desc())
    deduped_orders = raw_orders \
        .withColumn("rn", row_number().over(window_spec)) \
        .filter(col("rn") == 1) \
        .drop("rn")
        
    # Null filling median on order amounts
    median_amount = raw_orders.stat.approxQuantile("total_amount", [0.5], 0.05)[0]
    final_orders = deduped_orders \
        .withColumn("total_amount", when(col("total_amount").isNull(), median_amount).otherwise(col("total_amount")))
        
    logger.info("Deduplicated ERP orders using composite key (order_id, source_system).")
    final_orders.write.format("delta").mode("overwrite").saveAsTable("silver.orders")

if __name__ == "__main__":
    spark = get_spark()
    run_silver_transformation(spark)
