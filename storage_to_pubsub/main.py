import functions_framework
import os
import json
from google.cloud import pubsub_v1
import uuid

# Configuration (Assumes GCP_PROJECT is set in the environment)
# Configuration
# Use the most reliable environment variables for the Project ID in a GCP runtime
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', "social-463809")
if not PROJECT_ID:
    print("FATAL: Cannot determine Project ID from environment variables.")
    # Raise an error or exit if the project ID cannot be found.
    # We will trust the environment for now and assume one of the two works.

PUB_SUB_TOPIC = "aidelab.new_upload"

# Initialize Pub/Sub Client
publisher = pubsub_v1.PublisherClient()

# --- Helper Function for PID Extraction ---
def extract_pid_from_path(file_path):
    """Extracts the Project ID (the first directory prefix) from the GCS file path."""
    if file_path:
        # Splits the path by '/' and returns the first segment (e.g., 'PID-1234')
        return file_path.split('/')[0]
    return None
    
# --- The Cloud Function Triggered by GCS ---
@functions_framework.cloud_event
def gatekeeper_on_file_upload(cloud_event):
    """
    Triggers on a new file upload (finalize event) in Cloud Storage.
    Extracts the file path and uses the PID from the path as the project_id.
    Publishes a message to Pub/Sub.
    """
    
    # 1. Get the data from the CloudEvent
    data = cloud_event.data
    
    bucket_name = data.get('bucket')
    file_path = data.get('name') 
    
    if not file_path:
        print("No file name found in event data. Exiting.")
        return

    # 2. Extract the Project ID (PID)
    project_id = extract_pid_from_path(file_path)
    
    # Fallback to a generated PID if the file was uploaded without a prefix.
    # We expect the PID to be in the path for this experiment.
    if not project_id or not project_id.startswith("PID-"):
        project_id = f"PID-{uuid.uuid4().hex[:8]}" 
        print(f"File uploaded without a valid PID prefix. Using generated PID: {project_id}")
    else:
        print(f"Successfully extracted existing Project ID: {project_id}")


    # 3. Construct the Pub/Sub message
    gcs_uri = f"gs://{bucket_name}/{file_path}"
    topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_TOPIC)
    
    message_payload = {
        "project_id": project_id,
        "gcs_uri": gcs_uri,
        "source_file_path": file_path,
        "event_type": "google.storage.object.finalize"
    }
    
    # Message data must be a byte string
    message_data = json.dumps(message_payload).encode("utf-8")

    # 4. Publish the message to the aidelab.new_upload topic
    try:
        publish_future = publisher.publish(topic_path, message_data)
        message_id = publish_future.result() # Blocks until publish confirms
        print(f"Message published to {PUB_SUB_TOPIC}. Message ID: {message_id}")
    except Exception as e:
        print(f"Error publishing message: {e}")
        raise # Re-raise to signal failure for Cloud Function retry mechanism