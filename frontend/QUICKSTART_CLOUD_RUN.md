# Quick Start: Deploy Frontend to Cloud Run

Get your AI Agency frontend running on Cloud Run in 10 minutes.

## Prerequisites

- Backend already deployed to Cloud Run
- Google Cloud Project with billing enabled
- gcloud CLI installed and authenticated

## Deployment Steps

### 1. Get Backend URL

```bash
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Get backend URL from previous deployment
BACKEND_URL=$(gcloud run services describe ai-agency-backend \
    --region us-central1 \
    --format 'value(status.url)')

echo "Backend URL: $BACKEND_URL"

# Derive WebSocket URL
WS_URL=${BACKEND_URL/https/wss}
echo "WebSocket URL: $WS_URL"
```

### 2. Enable APIs

```bash
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com
```

### 3. Deploy Using Script (Recommended)

The deployment script automatically handles the build process:

```bash
cd frontend

# Set environment variables
export BACKEND_URL=$BACKEND_URL
export WS_URL=$WS_URL

# Run deployment script
./deploy.sh
```

The script will:
- Build with Docker locally (if available) or use Cloud Build
- Push to Container Registry
- Deploy to Cloud Run

**Note**: The script automatically handles the `--build-arg` issue by:
1. Using Docker locally if available (supports `--build-arg`)
2. Falling back to Cloud Build with temporary config if Docker not installed

The script will output the frontend URL when complete.

### 4. Update Backend CORS

Edit `backend/app/main.py` to add your frontend URL:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "YOUR_FRONTEND_URL_HERE",  # Add this
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

### 5. Test Deployment

The deploy script will output the frontend URL. Test it:

```bash
# Get the URL (if needed)
FRONTEND_URL=$(gcloud run services describe ai-agency-frontend \
    --region us-central1 \
    --format 'value(status.url)')

# Test health endpoint
curl $FRONTEND_URL/api/health

# Open in browser
echo "Visit: $FRONTEND_URL"
```

## Done!

Your frontend is now live! Visit the URL to test the application.

## Troubleshooting

### Build Fails

Check `package.json` and `package-lock.json` are committed:

```bash
git add package.json package-lock.json
git commit -m "Update dependencies"
```

### Can't Connect to Backend

1. Verify backend is running:
   ```bash
   curl $BACKEND_URL/health
   ```

2. Check CORS settings in backend

3. Verify environment variables:
   ```bash
   gcloud run services describe ai-agency-frontend \
       --region us-central1 \
       --format yaml | grep -A 5 "env:"
   ```

### WebSocket Errors

Ensure `NEXT_PUBLIC_WS_URL` uses `wss://` (not `https://`):

```bash
echo $WS_URL  # Should start with wss://
```

## Next Steps

- Review [CLOUD_RUN_DEPLOYMENT.md](./CLOUD_RUN_DEPLOYMENT.md) for production setup
- Set up custom domain
- Enable Cloud CDN for better performance
- Configure CI/CD with Cloud Build triggers
- Set up monitoring and alerts

## Cleanup

```bash
gcloud run services delete ai-agency-frontend --region us-central1 --quiet
gcloud container images delete gcr.io/$PROJECT_ID/ai-agency-frontend --quiet
```

## Using the Deploy Script

For even faster deployment, use the automated script:

```bash
cd frontend

export GOOGLE_CLOUD_PROJECT="your-project-id"
export BACKEND_URL="https://ai-agency-backend-xxxx.run.app"
export WS_URL="wss://ai-agency-backend-xxxx.run.app"

./deploy.sh
```

The script handles everything automatically!
