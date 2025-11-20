# Quick Start: Deploy to Cloud Run

Get your AI Agency backend running on Cloud Run in 10 minutes.

## Prerequisites

- Google Cloud Project with billing enabled
- gcloud CLI installed and authenticated

## Deployment Steps

### 1. Set Project ID

```bash
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID
```

### 2. Enable APIs

```bash
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    redis.googleapis.com
```

### 3. Create Redis Instance

```bash
gcloud redis instances create ai-agency-redis \
    --size=1 \
    --region=us-central1 \
    --redis-version=redis_7_0 \
    --tier=basic
```

### 4. Create VPC Connector

```bash
gcloud compute networks vpc-access connectors create ai-agency-connector \
    --region=us-central1 \
    --network=default \
    --range=10.8.0.0/28
```

### 5. Create GCS Bucket

```bash
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://ai-agency-assets-$PROJECT_ID/
```

### 6. Deploy Using Script

```bash
cd backend
./deploy.sh
```

### 7. Set Secrets

```bash
# Create Gemini API Key secret
echo -n "your-gemini-api-key" | gcloud secrets create gemini-api-key --data-file=-

# Update deployment with secrets
REDIS_HOST=$(gcloud redis instances describe ai-agency-redis --region=us-central1 --format='value(host)')

gcloud run services update ai-agency-backend \
    --region us-central1 \
    --vpc-connector ai-agency-connector \
    --vpc-egress all-traffic \
    --set-env-vars "REDIS_HOST=${REDIS_HOST}" \
    --set-env-vars "GCS_BUCKET_NAME=ai-agency-assets-${PROJECT_ID}" \
    --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"
```

### 8. Test Deployment

```bash
SERVICE_URL=$(gcloud run services describe ai-agency-backend --region us-central1 --format 'value(status.url)')
curl $SERVICE_URL/health
```

Expected response:
```json
{
  "status": "healthy",
  "redis": "connected",
  "environment": "production"
}
```

## Done!

Your backend is now live at the SERVICE_URL. Update your frontend's `NEXT_PUBLIC_BACKEND_URL` to point to this URL.

## Next Steps

- Review the full [CLOUD_RUN_DEPLOYMENT.md](./CLOUD_RUN_DEPLOYMENT.md) for detailed configuration
- Set up monitoring and alerts
- Configure custom domain (optional)
- Set up CI/CD with Cloud Build triggers

## Cleanup

To delete everything:

```bash
gcloud run services delete ai-agency-backend --region us-central1 --quiet
gcloud redis instances delete ai-agency-redis --region us-central1 --quiet
gcloud compute networks vpc-access connectors delete ai-agency-connector --region us-central1 --quiet
gsutil -m rm -r gs://ai-agency-assets-$PROJECT_ID/
```
