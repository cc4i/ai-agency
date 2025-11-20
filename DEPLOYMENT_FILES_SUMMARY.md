# Deployment Files Summary

All files created for Cloud Run deployment of AI Agency.

## Files Created

### Root Directory

- **`DEPLOYMENT_GUIDE.md`** - Complete deployment guide for both backend and frontend

### Backend Directory (`backend/`)

1. **`Dockerfile`** - Multi-stage Docker build for Python 3.13 FastAPI app
2. **`.dockerignore`** - Excludes unnecessary files from container image
3. **`deploy.sh`** - Automated deployment script (executable)
4. **`cloudbuild.yaml`** - Cloud Build configuration for CI/CD
5. **`CLOUD_RUN_DEPLOYMENT.md`** - Comprehensive backend deployment guide
6. **`QUICKSTART_CLOUD_RUN.md`** - Quick 10-minute backend deployment guide

### Frontend Directory (`frontend/`)

1. **`Dockerfile`** - Multi-stage Docker build for Next.js 14
2. **`.dockerignore`** - Excludes unnecessary files from container image
3. **`deploy.sh`** - Automated deployment script (executable)
4. **`cloudbuild.yaml`** - Cloud Build configuration for CI/CD
5. **`next.config.production.js`** - Production-specific Next.js configuration
6. **`src/app/api/health/route.ts`** - Health check API endpoint
7. **`CLOUD_RUN_DEPLOYMENT.md`** - Comprehensive frontend deployment guide
8. **`QUICKSTART_CLOUD_RUN.md`** - Quick 10-minute frontend deployment guide
9. **`README_DEPLOYMENT.md`** - Deployment overview and options

### Configuration Updates

- **`frontend/next.config.js`** - Updated with standalone output for production

## Quick Reference

### Backend Deployment

```bash
cd backend
export GOOGLE_CLOUD_PROJECT="your-project-id"
./deploy.sh
```

**Outputs**: Backend URL at `https://ai-agency-backend-xxxx.run.app`

### Frontend Deployment

```bash
cd frontend
export GOOGLE_CLOUD_PROJECT="your-project-id"
export BACKEND_URL="https://ai-agency-backend-xxxx.run.app"
export WS_URL="wss://ai-agency-backend-xxxx.run.app"
./deploy.sh
```

**Outputs**: Frontend URL at `https://ai-agency-frontend-xxxx.run.app`

## Architecture

### Backend (`backend/Dockerfile`)

```dockerfile
# Multi-stage build
FROM python:3.13-slim AS builder
  - Install uv package manager
  - Install dependencies

FROM python:3.13-slim AS runner
  - Copy application code
  - Run uvicorn server on port 8080
```

**Key Features**:
- Uses `uv` for fast dependency management
- Includes audio processing libraries (libsndfile)
- Health check endpoint
- Optimized for Cloud Run

### Frontend (`frontend/Dockerfile`)

```dockerfile
# Multi-stage build
FROM node:20-alpine AS deps
  - Install dependencies

FROM node:20-alpine AS builder
  - Build Next.js with standalone output

FROM node:20-alpine AS runner
  - Run optimized standalone server
  - Port 8080
```

**Key Features**:
- Standalone output (~200MB vs ~1GB)
- Build-time environment variables
- Health check endpoint
- Non-root user for security

## Environment Variables Reference

### Backend Required

| Variable | Set Via | Description |
|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Env Var | GCP Project ID |
| `GEMINI_API_KEY` | Secret Manager | Gemini API Key |
| `REDIS_HOST` | Env Var | Cloud Memorystore IP |
| `GCS_BUCKET_NAME` | Env Var | GCS bucket name |

### Frontend Required

| Variable | Set Via | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | Build Arg + Env Var | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | Build Arg + Env Var | WebSocket URL |

## Infrastructure Components

### Created by Deployment Scripts

1. **Cloud Run Services**
   - `ai-agency-backend` (us-central1)
   - `ai-agency-frontend` (us-central1)

2. **Container Images**
   - `gcr.io/{project}/ai-agency-backend:latest`
   - `gcr.io/{project}/ai-agency-frontend:latest`

### Manual Setup Required

1. **Cloud Memorystore (Redis)**
   - Instance: `ai-agency-redis`
   - Region: `us-central1`
   - Tier: Basic (dev) or Standard (prod)

2. **VPC Connector**
   - Name: `ai-agency-connector`
   - Region: `us-central1`
   - Range: `10.8.0.0/28`

3. **GCS Bucket**
   - Name: `ai-agency-assets-{project-id}`
   - Location: `us-central1`
   - Folders: `images/`, `videos/`, `audio/`

4. **Secrets**
   - `gemini-api-key` (Secret Manager)

## Deployment Workflow

### First-Time Setup

```bash
# 1. Set up infrastructure
gcloud services enable run.googleapis.com cloudbuild.googleapis.com redis.googleapis.com
gcloud redis instances create ai-agency-redis --size=1 --region=us-central1
gcloud compute networks vpc-access connectors create ai-agency-connector --region=us-central1 --network=default --range=10.8.0.0/28
gsutil mb gs://ai-agency-assets-$PROJECT_ID/
echo -n "api-key" | gcloud secrets create gemini-api-key --data-file=-

# 2. Deploy backend
cd backend
./deploy.sh

# 3. Deploy frontend
cd ../frontend
export BACKEND_URL=$(gcloud run services describe ai-agency-backend --region us-central1 --format 'value(status.url)')
export WS_URL=${BACKEND_URL/https/wss}
./deploy.sh

# 4. Update CORS (manual step)
# Edit backend/app/main.py and redeploy
```

### Subsequent Deployments

```bash
# Backend
cd backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/ai-agency-backend:latest
gcloud run deploy ai-agency-backend --image gcr.io/$PROJECT_ID/ai-agency-backend:latest --region us-central1

# Frontend
cd frontend
gcloud builds submit --config=cloudbuild.yaml
gcloud run deploy ai-agency-frontend --image gcr.io/$PROJECT_ID/ai-agency-frontend:latest --region us-central1
```

## CI/CD with Cloud Build

### Automated Deployments

The `cloudbuild.yaml` files enable automatic deployments:

1. **Push to main branch**
2. **Cloud Build trigger fires**
3. **Container built and pushed**
4. **Deployed to Cloud Run**

Set up triggers:

```bash
# Backend trigger
gcloud builds triggers create github \
    --repo-name=ai-agency \
    --branch-pattern="^main$" \
    --build-config=backend/cloudbuild.yaml

# Frontend trigger
gcloud builds triggers create github \
    --repo-name=ai-agency \
    --branch-pattern="^main$" \
    --build-config=frontend/cloudbuild.yaml
```

## Health Checks

### Backend

```bash
curl https://ai-agency-backend-xxxx.run.app/health
```

Response:
```json
{
  "status": "healthy",
  "redis": "connected",
  "environment": "production"
}
```

### Frontend

```bash
curl https://ai-agency-frontend-xxxx.run.app/api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-19T...",
  "environment": "production"
}
```

## Resource Limits

### Backend (Production)

- Memory: 2Gi
- CPU: 2
- Timeout: 300s (5 min)
- Max Instances: 10
- Min Instances: 0 (or 1 for production)

### Frontend (Production)

- Memory: 1Gi
- CPU: 1
- Timeout: 60s
- Max Instances: 10
- Min Instances: 0 (or 1 for production)

## Cost Optimization

### Development

- Min instances: 0 (scale to zero)
- Redis: Basic tier (1GB)
- VPC: Minimum instances

**Est. Cost**: ~$65-80/month

### Production

- Min instances: 1 (backend and frontend)
- Redis: Standard tier with HA
- VPC: Auto-scaling

**Est. Cost**: ~$305-390/month

## Documentation Hierarchy

```
DEPLOYMENT_GUIDE.md (Root)
  ├── Overview and quick start
  ├── Infrastructure setup
  └── Complete workflow

backend/
  ├── QUICKSTART_CLOUD_RUN.md (10-min guide)
  └── CLOUD_RUN_DEPLOYMENT.md (Detailed guide)

frontend/
  ├── QUICKSTART_CLOUD_RUN.md (10-min guide)
  ├── CLOUD_RUN_DEPLOYMENT.md (Detailed guide)
  └── README_DEPLOYMENT.md (Options overview)
```

## Getting Started

1. **Read**: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for overview
2. **Backend**: Follow [backend/QUICKSTART_CLOUD_RUN.md](./backend/QUICKSTART_CLOUD_RUN.md)
3. **Frontend**: Follow [frontend/QUICKSTART_CLOUD_RUN.md](./frontend/QUICKSTART_CLOUD_RUN.md)
4. **Advanced**: Refer to detailed guides for production setup

## Support

- **Backend Issues**: See [backend/CLOUD_RUN_DEPLOYMENT.md](./backend/CLOUD_RUN_DEPLOYMENT.md#troubleshooting)
- **Frontend Issues**: See [frontend/CLOUD_RUN_DEPLOYMENT.md](./frontend/CLOUD_RUN_DEPLOYMENT.md#troubleshooting)
- **General**: See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md#troubleshooting)

---

All files are ready for deployment. Start with the quickstart guides for fastest deployment.
