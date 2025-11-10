## Step 1: Create the Cloud Storage Bucket

```powershell
# Replace [YOUR_UNIQUE_SUFFIX] with your chosen identifier
$BUCKET_NAME = "aidelab-raw-uploads-mvp01"
$REGION = "us-central1"

gcloud storage buckets create gs://$BUCKET_NAME `
    --location=$REGION `
    --default-storage-class=STANDARD `
    --uniform-bucket-level-access
```

## Step 2: create the Pub/Sub Topic

```powershell
$TOPIC_NAME="aidelab.new_upload"
gcloud pubsub topics create ${TOPIC_NAME}
```
## step 3: verify the Pub/Sub Topic was created and bucket exists

```powershell
# Verify the Bucket
gcloud storage ls 

# Verify the Topic
gcloud pubsub topics list --filter="${TOPIC_NAME}"

```


## step 4 : create and deploy the Cloud Function

```powershell
# Set your variables first (replace YOUR_BUCKET_NAME)
$FUNCTION_NAME="gatekeeper-on-file-upload"
$BUCKET_NAME = "aidelab-raw-uploads-mvp01"
$REGION="us-central1" # Must match your bucket's region

gcloud functions deploy ${FUNCTION_NAME} `
    --gen2 `
    --runtime python311 `
    --region ${REGION} `
    --source . `
    --entry-point gatekeeper_on_file_upload `
    --trigger-bucket ${BUCKET_NAME} `
    --trigger-event google.cloud.storage.object.v1.finalized
```
output:
```
(base) PS C:\Users\barad\OneDrive\Desktop\GoogleCloudApplication\gcp_lae\storage_to_pubsub> gcloud functions deploy $FUNCTION_NAME `                                    
>>     --gen2 `
>>     --runtime python311 `
>>     --region $REGION `
>>     --source . `
>>     --entry-point gatekeeper_on_file_upload `
>>     --trigger-event google.cloud.storage.object.v1.finalized `
>>     --trigger-resource $BUCKET_NAME
Preparing function...done.
X  Updating function (may take a while)...
  OK [Build] Logs are available at [https://console.cloud.google.com/cloud-build/builds;region=us-central1/0636cb53-c
  10b-49d5-a550-1f16a812c906?project=797563351214]
     [Service]
  OK [Trigger]
  .  [ArtifactRegistry]
  .  [Healthcheck]
  .  [Triggercheck]
Completed with warnings:
  [WARNING] Cloud Run service projects/social-463809/locations/us-central1/services/gatekeeper-on-file-upload for the function was not found. The service was redeployed with default values.
You can view your function in the Cloud Console here: https://console.cloud.google.com/functions/details/us-central1/gatekeeper-on-file-upload?project=social-463809

buildConfig:
  automaticUpdatePolicy: {}
  build: projects/797563351214/locations/us-central1/builds/0636cb53-c10b-49d5-a550-1f16a812c906
  dockerRegistry: ARTIFACT_REGISTRY
  dockerRepository: projects/social-463809/locations/us-central1/repositories/gcf-artifacts
  entryPoint: gatekeeper_on_file_upload
  runtime: python311
  serviceAccount: projects/social-463809/serviceAccounts/797563351214-compute@developer.gserviceaccount.com
  source:
    storageSource:
      bucket: gcf-v2-sources-797563351214-us-central1
      generation: '1762721792494807'
      object: gatekeeper-on-file-upload/function-source.zip
  sourceProvenance:
    resolvedStorageSource:
      bucket: gcf-v2-sources-797563351214-us-central1
      generation: '1762721792494807'
      object: gatekeeper-on-file-upload/function-source.zip
createTime: '2025-11-09T20:46:03.537057676Z'
environment: GEN_2
eventTrigger:
  eventFilters:
  - attribute: bucket
    value: aidelab-raw-uploads-mvp01
  eventType: google.cloud.storage.object.v1.finalized
  pubsubTopic: projects/social-463809/topics/eventarc-us-central1-gatekeeper-on-file-upload-786637-672
  retryPolicy: RETRY_POLICY_DO_NOT_RETRY
  serviceAccountEmail: 797563351214-compute@developer.gserviceaccount.com
  trigger: projects/social-463809/locations/us-central1/triggers/gatekeeper-on-file-upload-786637
  triggerRegion: us-central1
labels:
  deployment-tool: cli-gcloud
name: projects/social-463809/locations/us-central1/functions/gatekeeper-on-file-upload
satisfiesPzi: true
serviceConfig:
  allTrafficOnLatestRevision: true
  availableCpu: '0.1666'
  availableMemory: 256M
  environmentVariables:
    LOG_EXECUTION_ID: 'true'
  ingressSettings: ALLOW_ALL
  maxInstanceCount: 12
  maxInstanceRequestConcurrency: 1
  revision: gatekeeper-on-file-upload-00001-tuj
  service: projects/social-463809/locations/us-central1/services/gatekeeper-on-file-upload
  serviceAccountEmail: 797563351214-compute@developer.gserviceaccount.com
  timeoutSeconds: 60
  uri: https://gatekeeper-on-file-upload-y73vpw3mwa-uc.a.run.app
state: ACTIVE
updateTime: '2025-11-09T20:57:29.150369247Z'
url: https://us-central1-social-463809.cloudfunctions.net/gatekeeper-on-file-upload
```
### iam permissions for Cloud Function to publish to Pub/Sub Topic (if needed, run before step 4 or redeploy the function after it)

```powershell
gcloud projects describe social-463809 --format="value(projectNumber)"
```
it will return a number like 79756*****

```powershell
$GCS_SA = "service-79756*****@gs-project-accounts.iam.gserviceaccount.com"
---
**Grant the Pub/Sub Publisher Role** 

Now, grant this service account the necessary permission (roles/pubsub.publisher) on your current project (social-463809).

```PowerShell

gcloud projects add-iam-policy-binding social-463809 `
    --member="serviceAccount:$GCS_SA" `
    --role="roles/pubsub.publisher"

```


# Testing the Setup
## crating a test file and uploading it to the bucket

```powershell 
"This is test data for AIDE project isolation confirmation." | Out-File -Encoding ASCII test_file.txt
```

```powershell
$BUCKET_NAME = "aidelab-raw-uploads-mvp01"
$TEST_PID = "PID-T7A1C2B9"
$UPLOAD_PATH = "gs://${BUCKET_NAME}/${TEST_PID}/transport_company_data_01.csv"

gsutil cp test_file.txt $UPLOAD_PATH
```

#### Create a temporary subscription to the Pub/Sub Topic to see the messages being published when the file is uploaded.

```powershell
gcloud pubsub subscriptions create TEMP_TEST_SUB --topic aidelab.new_upload --expiration-period 24h
```

#### Pull the Message Data: Once the subscription is created, the new message (the one published by the function in the last successful run) should be immediately available.
```powershell
gcloud pubsub subscriptions pull TEMP_TEST_SUB --limit=10 --auto-ack
```

## step optionally: Create the Notification on the Bucket to Publish to Pub/Sub Topic

```powershell
gcloud storage buckets notifications create gs://$BUCKET_NAME `
    --topic=$TOPIC_NAME `
    --event-types=OBJECT_FINALIZE `
    --payload-format="JSON_API_V1"
```

