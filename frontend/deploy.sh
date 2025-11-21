#!/bin/bash
# Deployment script for AI Agency Frontend to Cloud Run

set -e

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-your-project-id}"
REGION="us-central1"
SERVICE_NAME="ai-agency-frontend"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Backend URL - set via environment variables or defaults
BACKEND_URL="${BACKEND_URL:-https://ai-agency-backend-xxxx.run.app}"
WS_URL="${WS_URL:-wss://ai-agency-backend-xxxx.run.app}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment of AI Agency Frontend to Cloud Run${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    exit 1
fi

# Confirm project ID
echo -e "${YELLOW}Project ID: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}Backend URL: ${BACKEND_URL}${NC}"
echo -e "${YELLOW}WebSocket URL: ${WS_URL}${NC}"
read -p "Is this configuration correct? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Deployment cancelled${NC}"
    echo -e "${YELLOW}To set backend URL, run:${NC}"
    echo -e "  export BACKEND_URL=https://your-backend-url.run.app"
    echo -e "  export WS_URL=wss://your-backend-url.run.app"
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
    containerregistry.googleapis.com

# Build the container with build args
echo -e "${GREEN}Building container image...${NC}"

# Check if Docker is installed for local build
if command -v docker &> /dev/null; then
    echo -e "${YELLOW}Using Docker to build locally...${NC}"

    # Configure Docker authentication for GCR
    gcloud auth configure-docker --quiet

    # Build with Docker (supports --build-arg)
    docker build \
        --build-arg NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL} \
        --build-arg NEXT_PUBLIC_WS_URL=${WS_URL} \
        -t ${IMAGE_NAME}:latest \
        .

    # Push to Container Registry
    echo -e "${GREEN}Pushing image to Container Registry...${NC}"
    docker push ${IMAGE_NAME}:latest
else
    # Fallback: Use Cloud Build with temporary cloudbuild.yaml
    echo -e "${YELLOW}Docker not found. Using Cloud Build with temporary config...${NC}"

    # Create temporary cloudbuild.yaml
    cat > /tmp/cloudbuild-deploy.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - '${IMAGE_NAME}:latest'
      - '--build-arg'
      - 'NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL}'
      - '--build-arg'
      - 'NEXT_PUBLIC_WS_URL=${WS_URL}'
      - '.'

images:
  - '${IMAGE_NAME}:latest'
EOF

    # Build using temporary cloudbuild.yaml
    gcloud builds submit --config=/tmp/cloudbuild-deploy.yaml

    # Clean up
    rm /tmp/cloudbuild-deploy.yaml
fi

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 60s \
    --max-instances 10 \
    --min-instances 0 \
    --port 8080 \
    --set-env-vars "NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL}" \
    --set-env-vars "NEXT_PUBLIC_WS_URL=${WS_URL}" \
    --set-env-vars "BACKEND_URL=${BACKEND_URL}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}Frontend URL: ${SERVICE_URL}${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Visit ${SERVICE_URL} to test the application"
echo "2. Update CORS settings in backend to allow ${SERVICE_URL}"
echo "3. Configure custom domain (optional)"
