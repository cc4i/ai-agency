#!/bin/bash
# Deployment script for AI Agency Backend to Cloud Run

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
REGION="us-central1"
SERVICE_NAME="ai-agency-backend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Get configuration from environment or use defaults
REDIS_HOST="${REDIS_HOST:-10.125.0.3}"
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-ai-agency-demo}"
AGENT_ENGINE_ID="${AGENT_ENGINE_ID:-3117603647907692544}"
ENABLE_MEMORY_BANK="${ENABLE_MEMORY_BANK:-true}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
BACKEND_URL="${BACKEND_URL:-https://ai-agency-backend-xxxx.run.app}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment of AI Agency Backend to Cloud Run${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    exit 1
fi

# Display configuration
# Display configuration
echo -e "${YELLOW}Deployment Configuration:${NC}"
echo -e "  Project ID: ${PROJECT_ID}"
echo -e "  Region: ${REGION}"
echo -e "  GCS Bucket: ${GCS_BUCKET_NAME}"
echo -e "  Memory Bank: ${ENABLE_MEMORY_BANK}"
if [[ -n "${REDIS_HOST}" ]]; then
    echo -e "  Redis Host: ${REDIS_HOST}"
else
    echo -e "${RED}  Redis Host: NOT SET (will use localhost - likely to fail!)${NC}"
fi
if [[ -n "${GEMINI_API_KEY}" ]]; then
    echo -e "  Gemini API Key: ${GEMINI_API_KEY:0:20}... (set)"
else
    echo -e "${RED}  Gemini API Key: NOT SET (Agent initialization will fail!)${NC}"
fi
if [[ -n "${AGENT_ENGINE_ID}" && "${ENABLE_MEMORY_BANK}" == "true" ]]; then
    echo -e "  Agent Engine ID: ${AGENT_ENGINE_ID}"
fi
if [[ -n "${BACKEND_URL}" ]]; then
    echo -e "  Backend URL: ${BACKEND_URL}"
else
    echo -e "${RED}  Backend URL: NOT SET (will use localhost - likely to fail!)${NC}"
fi
echo ""
read -p "Proceed with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 1
fi

# Set the project
echo -e "${GREEN}Setting project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${GREEN}Enabling required APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    redis.googleapis.com

# Build the container
echo -e "${GREEN}Building container image...${NC}"
gcloud builds submit --tag ${IMAGE_NAME}:latest

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"

# Build environment variables string
ENV_VARS="ENVIRONMENT=production"
ENV_VARS="${ENV_VARS},LOG_LEVEL=INFO"
ENV_VARS="${ENV_VARS},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
ENV_VARS="${ENV_VARS},GOOGLE_CLOUD_LOCATION=${REGION}"
ENV_VARS="${ENV_VARS},REDIS_HOST=${REDIS_HOST}"
ENV_VARS="${ENV_VARS},GCS_BUCKET_NAME=${GCS_BUCKET_NAME}"
ENV_VARS="${ENV_VARS},ENABLE_MEMORY_BANK=${ENABLE_MEMORY_BANK}"

# Add GEMINI_API_KEY if set
if [[ -n "${GEMINI_API_KEY}" ]]; then
    ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi

# Add Memory Bank Agent Engine ID if enabled
if [[ -n "${AGENT_ENGINE_ID}" ]]; then
    ENV_VARS="${ENV_VARS},AGENT_ENGINE_ID=${AGENT_ENGINE_ID}"
fi

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 16Gi \
    --cpu 4 \
    --timeout 3600s \
    --max-instances 10 \
    --min-instances 1 \
    --port 8080 \
    --set-env-vars "${ENV_VARS}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}Service URL: ${SERVICE_URL}${NC}"
echo ""
if [[ -z "${GEMINI_API_KEY}" ]]; then
    echo -e "${RED}⚠️  WARNING: GEMINI_API_KEY not set!${NC}"
    echo "The backend needs GEMINI_API_KEY to initialize the AI agent."
    echo ""
    echo "Quick fix - set as environment variable:"
    echo "  gcloud run services update ${SERVICE_NAME} \\"
    echo "    --region ${REGION} \\"
    echo "    --set-env-vars 'GEMINI_API_KEY=your-api-key'"
    echo ""
    echo "Or use Secret Manager (more secure for production):"
    echo "  echo -n 'your-api-key' | gcloud secrets create gemini-api-key --data-file=-"
    echo "  gcloud run services update ${SERVICE_NAME} \\"
    echo "    --region ${REGION} \\"
    echo "    --set-secrets 'GEMINI_API_KEY=gemini-api-key:latest'"
    echo ""
fi
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the health endpoint: ${SERVICE_URL}/health"
echo "2. Test WebSocket connection from frontend"
echo "3. Update frontend CORS if needed"
