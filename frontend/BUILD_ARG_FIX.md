# Build Arg Fix for Cloud Run Deployment

## Problem

The original `deploy.sh` script failed with this error:

```bash
ERROR: (gcloud.builds.submit) unrecognized arguments:
  --build-arg
  NEXT_PUBLIC_BACKEND_URL=...
  NEXT_PUBLIC_WS_URL=...
```

**Root Cause**: `gcloud builds submit` does NOT support the `--build-arg` flag that Docker supports.

## Solution

The updated `deploy.sh` script now uses a **two-strategy approach**:

### Strategy 1: Local Docker Build (Preferred)

If Docker is installed locally, the script:

1. **Configures Docker authentication** for Google Container Registry
2. **Builds locally with Docker** (which supports `--build-arg`)
3. **Pushes to GCR** for Cloud Run deployment

```bash
# Configure Docker authentication
gcloud auth configure-docker --quiet

# Build with build args (Docker supports this)
docker build \
    --build-arg NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL} \
    --build-arg NEXT_PUBLIC_WS_URL=${WS_URL} \
    -t gcr.io/${PROJECT_ID}/ai-agency-frontend:latest \
    .

# Push to Container Registry
docker push gcr.io/${PROJECT_ID}/ai-agency-frontend:latest
```

**Advantages**:
- Faster builds (uses local Docker cache)
- More control over build process
- Immediate feedback on build errors

### Strategy 2: Cloud Build with Temporary Config (Fallback)

If Docker is NOT installed, the script:

1. **Creates a temporary `cloudbuild.yaml`** with the environment variables
2. **Runs Cloud Build** using this temporary config
3. **Cleans up** the temporary file

```bash
# Create temporary cloudbuild.yaml
cat > /tmp/cloudbuild-deploy.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/${PROJECT_ID}/ai-agency-frontend:latest'
      - '--build-arg'
      - 'NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL}'
      - '--build-arg'
      - 'NEXT_PUBLIC_WS_URL=${WS_URL}'
      - '.'

images:
  - 'gcr.io/${PROJECT_ID}/ai-agency-frontend:latest'
EOF

# Build using temporary config
gcloud builds submit --config=/tmp/cloudbuild-deploy.yaml

# Clean up
rm /tmp/cloudbuild-deploy.yaml
```

**Advantages**:
- Works without Docker installed
- Uses Cloud Build's infrastructure
- No local resource usage

## Updated Deployment Workflow

### Before (Broken)

```bash
cd frontend
./deploy.sh
# ❌ ERROR: --build-arg not supported
```

### After (Fixed)

```bash
cd frontend

# Set environment variables
export GOOGLE_CLOUD_PROJECT="your-project-id"
export BACKEND_URL="https://ai-agency-backend-xxx.run.app"
export WS_URL="wss://ai-agency-backend-xxx.run.app"

# Run deployment
./deploy.sh

# ✅ Script automatically:
#    1. Detects if Docker is available
#    2. Uses appropriate build method
#    3. Pushes to GCR
#    4. Deploys to Cloud Run
```

## How the Script Decides

```bash
if command -v docker &> /dev/null; then
    # Docker is installed → Use local build
    echo "Using Docker to build locally..."
    docker build --build-arg ... -t ... .
    docker push ...
else
    # Docker not installed → Use Cloud Build
    echo "Docker not found. Using Cloud Build..."
    # Create temp cloudbuild.yaml
    gcloud builds submit --config=/tmp/cloudbuild-deploy.yaml
fi
```

## Why This Fix Works

### Problem with `gcloud builds submit --build-arg`

The `gcloud builds submit` command is a **simplified wrapper** around Cloud Build that:
- Automatically creates a basic build configuration
- Only supports a limited set of flags
- Does NOT support passing build arguments

### Solution Approaches Compared

| Approach | Docker Required? | Speed | Caching | Complexity |
|----------|------------------|-------|---------|------------|
| **Local Docker Build** | Yes | Fast | Local cache | Low |
| **Cloud Build YAML** | No | Slower | Remote cache | Medium |
| **Modified Dockerfile** | No | Medium | Remote cache | High (not maintainable) |

We chose the **hybrid approach** to support both scenarios.

## Testing the Fix

### Test with Docker Installed

```bash
cd frontend
export BACKEND_URL="https://your-backend.run.app"
export WS_URL="wss://your-backend.run.app"
./deploy.sh

# Expected output:
# ✓ Using Docker to build locally...
# ✓ Building container image...
# ✓ Pushing image to Container Registry...
# ✓ Deploying to Cloud Run...
```

### Test without Docker

```bash
# Temporarily disable Docker (for testing)
alias docker='echo "Docker not found" && false'

cd frontend
./deploy.sh

# Expected output:
# ✓ Docker not found. Using Cloud Build with temporary config...
# ✓ Building container image...
# ✓ Deploying to Cloud Run...

# Restore Docker
unalias docker
```

## Alternative Solutions (Not Chosen)

### Alternative 1: Hardcode Values in Dockerfile

**Rejected**: Not maintainable, requires editing Dockerfile for each deployment

```dockerfile
# Bad: Hardcoded values
ENV NEXT_PUBLIC_BACKEND_URL=https://specific-backend.run.app
```

### Alternative 2: Only Use Cloud Build YAML

**Rejected**: Requires Docker to be absent or forces all users to use Cloud Build even if they have Docker

```bash
# Bad: Always uses Cloud Build (slower)
gcloud builds submit --config=cloudbuild.yaml
```

### Alternative 3: Runtime Environment Variables

**Rejected**: Next.js `NEXT_PUBLIC_*` variables are **build-time only** and cannot be changed at runtime

```bash
# Bad: Won't work for Next.js
gcloud run deploy ... --set-env-vars "NEXT_PUBLIC_BACKEND_URL=..."
```

## Files Changed

1. **`frontend/deploy.sh`**
   - Added Docker detection
   - Added local build path
   - Added Cloud Build fallback
   - Removed duplicate BACKEND_URL definitions

2. **`frontend/QUICKSTART_CLOUD_RUN.md`**
   - Updated deployment instructions
   - Removed manual build steps
   - Clarified script behavior

## Additional Improvements

While fixing the build arg issue, we also:

1. **Removed duplicate BACKEND_URL definitions** (lines 11-12 were redundant)
2. **Added Docker authentication** (`gcloud auth configure-docker`)
3. **Improved error messages** with color-coded output
4. **Added cleanup** for temporary files

## Summary

The fix ensures deployment works in all scenarios:

✅ **With Docker**: Fast local builds with full Docker features
✅ **Without Docker**: Automatic fallback to Cloud Build
✅ **Consistent results**: Same final image regardless of build method
✅ **User-friendly**: Automatic detection, no manual configuration

Simply run `./deploy.sh` and the script handles everything!
