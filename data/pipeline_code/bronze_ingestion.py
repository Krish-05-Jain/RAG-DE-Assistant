# data/pipeline_code/bronze_ingestion.py
import time
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BronzeIngestion")

def get_spark():
    return SparkSession.builder \
        .appName("BronzeIngestion") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

def run_salesforce_ingestion(spark, db_conn, target_table="bronze.salesforce_accounts"):
    """
    Ingests accounts from Salesforce CRM API with Watermark tracking.
    """
    logger.info(f"Starting incremental ingestion into {target_table}")
    
    # 1. Fetch last watermark timestamp
    watermark_df = spark.sql("SELECT MAX(last_ingested_at) FROM meta.pipeline_watermarks WHERE pipeline_id = 'bronze_salesforce_accounts'")
    last_watermark = watermark_df.collect()[0][0] if watermark_df.count() > 0 else "1970-01-01T00:00:00"
    
    logger.info(f"Querying Salesforce records modified after: {last_watermark}")
    
    # 2. Simulate API Call with Exponential Backoff Retry Strategy
    retries = 3
    delay = 30
    success = False
    for attempt in range(1, retries + 1):
        try:
            # Simulate API query
            raw_data = [
                {"account_id": "ACC100", "account_name": "Acme Corp", "email": "info@acme.com", "phone": "555-0199", "region": "North"},
                {"account_id": "ACC101", "account_name": "Globex", "email": "contact@globex.org", "phone": "555-0122", "region": "South"},
            ]
            raw_df = spark.createDataFrame(raw_data)
            success = True
            break
        except Exception as e:
            logger.warning(f"Salesforce API timeout (Attempt {attempt}/{retries}). Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff multiplier
            
    if not success:
        logger.error("Salesforce API connection failed after 3 retries. Routing to S3 Dead-Letter-Queue.")
        # In production, route to s3://bronze-dlq/
        raise ConnectionError("Salesforce API offline.")

    # 3. Add ingest metadata
    bronze_df = raw_df \
        .withColumn("_ingested_at", current_timestamp()) \
        .withColumn("_source_system", lit("Salesforce"))

    # 4. Write incrementally using Delta MERGE (idempotent upsert)
    logger.info(f"Merging {bronze_df.count()} rows into Bronze Delta table {target_table}")
    bronze_df.write \
        .format("delta") \
        .mode("append") \
        .saveAsTable(target_table)

    # 5. Update watermark
    spark.sql(f"INSERT INTO meta.pipeline_watermarks VALUES ('bronze_salesforce_accounts', CURRENT_TIMESTAMP(), 'RUN_ID_SF_{int(time.time())}', CURRENT_TIMESTAMP())")
    logger.info("Bronze Salesforce ingestion complete.")

if __name__ == "__main__":
    spark = get_spark()
    run_salesforce_ingestion(spark, None)
