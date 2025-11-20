# AI Agency - Complete Cloud Run Deployment Guide

Complete guide to deploy both backend and frontend to Google Cloud Run.

## Overview

This guide covers deploying the entire AI Agency system to Google Cloud Platform:

- **Backend**: FastAPI (Python 3.13) with Redis, Celery, and Google AI APIs
- **Frontend**: Next.js 14 with TypeScript and Tailwind CSS
- **Infrastructure**: Cloud Run, Cloud Memorystore (Redis), VPC, GCS

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Google Cloud Platform                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │   Cloud Run      │         │   Cloud Run      │        │
│  │   (Frontend)     │────────▶│   (Backend)      │        │
│  │   Next.js 14     │  HTTPS  │   FastAPI        │        │
│  │   Port: 8080     │  WSS    │   Port: 8080     │        │
│  └──────────────────┘         └────────┬─────────┘        │
│                                         │                   │
│                                         │                   │
│                          ┌──────────────┼──────────────┐   │
│                          │              │              │   │
│                    ┌─────▼─────┐  ┌────▼─────┐  ┌────▼────┐
│                    │   Redis   │  │   GCS    │  │ Google  │
│                    │ Memorystore│  │ Bucket   │  │ AI APIs │
│                    └───────────┘  └──────────┘  └─────────┘
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Google Cloud Project**: Active project with billing enabled
2. **gcloud CLI**: Installed and authenticated
3. **Git**: Repository access
4. **Docker**: Optional, for local testing

## Quick Deployment

Deploy everything with automated scripts:

### Step 1: Deploy Backend

```bash
cd backend

export GOOGLE_CLOUD_PROJECT="your-project-id"

# Run backend deployment
./deploy.sh

# Note the backend URL
BACKEND_URL=$(gcloud run services describe ai-agency-backend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Backend URL: $BACKEND_URL"
```

### Step 2: Deploy Frontend

```bash
cd ../frontend

export BACKEND_URL="$BACKEND_URL"
export WS_URL="${BACKEND_URL/https/wss}"

# Run frontend deployment
./deploy.sh

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe ai-agency-frontend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Frontend URL: $FRONTEND_URL"
```

### Step 3: Update Backend CORS

Edit `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "YOUR_FRONTEND_URL_HERE",  # Add your Cloud Run frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Redeploy backend:

```bash
cd backend
gcloud builds submit --tag gcr.io/$GOOGLE_CLOUD_PROJECT/ai-agency-backend:latest
gcloud run deploy ai-agency-backend \
    --image gcr.io/$GOOGLE_CLOUD_PROJECT/ai-agency-backend:latest \
    --region us-central1
```

### Step 4: Test Deployment

```bash
# Test backend
curl $BACKEND_URL/health

# Test frontend
curl $FRONTEND_URL/api/health

# Open in browser
echo "Visit: $FRONTEND_URL"
```

## Detailed Deployment

For step-by-step instructions with full configuration:

- **Backend**: See [backend/CLOUD_RUN_DEPLOYMENT.md](./backend/CLOUD_RUN_DEPLOYMENT.md)
- **Frontend**: See [frontend/CLOUD_RUN_DEPLOYMENT.md](./frontend/CLOUD_RUN_DEPLOYMENT.md)

## Infrastructure Setup

### 1. Enable APIs

```bash
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    redis.googleapis.com \
    aiplatform.googleapis.com \
    storage-api.googleapis.com \
    secretmanager.googleapis.com
```

### 2. Create Redis Instance

```bash
gcloud redis instances create ai-agency-redis \
    --size=1 \
    --region=us-central1 \
    --redis-version=redis_7_0 \
    --tier=basic
```

### 3. Create VPC Connector

```bash
gcloud compute networks vpc-access connectors create ai-agency-connector \
    --region=us-central1 \
    --network=default \
    --range=10.8.0.0/28 \
    --min-instances=2 \
    --max-instances=3
```

### 4. Create GCS Bucket

```bash
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://ai-agency-assets-$PROJECT_ID/

# Create folder structure
gsutil -m mkdir \
    gs://ai-agency-assets-$PROJECT_ID/images/ \
    gs://ai-agency-assets-$PROJECT_ID/videos/ \
    gs://ai-agency-assets-$PROJECT_ID/audio/
```

### 5. Configure Secrets

```bash
# Create Gemini API Key secret
echo -n "your-gemini-api-key" | gcloud secrets create gemini-api-key --data-file=-

# Grant access to Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
```

## Environment Variables

### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP Project ID |
| `GEMINI_API_KEY` | Yes | Gemini API Key (Secret) |
| `REDIS_HOST` | Yes | Cloud Memorystore IP |
| `GCS_BUCKET_NAME` | Yes | GCS bucket name |
| `ENVIRONMENT` | No | Environment name |

### Frontend

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | Backend URL (build-time) |
| `NEXT_PUBLIC_WS_URL` | Yes | WebSocket URL (build-time) |

## Deployment Checklist

### Backend Deployment

- [ ] Redis instance created
- [ ] VPC connector configured
- [ ] GCS bucket created
- [ ] Secrets configured
- [ ] Backend deployed
- [ ] Health check passing

### Frontend Deployment

- [ ] Backend URL obtained
- [ ] Frontend built with correct env vars
- [ ] Frontend deployed
- [ ] Health check passing

### Post-Deployment

- [ ] CORS configured in backend
- [ ] Both services communicating
- [ ] WebSocket connections working
- [ ] Assets loading correctly
- [ ] Monitoring configured
- [ ] Alerts set up

## Monitoring and Logging

### View Logs

```bash
# Backend logs
gcloud run services logs tail ai-agency-backend --region us-central1

# Frontend logs
gcloud run services logs tail ai-agency-frontend --region us-central1
```

### Monitoring Dashboard

1. Navigate to Cloud Console → Cloud Run
2. Select service → Metrics tab
3. View request count, latency, errors

### Set Up Alerts

Create alerts for:
- High error rates (> 5%)
- High latency (> 2s p95)
- Redis connection failures
- Memory usage (> 80%)

## Troubleshooting

### Backend Issues

**Redis Connection Fails**:
- Verify VPC connector attached
- Check Redis host IP
- Ensure VPC egress = `all-traffic`

**API Errors**:
- Check Gemini API key is valid
- Verify secrets are accessible
- Review logs for details

### Frontend Issues

**Can't Connect to Backend**:
- Verify backend URL is correct
- Check CORS configuration
- Test backend health endpoint

**WebSocket Fails**:
- Ensure WS URL uses `wss://`
- Check backend WebSocket endpoint
- Verify Cloud Run timeout settings

## Production Best Practices

### 1. Use Cloud Build Triggers

Set up automatic deployments:

```bash
# Backend trigger
gcloud builds triggers create github \
    --repo-name=ai-agency \
    --repo-owner=your-username \
    --branch-pattern="^main$" \
    --build-config=backend/cloudbuild.yaml

# Frontend trigger
gcloud builds triggers create github \
    --repo-name=ai-agency \
    --repo-owner=your-username \
    --branch-pattern="^main$" \
    --build-config=frontend/cloudbuild.yaml \
    --substitutions="_BACKEND_URL=https://backend.run.app,_WS_URL=wss://backend.run.app"
```

### 2. Configure Custom Domains

```bash
# Backend
gcloud run domain-mappings create \
    --service ai-agency-backend \
    --domain api.yourdomain.com \
    --region us-central1

# Frontend
gcloud run domain-mappings create \
    --service ai-agency-frontend \
    --domain app.yourdomain.com \
    --region us-central1
```

### 3. Enable CDN (Frontend)

For better static asset performance:
- Set up Cloud Load Balancer
- Enable Cloud CDN
- Configure cache headers

### 4. Set Minimum Instances

Reduce cold starts in production:

```bash
# Backend
gcloud run services update ai-agency-backend \
    --region us-central1 \
    --min-instances 1

# Frontend
gcloud run services update ai-agency-frontend \
    --region us-central1 \
    --min-instances 1
```

### 5. Use Standard Tier Redis

For production high availability:

```bash
gcloud redis instances create ai-agency-redis-prod \
    --size=5 \
    --region=us-central1 \
    --redis-version=redis_7_0 \
    --tier=standard-ha \
    --replica-count=1
```

## Cost Estimation

### Development Environment

- Cloud Run Backend: ~$10-20/month
- Cloud Run Frontend: ~$5-10/month
- Redis Basic (1GB): ~$40/month
- VPC Connector: ~$10/month
- **Total**: ~$65-80/month

### Production Environment

- Cloud Run Backend (1 min instance): ~$50-100/month
- Cloud Run Frontend (1 min instance): ~$30-50/month
- Redis Standard (5GB HA): ~$200/month
- VPC Connector: ~$20/month
- GCS: ~$5-20/month
- **Total**: ~$305-390/month

## Cleanup

To delete all resources:

```bash
# Delete Cloud Run services
gcloud run services delete ai-agency-backend --region us-central1 --quiet
gcloud run services delete ai-agency-frontend --region us-central1 --quiet

# Delete Redis
gcloud redis instances delete ai-agency-redis --region us-central1 --quiet

# Delete VPC connector
gcloud compute networks vpc-access connectors delete ai-agency-connector --region us-central1 --quiet

# Delete GCS bucket
gsutil -m rm -r gs://ai-agency-assets-$PROJECT_ID/

# Delete container images
gcloud container images delete gcr.io/$PROJECT_ID/ai-agency-backend --quiet
gcloud container images delete gcr.io/$PROJECT_ID/ai-agency-frontend --quiet

# Delete secrets
gcloud secrets delete gemini-api-key --quiet
```

## CI/CD Pipeline

### Automated Deployment Flow

```
Git Push to main
      │
      ▼
Cloud Build Trigger
      │
      ├──► Build Backend Image
      │    Push to Container Registry
      │    Deploy to Cloud Run
      │
      └──► Build Frontend Image
           Push to Container Registry
           Deploy to Cloud Run
```

### Set Up GitHub Integration

1. Connect your repository:
   ```bash
   gcloud alpha builds connections create github ai-agency-connection \
       --region=us-central1
   ```

2. Create triggers (see above)

3. Push to trigger deployment:
   ```bash
   git push origin main
   ```

## Security Considerations

### 1. Service-to-Service Authentication

Configure IAM for service accounts:

```bash
# Backend can access secrets
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
```

### 2. Network Security

- VPC connector isolates Redis traffic
- Cloud Run enforces HTTPS
- WebSocket encrypted (WSS)

### 3. API Keys

- Store in Secret Manager
- Rotate regularly
- Never commit to git

### 4. CORS Configuration

- Whitelist specific origins
- Don't use `*` in production
- Validate in backend

## Performance Optimization

### Backend

1. **Connection Pooling**: Redis connections reused
2. **Async Operations**: FastAPI async handlers
3. **Celery Workers**: Offload long tasks
4. **Caching**: Redis for frequently accessed data

### Frontend

1. **Standalone Build**: Reduces image size 5x
2. **Code Splitting**: Automatic in Next.js
3. **Static Optimization**: Pre-rendered pages
4. **Image Optimization**: Next.js Image component

## Support Resources

- [Backend Deployment Guide](./backend/CLOUD_RUN_DEPLOYMENT.md)
- [Frontend Deployment Guide](./frontend/CLOUD_RUN_DEPLOYMENT.md)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

## Getting Help

1. Check service logs
2. Review health endpoints
3. Verify environment variables
4. Test locally with Docker
5. Check Cloud Console monitoring

## Next Steps After Deployment

1. **Test thoroughly**: Verify all features work
2. **Set up monitoring**: Configure alerts
3. **Configure custom domains**: Use friendly URLs
4. **Enable HTTPS**: Automatic with Cloud Run
5. **Set up CI/CD**: Automate deployments
6. **Performance testing**: Load test your application
7. **Security audit**: Review IAM and CORS settings
8. **Documentation**: Update with your specific URLs

---

**Congratulations!** Your AI Agency is now running on Google Cloud Run.

Visit your frontend URL to start using the application.
