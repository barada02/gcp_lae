from fastapi import FastAPI, Request
from google.cloud import storage, bigquery
from google.api_core import exceptions as gcp_exceptions # Import GCP exceptions
import pandas as pd
import io
import json
import base64
from datetime import datetime

app = FastAPI()

# --- Configuration ---
# Hardcoding Project ID for robustness after previous deployment issues
PROJECT_ID = "social-463809" 
BQ_DATASET = "aidelab_processed"
BQ_TABLE_ID = "transformed_data" # Single destination table for all files in this MVP test
PROCESSOR_NAME = "CloudRunParserAgent"

# Initialize clients globally
storage_client = storage.Client()
bq_client = bigquery.Client()

# Set the full table ID globally
BQ_FULL_TABLE_ID = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE_ID}"

# --- Schema Definition for Dynamic Creation ---
# Defines the output structure expected in BigQuery
SCHEMA = [
    bigquery.SchemaField("col1", "STRING"),
    bigquery.SchemaField("col2", "STRING"),
    bigquery.SchemaField("col3", "STRING"),
    bigquery.SchemaField("project_id", "STRING"),
    bigquery.SchemaField("processed_by", "STRING"),
    bigquery.SchemaField("load_timestamp", "TIMESTAMP"),
]

def create_bigquery_table(table_id, schema):
    """Creates the BigQuery table using the defined schema."""
    try:
        table = bigquery.Table(table_id, schema=schema)
        bq_client.create_table(table)
        print(f"Dynamically created BigQuery table: {table_id}")
    except gcp_exceptions.Conflict:
        # Table already exists, ignore the error
        print(f"Table {table_id} already exists (Conflict error handled).")
    except Exception as e:
        # Re-raise any other critical error (like permission issues)
        print(f"FATAL BQ Table Creation Error: {e}")
        raise e


# --- Endpoints ---

@app.get("/")
def welcome():
    """Root endpoint for health check and general service info."""
    return {"status": "ok", "service": PROCESSOR_NAME, "message": "AIDE Parser Agent is running."}


@app.post("/pubsub-receiver")
async def pubsub_receiver(request: Request):
    """
    Handles the Pub/Sub push notification.
    Includes logic to create the BigQuery table if it's missing (self-healing).
    """
    
    # 1. Decode and Parse the Clean Payload
    try:
        data = await request.json()
        pubsub_message = data['message']['data']
        decoded_data = base64.b64decode(pubsub_message).decode('utf-8')
        payload = json.loads(decoded_data)
        
        project_id = payload.get("project_id")
        gcs_uri = payload.get("gcs_uri")
    except Exception as e:
        print(f"Error parsing Pub/Sub push or payload: {e}")
        return {"status": "success", "message": "Bad request format handled."}

    if not gcs_uri or not project_id:
        print("Payload missing GCS URI or project_id. Skipping.")
        return {"status": "success"}

    print(f"Processing GCS URI: {gcs_uri} for Project ID: {project_id}")

    # 2. Read the file from GCS and parse into DataFrame
    try:
        path_parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(path_parts[0])
        blob = bucket.blob(path_parts[1])
        
        file_content = blob.download_as_bytes()
        df = pd.read_csv(io.BytesIO(file_content)) 
    except Exception as e:
        print(f"Error reading/parsing GCS file {gcs_uri}: {e}")
        return {"status": "success", "message": "File read/parse failure, needs DLQ."}

    # 3. Transformation (Adding Isolation Context)
    df['project_id'] = project_id
    df['processed_by'] = PROCESSOR_NAME
    df['load_timestamp'] = pd.Timestamp.now(tz='UTC')
    print(f"Transformation applied. DataFrame size: {len(df)}")
    
    # 4. Load Data into BigQuery with Self-Healing Logic
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema=SCHEMA # Ensures consistent schema when appending
    )
    
    try:
        # FIRST ATTEMPT: Try to load the data assuming the table exists
        job = bq_client.load_table_from_dataframe(df, BQ_FULL_TABLE_ID, job_config=job_config)
        job.result()
        print(f"Data loaded successfully (First attempt). Rows: {job.output_rows}")
        return {"status": "success", "rows_loaded": job.output_rows}
        
    except gcp_exceptions.NotFound:
        print(f"Table {BQ_FULL_TABLE_ID} not found. Attempting creation...")
        try:
            # SECOND ATTEMPT: Create the table and re-run the load job
            create_bigquery_table(BQ_FULL_TABLE_ID, SCHEMA)
            
            # RE-LOAD JOB
            job = bq_client.load_table_from_dataframe(df, BQ_FULL_TABLE_ID, job_config=job_config)
            job.result()
            print(f"Data loaded successfully after dynamic creation. Rows: {job.output_rows}")
            return {"status": "success", "rows_loaded": job.output_rows}
            
        except Exception as create_e:
            print(f"BigQuery Creation/Load FAILED in retry: {create_e}")
            return {"status": "success", "message": "BigQuery creation/load failure logged."}
            
    except Exception as e:
        # Handle other non-NotFound BigQuery errors
        print(f"BigQuery Load FAILED: {e}")
        return {"status": "success", "message": "BigQuery load failure logged."}