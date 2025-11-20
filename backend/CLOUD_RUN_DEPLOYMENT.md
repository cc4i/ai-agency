# Cloud Run Deployment Guide

Complete guide to deploy the AI Agency Backend to Google Cloud Run.

## Prerequisites

1. **Google Cloud Project**: Active GCP project with billing enabled
2. **gcloud CLI**: Installed and authenticated ([Install Guide](https://cloud.google.com/sdk/docs/install))
3. **Docker**: Installed locally for testing (optional)
4. **APIs Enabled**: Cloud Run, Cloud Build, Container Registry, Redis

## Architecture Overview

```
┌─────────────────┐
│   Cloud Run     │
│  (FastAPI App)  │
│   Port: 8080    │
└────────┬────────┘
         │
         ├─────► Redis (Cloud Memorystore)
         │
         ├─────► Google AI APIs (Gemini, Imagen, Veo, Lyria)
         │
         └─────► Cloud Storage (GCS)
```

## Quick Deployment (Recommended)

### Option 1: Using the Deployment Script

```bash
cd backend

# Set your project ID
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Run the deployment script
./deploy.sh
```

The script will:
1. Enable required APIs
2. Build the container image
3. Deploy to Cloud Run
4. Display the service URL

### Option 2: Manual Deployment Steps

Follow the detailed steps below for more control.

---

## Detailed Deployment Steps

### Step 1: Set Up Google Cloud Project

```bash
# Authenticate with Google Cloud
gcloud auth login

# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    redis.googleapis.com \
    aiplatform.googleapis.com \
    storage-api.googleapis.com
```

### Step 2: Set Up Redis (Cloud Memorystore)

Cloud Run requires an external Redis instance. Use Cloud Memorystore:

```bash
# Create Redis instance (Basic tier for development, Standard for production)
gcloud redis instances create ai-agency-redis \
    --size=1 \
    --region=us-central1 \
    --redis-version=redis_7_0 \
    --tier=basic

# Get the Redis host (internal IP)
REDIS_HOST=$(gcloud redis instances describe ai-agency-redis \
    --region=us-central1 \
    --format='value(host)')

echo "Redis Host: $REDIS_HOST"
```

**Note**: Cloud Memorystore instances are only accessible from within the same VPC. You'll need to configure VPC connector (see Step 5).

### Step 3: Set Up Serverless VPC Access

To connect Cloud Run to Redis (Cloud Memorystore):

```bash
# Create VPC connector
gcloud compute networks vpc-access connectors create ai-agency-connector \
    --region=us-central1 \
    --network=default \
    --range=10.8.0.0/28 \
    --min-instances=2 \
    --max-instances=3
```

### Step 4: Create Google Cloud Storage Bucket

For storing generated assets (images, videos, audio):

```bash
# Create GCS bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://ai-agency-assets-$PROJECT_ID/

# Create folder structure
gsutil -m mkdir \
    gs://ai-agency-assets-$PROJECT_ID/images/ \
    gs://ai-agency-assets-$PROJECT_ID/videos/ \
    gs://ai-agency-assets-$PROJECT_ID/audio/

# Set CORS for web access
cat > cors.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

gsutil cors set cors.json gs://ai-agency-assets-$PROJECT_ID/
```

### Step 5: Build and Push Container Image

```bash
cd backend

# Build using Cloud Build (recommended)
gcloud builds submit --tag gcr.io/$PROJECT_ID/ai-agency-backend:latest

# Alternative: Build locally and push
# docker build -t gcr.io/$PROJECT_ID/ai-agency-backend:latest .
# docker push gcr.io/$PROJECT_ID/ai-agency-backend:latest
```

### Step 6: Set Up Secrets

Store sensitive configuration in Secret Manager:

```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create secrets
echo -n "your-gemini-api-key" | gcloud secrets create gemini-api-key --data-file=-
echo -n "$PROJECT_ID" | gcloud secrets create google-cloud-project --data-file=-

# Grant Cloud Run service account access
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding google-cloud-project \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 7: Deploy to Cloud Run

```bash
# Get Redis host from earlier step
REDIS_HOST=$(gcloud redis instances describe ai-agency-redis \
    --region=us-central1 \
    --format='value(host)')

# Deploy with all configuration
gcloud run deploy ai-agency-backend \
    --image gcr.io/$PROJECT_ID/ai-agency-backend:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300s \
    --max-instances 10 \
    --min-instances 0 \
    --port 8080 \
    --vpc-connector ai-agency-connector \
    --vpc-egress all-traffic \
    --set-env-vars "ENVIRONMENT=production" \
    --set-env-vars "LOG_LEVEL=INFO" \
    --set-env-vars "REDIS_HOST=${REDIS_HOST}" \
    --set-env-vars "REDIS_PORT=6379" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --set-env-vars "GOOGLE_CLOUD_LOCATION=us-central1" \
    --set-env-vars "GCS_BUCKET_NAME=ai-agency-assets-${PROJECT_ID}" \
    --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"
```

### Step 8: Verify Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe ai-agency-backend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/health

# Expected output:
# {
#   "status": "healthy",
#   "redis": "connected",
#   "environment": "production"
# }
```

---

## Environment Variables Reference

Configure these via `--set-env-vars` flag:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP Project ID | - |
| `GOOGLE_CLOUD_LOCATION` | Yes | GCP Region | `us-central1` |
| `GEMINI_API_KEY` | Yes | Gemini API Key (use Secret) | - |
| `REDIS_HOST` | Yes | Redis host (Cloud Memorystore IP) | `localhost` |
| `REDIS_PORT` | No | Redis port | `6379` |
| `REDIS_PASSWORD` | No | Redis password (if auth enabled) | - |
| `GCS_BUCKET_NAME` | Yes | GCS bucket for assets | - |
| `ENVIRONMENT` | No | Environment name | `production` |
| `LOG_LEVEL` | No | Logging level | `INFO` |
| `DEBUG` | No | Debug mode | `false` |

---

## Updating the Deployment

### Update Code

```bash
cd backend

# Rebuild and deploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/ai-agency-backend:latest

gcloud run deploy ai-agency-backend \
    --image gcr.io/$PROJECT_ID/ai-agency-backend:latest \
    --region us-central1
```

### Update Environment Variables

```bash
gcloud run services update ai-agency-backend \
    --region us-central1 \
    --set-env-vars "NEW_VAR=value"
```

### Update Secrets

```bash
# Update secret value
echo -n "new-api-key" | gcloud secrets versions add gemini-api-key --data-file=-

# Cloud Run will automatically use the latest version
```

---

## Monitoring and Logging

### View Logs

```bash
# Stream logs
gcloud run services logs tail ai-agency-backend --region us-central1

# View in Cloud Console
gcloud run services describe ai-agency-backend \
    --region us-central1 \
    --format='value(status.url)' | \
    xargs -I {} echo "Logs: https://console.cloud.google.com/logs"
```

### Monitoring Metrics

```bash
# View service metrics in Cloud Console
gcloud run services describe ai-agency-backend \
    --region us-central1 \
    --format='value(metadata.selfLink)' | \
    xargs -I {} echo "Metrics: https://console.cloud.google.com/run"
```

---

## Troubleshooting

### Redis Connection Fails

**Symptom**: `/health` returns `"redis": "disconnected"`

**Solution**:
1. Verify VPC connector is attached:
   ```bash
   gcloud run services describe ai-agency-backend \
       --region us-central1 \
       --format='value(spec.template.spec.vpcAccess.connector)'
   ```
2. Verify Redis host is correct:
   ```bash
   gcloud redis instances describe ai-agency-redis \
       --region=us-central1 \
       --format='value(host)'
   ```
3. Ensure VPC egress is set to `all-traffic`

### Container Fails to Start

**Symptom**: Service shows unhealthy status

**Solution**:
1. Check logs:
   ```bash
   gcloud run services logs tail ai-agency-backend --region us-central1
   ```
2. Verify all required environment variables are set
3. Test container locally:
   ```bash
   docker build -t test-backend .
   docker run -p 8080:8080 \
       -e REDIS_HOST=localhost \
       -e GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
       test-backend
   ```

### WebSocket Connection Errors

**Symptom**: WebSocket connections fail or timeout

**Solution**:
1. Increase timeout:
   ```bash
   gcloud run services update ai-agency-backend \
       --region us-central1 \
       --timeout 900s
   ```
2. Cloud Run supports WebSocket but has a 60-minute limit
3. For long-running connections, consider Cloud Run for Anthos or GKE

### Memory Issues

**Symptom**: Container crashes with OOM errors

**Solution**:
```bash
gcloud run services update ai-agency-backend \
    --region us-central1 \
    --memory 4Gi \
    --cpu 4
```

---

## Production Best Practices

### 1. Use Cloud Build Triggers

Set up automatic deployments on git push:

```bash
gcloud builds triggers create github \
    --repo-name=ai-agency \
    --repo-owner=your-github-username \
    --branch-pattern="^main$" \
    --build-config=backend/cloudbuild.yaml
```

### 2. Enable Container Scanning

```bash
gcloud services enable containerscanning.googleapis.com
```

### 3. Set Up Uptime Checks

Create uptime checks for the health endpoint:
- Navigate to Cloud Console → Monitoring → Uptime checks
- Create check for `$SERVICE_URL/health`

### 4. Configure Alerts

Set up alerts for:
- High error rates
- High latency
- Redis connection failures
- Memory/CPU usage

### 5. Use Managed Redis (Standard Tier)

For production, use Standard tier with high availability:

```bash
gcloud redis instances create ai-agency-redis-prod \
    --size=5 \
    --region=us-central1 \
    --redis-version=redis_7_0 \
    --tier=standard-ha \
    --replica-count=1
```

---

## Cost Optimization

1. **Min Instances**: Set to 0 for development, 1+ for production
2. **Memory**: Start with 2Gi, scale based on usage
3. **Redis**: Basic tier for dev, Standard for production
4. **VPC Connector**: Use minimum instances (2) for development

### Estimated Monthly Costs (Low Traffic)

- Cloud Run: ~$10-50/month (depends on traffic)
- Redis Basic (1GB): ~$40/month
- VPC Connector: ~$10/month
- **Total**: ~$60-100/month

---

## Cleanup

To delete all resources:

```bash
# Delete Cloud Run service
gcloud run services delete ai-agency-backend --region us-central1

# Delete Redis instance
gcloud redis instances delete ai-agency-redis --region us-central1

# Delete VPC connector
gcloud compute networks vpc-access connectors delete ai-agency-connector --region us-central1

# Delete GCS bucket
gsutil -m rm -r gs://ai-agency-assets-$PROJECT_ID/

# Delete container images
gcloud container images delete gcr.io/$PROJECT_ID/ai-agency-backend --quiet
```

---

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Memorystore for Redis](https://cloud.google.com/memorystore/docs/redis)
- [Serverless VPC Access](https://cloud.google.com/vpc/docs/configure-serverless-vpc-access)
- [Secret Manager](https://cloud.google.com/secret-manager/docs)
- [Cloud Build](https://cloud.google.com/build/docs)

---

## Support

For issues specific to this deployment:
1. Check logs: `gcloud run services logs tail ai-agency-backend --region us-central1`
2. Verify configuration: `gcloud run services describe ai-agency-backend --region us-central1`
3. Review Cloud Console monitoring dashboards
