from google.cloud import bigquery
from gcp_utils_sds import buckets
from modules.file_transformation import *
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/app/icef-437920.json"
client = bigquery.Client(project="icef-437920")

YEAR = "26-27"

# Capacity for enrollment_demographics: static budget + PS roster counts.
# Does not use intent_to_return_results or completed_registrations.
# 25-26 remains on enrollment.budgeted_enrollment_capacity_hardcode_8_18_25 (no YoY appender).
# Dual-write: GCS (audit) + BQ (hourly freshness for enrollment_demographics).
budgeted_enrollment_capacity = create_budgeted_enrollment_capacity(client, year=YEAR)

buckets.send_to_gcs(
    bucket_name="enrollmentbucket-icefschools-1",
    save_path="",
    frame=budgeted_enrollment_capacity,
    frame_name="budgeted_enrollment_capacity.csv",
    project_id="icef-437920",
    dag_name="enrollment",
)

job_config = bigquery.LoadJobConfig(
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    schema=[
        bigquery.SchemaField("school_name", "STRING"),
        bigquery.SchemaField("grade_level", "INTEGER"),
        bigquery.SchemaField("student_count", "INTEGER"),
        bigquery.SchemaField("budgeted_enrollment", "INTEGER"),
        bigquery.SchemaField("seats_remaining", "INTEGER"),
        bigquery.SchemaField("percent_of_seats_filled", "FLOAT"),
        bigquery.SchemaField("year", "STRING"),
        bigquery.SchemaField("program_id", "INTEGER"),
    ],
)
load_job = client.load_table_from_dataframe(
    budgeted_enrollment_capacity,
    "icef-437920.enrollment.budgeted_enrollment_capacity",
    job_config=job_config,
)
load_job.result()
logging.info(
    "Loaded icef-437920.enrollment.budgeted_enrollment_capacity (%s rows)",
    len(budgeted_enrollment_capacity),
)
