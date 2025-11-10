##  Step 1: BigQuery Dataset Setup
The first step is to ensure the BigQuery destination dataset exists.

```powershell
# Create the BigQuery dataset to hold all processed AIDE data
# Using a single dataset for the MVP is simple and sufficient for internal isolation.
bq mk --dataset social-463809:aidelab_processed
bq ls
```

# **Critical : Grant BigQuery Data Editor Role to Cloud Run Service Account**

$CR_SA = "797563351214-compute@developer.gserviceaccount.com"
$PROJECT_ID = "social-463809"

# Grant BigQuery Permissions
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CR_SA" `
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CR_SA" `
    --role="roles/bigquery.jobUser"

# Grant GCS Read Permission
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CR_SA" `
    --role="roles/storage.objectViewer"

## step 2: set up your fast api app for receiving pub/sub messages and writing to BigQuery

## step 3: deploy the Cloud Run service
```powershell
$SERVICE_NAME="aide-parser-agent"
$REGION="us-central1"

gcloud run deploy $SERVICE_NAME `
    --source . `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated # Needed for Pub/Sub push
```

## step 4: create the Pub/Sub subscription to push to Cloud Run

```powershell
$TOPIC_NAME="aidelab.new_upload"
# Use the URL from your successful deployment output
$SERVICE_URL="https://aide-parser-agent-797563351214.us-central1.run.app" 
$SERVICE_NAME="aide-parser-agent"


# Create the new subscription pointing to the dedicated push path
gcloud pubsub subscriptions create $SERVICE_NAME-sub `
    --topic $TOPIC_NAME `
    --push-endpoint="${SERVICE_URL}/pubsub-receiver" `
    --expiration-period 24h
```

## Create a csv file to use for testing

```powershell
# 1. Define the content (header + two data rows)
# The `n` character creates a new line within the string literal.
$CSV_CONTENT = "col1,col2,col3`napple,red,small`nbanana,yellow,large"

# 2. Write the content to the file
# Using Out-File with -Encoding ASCII ensures a clean file for gsutil/Pandas
$CSV_CONTENT | Out-File -Encoding ASCII test_data.csv
```

### upload the test file to GCS to trigger the end-to-end flow

```powershell
$BUCKET_NAME = "aidelab-raw-uploads-mvp01"
$TEST_PID = "PID-J1K2L3M4" 
$UPLOAD_PATH = "gs://${BUCKET_NAME}/${TEST_PID}/project_data_final.csv"

# Use the new file you just created
gsutil cp test_data.csv $UPLOAD_PATH
```
## Monitor the Cloud Run logs to see the processing in action:

```powershell
$SERVICE_NAME = "aide-parser-agent"
$REGION = "us-central1"
gcloud run services logs read $SERVICE_NAME --region $REGION --limit 20
``` 
## BigQuery Verification
After the file is processed, verify that the data has been correctly inserted into BigQuery by running a simple query:

```powershell
$BQ_QUERY = "SELECT col1, col2, project_id, processed_by FROM aidelab_processed.transformed_data WHERE project_id = 'PID-N5O6P7Q8'"
bq query --nouse_legacy_sql $BQ_QUERY
```
Reslult:
+--------+--------+--------------+---------------------+
|  col1  |  col2  |  project_id  |    processed_by     |
+--------+--------+--------------+---------------------+
| apple  | red    | PID-N5O6P7Q8 | CloudRunParserAgent |
| banana | yellow | PID-N5O6P7Q8 | CloudRunParserAgent |
+--------+--------+--------------+---------------------+