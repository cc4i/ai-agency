# AI Agency Frontend - Deployment Guide

This directory contains the Next.js 14 frontend application for AI Agency.

## Deployment Options

### 1. Cloud Run (Recommended)

Deploy to Google Cloud Run for serverless, auto-scaling hosting:

- **Quick Start**: [QUICKSTART_CLOUD_RUN.md](./QUICKSTART_CLOUD_RUN.md)
- **Detailed Guide**: [CLOUD_RUN_DEPLOYMENT.md](./CLOUD_RUN_DEPLOYMENT.md)

**Quick Deploy**:
```bash
cd frontend
export GOOGLE_CLOUD_PROJECT="your-project-id"
export BACKEND_URL="https://your-backend.run.app"
export WS_URL="wss://your-backend.run.app"
./deploy.sh
```

### 2. Local Development

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000

### 3. Production Build (Local)

```bash
npm run build
npm start
```

### 4. Docker (Local Testing)

```bash
# Build
docker build \
    --build-arg NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 \
    --build-arg NEXT_PUBLIC_WS_URL=ws://localhost:8000 \
    -t ai-agency-frontend \
    .

# Run
docker run -p 8080:8080 ai-agency-frontend
```

Visit http://localhost:8080

## Environment Variables

### Required for Deployment

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_BACKEND_URL` | Backend API URL | `https://backend.run.app` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL | `wss://backend.run.app` |

**Important**: These are build-time variables and are embedded in the bundle. Changing them requires a rebuild.

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `NODE_ENV` | Environment | `production` |
| `PORT` | Server port | `8080` |

## Files Created for Deployment

- `Dockerfile` - Multi-stage Docker build optimized for Next.js
- `.dockerignore` - Exclude unnecessary files from container
- `deploy.sh` - Automated deployment script
- `cloudbuild.yaml` - Cloud Build configuration for CI/CD
- `next.config.production.js` - Production-specific Next.js config
- `src/app/api/health/route.ts` - Health check endpoint

## Architecture

```
Frontend (Next.js 14)
├── Server-side rendering (SSR)
├── Static optimization
├── WebSocket support for Gemini Live
└── API routes for health checks

Production Build Features:
├── Standalone output (~200MB vs ~1GB)
├── Optimized static assets
├── Code splitting
└── Minification & compression
```

## Deployment Workflow

1. **Deploy Backend First**: Ensure backend is running
2. **Get Backend URL**: Note the Cloud Run URL
3. **Build Frontend**: Pass backend URL as build arg
4. **Deploy Frontend**: Deploy to Cloud Run
5. **Update CORS**: Add frontend URL to backend CORS config
6. **Test**: Verify end-to-end functionality

## Production Checklist

- [ ] Backend deployed and healthy
- [ ] Backend URL configured in build
- [ ] Frontend deployed successfully
- [ ] CORS configured in backend
- [ ] Health endpoint responding
- [ ] WebSocket connections working
- [ ] Custom domain configured (optional)
- [ ] CDN enabled (optional)
- [ ] Monitoring set up
- [ ] Error tracking configured

## Troubleshooting

### Build Fails

```bash
# Update dependencies
npm install
npm audit fix

# Clear cache
rm -rf node_modules .next
npm install
```

### Can't Connect to Backend

Check environment variables:
```bash
gcloud run services describe ai-agency-frontend \
    --region us-central1 \
    --format yaml | grep -A 5 "env:"
```

Verify backend is accessible:
```bash
curl $BACKEND_URL/health
```

### WebSocket Errors

Ensure WS URL uses `wss://` protocol:
```bash
echo $NEXT_PUBLIC_WS_URL  # Should be wss://...
```

## Performance Optimization

### Reduce Cold Starts

Set minimum instances:
```bash
gcloud run services update ai-agency-frontend \
    --region us-central1 \
    --min-instances 1
```

### Enable CDN

For static assets:
- Set up Cloud Load Balancer
- Enable Cloud CDN
- Configure cache headers

### Monitor Performance

```bash
# View logs
gcloud run services logs tail ai-agency-frontend --region us-central1

# View metrics in Cloud Console
```

## Cost Estimation

**Development** (scale to zero):
- ~$5-10/month for low traffic

**Production** (1 min instance):
- ~$30-50/month for medium traffic
- Includes always-on instance for fast response

## Support

For deployment issues:
- Check [CLOUD_RUN_DEPLOYMENT.md](./CLOUD_RUN_DEPLOYMENT.md) troubleshooting section
- Review Cloud Run logs
- Test locally with Docker first
- Verify backend connectivity

## Next Steps

1. Deploy backend (see `../backend/CLOUD_RUN_DEPLOYMENT.md`)
2. Deploy frontend using quick start guide
3. Configure custom domain
4. Set up monitoring and alerts
5. Enable CI/CD with Cloud Build triggers
6. Configure CDN for better performance
