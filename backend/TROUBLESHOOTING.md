# Troubleshooting Guide

## 403 Forbidden Error When Starting Backend

If you're getting "403 Forbidden" errors when starting the backend or making API calls, this typically indicates authentication or authorization issues with Google Cloud APIs.

### Common Causes and Solutions

#### 1. **Missing or Invalid API Key**

**Symptom**: `403 Forbidden` when calling Gemini API

**Solution**:
```bash
# Check if GEMINI_API_KEY is set
echo $GEMINI_API_KEY

# Get your API key from Google AI Studio
# Visit: https://aistudio.google.com/apikey

# Add to .env file
GEMINI_API_KEY=your-actual-api-key-here
```

#### 2. **Google Cloud Credentials Not Set**

**Symptom**: `403 Forbidden` when using Vertex AI (Imagen, Veo, etc.)

**Solution**:
```bash
# 1. Create a service account in Google Cloud Console
# 2. Download the JSON key file
# 3. Set the environment variable

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"

# Or add to .env file
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

#### 3. **APIs Not Enabled**

**Symptom**: `403 Forbidden` or "API not enabled"

**Solution**: Enable the required APIs in Google Cloud Console:
```
1. Go to: https://console.cloud.google.com/apis/library
2. Enable the following APIs:
   - Generative Language API (for Gemini)
   - Vertex AI API (for Imagen, Veo)
   - Cloud Text-to-Speech API
   - Cloud Speech-to-Text API
   - Cloud Storage API
```

#### 4. **Billing Not Enabled**

**Symptom**: `403 Forbidden` with "billing not enabled" message

**Solution**:
```
1. Go to: https://console.cloud.google.com/billing
2. Link a billing account to your project
3. Ensure billing is enabled
```

#### 5. **Incorrect Project ID**

**Symptom**: `403 Forbidden` or "Project not found"

**Solution**:
```bash
# Check your project ID
gcloud projects list

# Update .env file with correct project ID
GOOGLE_CLOUD_PROJECT=your-actual-project-id
```

#### 6. **Service Account Permissions**

**Symptom**: `403 Forbidden` even with credentials set

**Solution**:
```
1. Go to IAM & Admin in Google Cloud Console
2. Find your service account
3. Add the following roles:
   - Vertex AI User
   - Cloud Storage Admin (if using GCS)
   - Service Usage Consumer
```

### Testing Your Setup

Run this test script to verify your credentials:

```bash
cd backend

# Test Gemini API Key
uv run python << EOF
import google.generativeai as genai
import os

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')
response = model.generate_content("Say hello!")
print("✓ Gemini API works!")
print(response.text)
EOF

# Test Google Cloud credentials
uv run python << EOF
from google.cloud import aiplatform
import os

project = os.getenv('GOOGLE_CLOUD_PROJECT')
location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')

print(f"Project: {project}")
print(f"Location: {location}")

import vertexai
vertexai.init(project=project, location=location)
print("✓ Vertex AI credentials work!")
EOF
```

### Checking Logs

When starting the backend, check the logs for specific error messages:

```bash
uv run uvicorn app.main:app --reload --log-level debug
```

Look for:
- `Vertex AI initialized` - Good!
- `Vertex AI initialization failed` - Check credentials
- `403 Forbidden` - Check API keys and permissions
- `Invalid API key` - Check GEMINI_API_KEY
- `Project not found` - Check GOOGLE_CLOUD_PROJECT

### Environment Variables Checklist

Make sure your `.env` file has all of these:

```bash
# Required for Gemini
GEMINI_API_KEY=AIza...your-key...

# Required for Vertex AI (Imagen, Veo, etc.)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Optional
GCS_BUCKET_NAME=your-bucket-name
```

### Still Having Issues?

1. **Check API quotas**: Some APIs have free tier limits
2. **Verify region**: Some models only work in certain regions (use `us-central1`)
3. **Test with gcloud CLI**: Run `gcloud auth application-default login`
4. **Check firewall**: Ensure no proxy/firewall is blocking Google APIs

### Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid API key` | Wrong or missing Gemini API key | Check GEMINI_API_KEY in .env |
| `Project not found` | Wrong project ID | Verify GOOGLE_CLOUD_PROJECT |
| `Permission denied` | Service account lacks permissions | Add Vertex AI User role |
| `Billing not enabled` | No billing account | Enable billing in Console |
| `API not enabled` | Vertex AI API disabled | Enable in API Library |
| `Model not found` | Wrong model name or region | Use correct model ID |

### Support

If you're still stuck:
1. Check the logs with `--log-level debug`
2. Verify all environment variables are set
3. Test with the simple scripts above
4. Check Google Cloud Console for any alerts
