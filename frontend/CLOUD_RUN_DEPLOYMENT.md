# Cloud Run Deployment Guide - Frontend

Complete guide to deploy the AI Agency Frontend (Next.js 14) to Google Cloud Run.

## Prerequisites

1. **Backend Deployed**: Deploy the backend first and note the URL
2. **Google Cloud Project**: Active GCP project with billing enabled
3. **gcloud CLI**: Installed and authenticated ([Install Guide](https://cloud.google.com/sdk/docs/install))
4. **Node.js 20+**: For local testing (optional)

## Architecture Overview

```
┌─────────────────────┐
│   Cloud Run         │
│  (Next.js Frontend) │
│   Port: 8080        │
└──────────┬──────────┘
           │
           ├─────► Backend API (Cloud Run)
           │       - REST endpoints
           │       - WebSocket (Gemini Live)
           │
           └─────► GCS (Images via backend proxy)
```

## Quick Deployment

### Option 1: Using the Deployment Script

```bash
cd frontend

# Set environment variables
export GOOGLE_CLOUD_PROJECT="your-project-id"
export BACKEND_URL="https://ai-agency-backend-xxxx.run.app"
export WS_URL="wss://ai-agency-backend-xxxx.run.app"

# Run deployment
./deploy.sh
```

### Option 2: Manual Deployment Steps

Follow the detailed steps below for more control.

---

## Detailed Deployment Steps

### Step 1: Prerequisites Check

Ensure backend is deployed and running:

```bash
# Get backend URL from previous deployment
BACKEND_URL=$(gcloud run services describe ai-agency-backend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Backend URL: $BACKEND_URL"

# Test backend health
curl $BACKEND_URL/health
```

### Step 2: Update Next.js Configuration

The project includes a production-ready `next.config.production.js`. You need to enable it:

```bash
cd frontend

# Option A: Rename for permanent use
mv next.config.js next.config.dev.js
mv next.config.production.js next.config.js

# Option B: Use as override during build (handled by Dockerfile)
# No action needed - Dockerfile uses production config
```

### Step 3: Set Environment Variables

Create a `.env.production` file (used for local testing):

```bash
cat > .env.production << EOF
NEXT_PUBLIC_BACKEND_URL=$BACKEND_URL
NEXT_PUBLIC_WS_URL=${BACKEND_URL/https/wss}
NODE_ENV=production
EOF
```

**Note**: These will be passed as build args during Docker build.

### Step 4: Test Build Locally (Optional)

```bash
# Build Docker image locally
docker build \
    --build-arg NEXT_PUBLIC_BACKEND_URL=$BACKEND_URL \
    --build-arg NEXT_PUBLIC_WS_URL=${BACKEND_URL/https/wss} \
    -t ai-agency-frontend:local \
    .

# Run locally to test
docker run -p 8080:8080 \
    -e NEXT_PUBLIC_BACKEND_URL=$BACKEND_URL \
    -e NEXT_PUBLIC_WS_URL=${BACKEND_URL/https/wss} \
    ai-agency-frontend:local

# Visit http://localhost:8080
```

### Step 5: Build and Push to Container Registry

```bash
# Set project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com

# Build using Cloud Build (recommended - faster)
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/ai-agency-frontend:latest \
    --build-arg NEXT_PUBLIC_BACKEND_URL=$BACKEND_URL \
    --build-arg NEXT_PUBLIC_WS_URL=${BACKEND_URL/https/wss}
```

**Note**: Cloud Build doesn't directly support `--build-arg`. You'll need to update the Dockerfile or use substitutions. See the workaround below.

#### Workaround for Build Args in Cloud Build

Create a temporary `cloudbuild-manual.yaml`:

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/ai-agency-frontend:latest'
      - '--build-arg'
      - 'NEXT_PUBLIC_BACKEND_URL=${_BACKEND_URL}'
      - '--build-arg'
      - 'NEXT_PUBLIC_WS_URL=${_WS_URL}'
      - '.'

substitutions:
  _BACKEND_URL: 'YOUR_BACKEND_URL_HERE'
  _WS_URL: 'YOUR_WS_URL_HERE'

images:
  - 'gcr.io/$PROJECT_ID/ai-agency-frontend:latest'
```

Then build:

```bash
gcloud builds submit --config=cloudbuild-manual.yaml
```

### Step 6: Deploy to Cloud Run

```bash
gcloud run deploy ai-agency-frontend \
    --image gcr.io/$PROJECT_ID/ai-agency-frontend:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 60s \
    --max-instances 10 \
    --min-instances 0 \
    --port 8080 \
    --set-env-vars "NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL}" \
    --set-env-vars "NEXT_PUBLIC_WS_URL=${BACKEND_URL/https/wss}"
```

### Step 7: Update Backend CORS Configuration

Your frontend URL needs to be allowed in backend CORS:

```bash
# Get frontend URL
FRONTEND_URL=$(gcloud run services describe ai-agency-frontend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Frontend URL: $FRONTEND_URL"
```

Update `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "YOUR_FRONTEND_URL_HERE",  # Add your Cloud Run frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Redeploy backend:

```bash
cd ../backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/ai-agency-backend:latest
gcloud run deploy ai-agency-backend \
    --image gcr.io/$PROJECT_ID/ai-agency-backend:latest \
    --region us-central1
```

### Step 8: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe ai-agency-frontend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Frontend URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/api/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-11-19T...",
#   "environment": "production"
# }
```

---

## Environment Variables Reference

### Build-time Variables (Build Args)

These must be set during `docker build`:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | Backend API URL | `https://ai-agency-backend-xxx.run.app` |
| `NEXT_PUBLIC_WS_URL` | Yes | WebSocket URL | `wss://ai-agency-backend-xxx.run.app` |

### Runtime Variables

These can be updated without rebuilding:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `NODE_ENV` | No | Environment | `production` |
| `PORT` | No | Server port | `8080` |

**Important**: Next.js environment variables starting with `NEXT_PUBLIC_` are embedded at build time and cannot be changed at runtime.

---

## Updating the Deployment

### Update Code Only (No Env Changes)

```bash
cd frontend

# Rebuild with same environment variables
gcloud builds submit \
    --config=cloudbuild.yaml

# Redeploy
gcloud run deploy ai-agency-frontend \
    --image gcr.io/$PROJECT_ID/ai-agency-frontend:latest \
    --region us-central1
```

### Update Environment Variables

Since `NEXT_PUBLIC_*` variables are build-time, you must rebuild:

```bash
# Set new backend URL
export NEW_BACKEND_URL="https://new-backend-url.run.app"

# Rebuild with new environment
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/ai-agency-frontend:latest \
    --build-arg NEXT_PUBLIC_BACKEND_URL=$NEW_BACKEND_URL \
    --build-arg NEXT_PUBLIC_WS_URL=${NEW_BACKEND_URL/https/wss}

# Deploy new image
gcloud run deploy ai-agency-frontend \
    --image gcr.io/$PROJECT_ID/ai-agency-frontend:latest \
    --region us-central1 \
    --set-env-vars "NEXT_PUBLIC_BACKEND_URL=${NEW_BACKEND_URL}" \
    --set-env-vars "NEXT_PUBLIC_WS_URL=${NEW_BACKEND_URL/https/wss}"
```

---

## Monitoring and Logging

### View Logs

```bash
# Stream logs
gcloud run services logs tail ai-agency-frontend --region us-central1

# Follow logs in real-time
gcloud run services logs tail ai-agency-frontend --region us-central1 --follow
```

### View Metrics

```bash
# Open Cloud Console monitoring
gcloud run services describe ai-agency-frontend \
    --region us-central1 \
    --format='value(metadata.selfLink)' | \
    xargs -I {} echo "Metrics: https://console.cloud.google.com/run/detail/us-central1/ai-agency-frontend/metrics"
```

---

## Troubleshooting

### Build Fails: "Module not found"

**Symptom**: Build fails during `npm ci` or `npm run build`

**Solution**:
1. Ensure `package-lock.json` is committed
2. Update dependencies:
   ```bash
   npm install
   npm audit fix
   git add package.json package-lock.json
   git commit -m "Update dependencies"
   ```

### Frontend Can't Connect to Backend

**Symptom**: Network errors or CORS errors in browser console

**Solution**:
1. Verify backend URL is correct:
   ```bash
   echo $BACKEND_URL
   curl $BACKEND_URL/health
   ```
2. Check CORS configuration in `backend/app/main.py`
3. Verify environment variables:
   ```bash
   gcloud run services describe ai-agency-frontend \
       --region us-central1 \
       --format yaml | grep -A 5 "env:"
   ```

### WebSocket Connection Fails

**Symptom**: WebSocket errors in browser console

**Solution**:
1. Verify WS URL uses `wss://` not `https://`
2. Check backend WebSocket endpoint is accessible:
   ```bash
   # Use websocat or similar tool
   websocat $WS_URL/ws/test
   ```
3. Cloud Run supports WebSocket but has a 60-minute connection limit

### Page Loads Slowly

**Symptom**: Slow initial page load

**Solution**:
1. Increase min instances to reduce cold starts:
   ```bash
   gcloud run services update ai-agency-frontend \
       --region us-central1 \
       --min-instances 1
   ```
2. Enable CDN (requires custom domain):
   - Set up Cloud CDN with Cloud Load Balancer

### Static Assets Not Loading

**Symptom**: Images or CSS not loading

**Solution**:
1. Verify standalone build includes assets:
   ```bash
   # Check .next/standalone structure
   docker run --entrypoint ls \
       gcr.io/$PROJECT_ID/ai-agency-frontend:latest \
       -la .next/static
   ```
2. Ensure public folder is copied correctly in Dockerfile

---

## Production Best Practices

### 1. Enable Standalone Output

Already configured in `next.config.production.js`:

```javascript
{
  output: 'standalone',
}
```

This reduces Docker image size from ~1GB to ~200MB.

### 2. Use Custom Domain

```bash
# Map custom domain
gcloud run domain-mappings create \
    --service ai-agency-frontend \
    --domain app.yourdomain.com \
    --region us-central1
```

### 3. Enable Cloud CDN

Requires Load Balancer setup:
- Follow [Cloud Run with CDN guide](https://cloud.google.com/run/docs/configuring/cdn)
- Significantly improves static asset performance

### 4. Set Up Cloud Build Triggers

Automate deployments on git push:

```bash
gcloud builds triggers create github \
    --repo-name=ai-agency \
    --repo-owner=your-github-username \
    --branch-pattern="^main$" \
    --build-config=frontend/cloudbuild.yaml \
    --substitutions="_BACKEND_URL=https://your-backend.run.app,_WS_URL=wss://your-backend.run.app"
```

### 5. Configure Cache Headers

In `next.config.js`, add:

```javascript
{
  async headers() {
    return [
      {
        source: '/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
}
```

### 6. Enable Error Reporting

Add Sentry or Cloud Error Reporting:

```bash
npm install @sentry/nextjs

# Initialize Sentry
npx @sentry/wizard -i nextjs
```

### 7. Set Min Instances for Production

Reduce cold start latency:

```bash
gcloud run services update ai-agency-frontend \
    --region us-central1 \
    --min-instances 1
```

**Cost**: ~$15/month for 1 always-on instance

---

## Cost Optimization

### Development

- **Min Instances**: 0 (scale to zero when not in use)
- **Memory**: 512Mi (reduce from 1Gi if possible)
- **Max Instances**: 5

```bash
gcloud run services update ai-agency-frontend \
    --region us-central1 \
    --min-instances 0 \
    --memory 512Mi \
    --max-instances 5
```

### Production

- **Min Instances**: 1-2 (for fast response times)
- **Memory**: 1Gi (for optimal performance)
- **Max Instances**: 10-20 (based on traffic)

### Estimated Monthly Costs

**Low Traffic** (< 10k requests/month):
- Cloud Run: ~$5-10/month
- Cloud Build: ~$5/month (50 builds)
- **Total**: ~$10-15/month

**Medium Traffic** (100k requests/month, 1 min instance):
- Cloud Run: ~$30-50/month
- Cloud Build: ~$10/month
- **Total**: ~$40-60/month

---

## Cleanup

To delete frontend deployment:

```bash
# Delete Cloud Run service
gcloud run services delete ai-agency-frontend --region us-central1 --quiet

# Delete container images
gcloud container images delete gcr.io/$PROJECT_ID/ai-agency-frontend --quiet
```

---

## Next Steps After Deployment

1. **Test the Application**: Visit your frontend URL and test all features
2. **Set Up Monitoring**: Configure uptime checks and alerts
3. **Configure Custom Domain**: Map a friendly domain name
4. **Enable HTTPS**: Automatic with Cloud Run, verify certificate
5. **Set Up CI/CD**: Automate deployments with Cloud Build triggers
6. **Performance Testing**: Use Lighthouse to optimize performance
7. **Security Audit**: Review Content Security Policy and CORS settings

---

## Additional Resources

- [Next.js Deployment Docs](https://nextjs.org/docs/deployment)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Next.js Standalone Output](https://nextjs.org/docs/advanced-features/output-file-tracing)
- [Cloud Run with Next.js](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-nodejs-service)
- [Cloud CDN Setup](https://cloud.google.com/run/docs/configuring/cdn)

---

## Support

For deployment issues:
1. Check logs: `gcloud run services logs tail ai-agency-frontend --region us-central1`
2. Verify configuration: `gcloud run services describe ai-agency-frontend --region us-central1`
3. Test locally with Docker before deploying
4. Review Cloud Console monitoring dashboards
