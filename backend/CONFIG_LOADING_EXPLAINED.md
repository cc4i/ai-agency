# How Configuration Loading Works in `backend/app/config.py`

Detailed explanation of how environment variables are loaded from `.env` file using Pydantic Settings.

## Overview

The `config.py` file uses **Pydantic Settings** (`pydantic-settings` package) to automatically load environment variables from:
1. `.env` file
2. System environment variables
3. Default values in the code

## Code Structure

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",              # Load from .env file
        env_file_encoding="utf-8",    # File encoding
        case_sensitive=False,         # Case-insensitive matching
        extra="ignore",               # Ignore extra env vars
    )

    redis_password: str = ""          # Default value

settings = Settings()  # Instantiate and load
```

## How It Works

### Step 1: Configuration via `SettingsConfigDict`

```python
model_config = SettingsConfigDict(
    env_file=".env",              # Load from .env file
    env_file_encoding="utf-8",    # File encoding
    case_sensitive=False,         # Case-insensitive matching
    extra="ignore",               # Ignore extra env vars
)
```

**Key Settings Explained**:

#### `env_file=".env"`
- Tells pydantic-settings to look for a file named `.env` in the current working directory
- The path is relative to where the Python process is started
- When running `uvicorn app.main:app`, the working directory is `backend/`, so it looks for `backend/.env`

#### `env_file_encoding="utf-8"`
- Specifies the character encoding for the `.env` file
- Ensures proper handling of special characters

#### `case_sensitive=False`
- Environment variable names are matched **case-insensitively**
- Example: All of these match `redis_password`:
  - `REDIS_PASSWORD=secret`
  - `redis_password=secret`
  - `Redis_Password=secret`
  - `ReDiS_pAsSwOrD=secret`

#### `extra="ignore"`
- Extra environment variables in `.env` that don't match any field are ignored
- Prevents errors when you have other env vars in the file

### Step 2: Field Definitions with Default Values

```python
class Settings(BaseSettings):
    # Field name: type = default_value
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
```

Each field:
- Has a **name** (e.g., `redis_password`)
- Has a **type** (e.g., `str`, `int`, `bool`)
- Has a **default value** (used if not found in env vars)

### Step 3: Loading Priority (Order of Precedence)

When `Settings()` is instantiated, values are loaded in this order (highest to lowest priority):

1. **System environment variables** (highest priority)
2. **`.env` file variables**
3. **Default values in code** (lowest priority)

#### Example Priority:

Given this configuration:

```python
# config.py
redis_password: str = "default_password"
```

And this `.env` file:

```bash
# .env
REDIS_PASSWORD=env_file_password
```

And this system environment:

```bash
export REDIS_PASSWORD=system_password
```

**Result**: `settings.redis_password = "system_password"` (system env wins)

### Step 4: Environment Variable Name Mapping

Pydantic automatically maps environment variable names to Python field names:

| Python Field Name | Environment Variable Name | Notes |
|-------------------|---------------------------|-------|
| `redis_host` | `REDIS_HOST` or `redis_host` | Case-insensitive |
| `redis_port` | `REDIS_PORT` or `redis_port` | Auto-converted to `int` |
| `redis_password` | `REDIS_PASSWORD` or `redis_password` | Loaded as `str` |
| `google_cloud_project` | `GOOGLE_CLOUD_PROJECT` or `google_cloud_project` | - |

## Practical Example

### 1. Create a `.env` File

Create `backend/.env`:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=my-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_API_KEY=your-api-key-here

# Redis Configuration
REDIS_HOST=10.0.0.5
REDIS_PORT=6379
REDIS_PASSWORD=my-secure-password

# Application Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### 2. How Values Are Loaded

When `settings = Settings()` is called in `config.py` line 68:

```python
settings = Settings()  # This line triggers the loading
```

Pydantic-settings:

1. **Reads the `.env` file**:
   ```
   GOOGLE_CLOUD_PROJECT=my-gcp-project
   REDIS_HOST=10.0.0.5
   REDIS_PASSWORD=my-secure-password
   ...
   ```

2. **Parses each line** and creates a dictionary:
   ```python
   {
       "google_cloud_project": "my-gcp-project",
       "redis_host": "10.0.0.5",
       "redis_password": "my-secure-password",
       ...
   }
   ```

3. **Checks system environment** for any variables (they override `.env`)

4. **Validates and converts types**:
   ```python
   redis_port: int = 6379  # "6379" string → 6379 integer
   debug: bool = True      # "false" string → False boolean
   ```

5. **Assigns to fields**:
   ```python
   settings.google_cloud_project = "my-gcp-project"
   settings.redis_host = "10.0.0.5"
   settings.redis_password = "my-secure-password"
   settings.redis_port = 6379  # Converted to int
   ```

### 3. Using the Settings

In any Python file:

```python
from app.config import settings

# Access configuration values
print(settings.redis_host)        # "10.0.0.5"
print(settings.redis_password)    # "my-secure-password"
print(settings.redis_port)        # 6379 (int)

# Use computed properties
print(settings.redis_url)         # "redis://:my-secure-password@10.0.0.5:6379/0"
```

## Type Conversion

Pydantic automatically converts string values from `.env` to the correct Python types:

### String Values

```python
redis_password: str = ""
```

`.env`:
```bash
REDIS_PASSWORD=my-secret
```

Result:
```python
settings.redis_password = "my-secret"  # str
```

### Integer Values

```python
redis_port: int = 6379
```

`.env`:
```bash
REDIS_PORT=6380
```

Result:
```python
settings.redis_port = 6380  # int (auto-converted)
```

### Boolean Values

```python
debug: bool = True
```

`.env` (accepts multiple formats):
```bash
# All of these work for True:
DEBUG=true
DEBUG=True
DEBUG=TRUE
DEBUG=1
DEBUG=on
DEBUG=yes

# All of these work for False:
DEBUG=false
DEBUG=False
DEBUG=FALSE
DEBUG=0
DEBUG=off
DEBUG=no
```

Result:
```python
settings.debug = False  # bool (auto-converted)
```

### Empty/Missing Values

If a variable is missing from both `.env` and system environment, the default value is used:

```python
redis_password: str = ""  # Default is empty string
```

If `.env` doesn't have `REDIS_PASSWORD`:
```python
settings.redis_password = ""  # Uses default
```

## Special Features

### 1. Computed Properties

You can create computed properties that depend on other settings:

```python
@property
def redis_url(self) -> str:
    """Construct Redis URL from components."""
    if self.redis_password:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
    return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
```

Usage:
```python
# If redis_password is set:
settings.redis_url  # "redis://:my-password@localhost:6379/0"

# If redis_password is empty:
settings.redis_url  # "redis://localhost:6379/0"
```

### 2. Validation

Pydantic validates types automatically:

```python
redis_port: int = 6379
```

If `.env` has:
```bash
REDIS_PORT=not-a-number
```

**Error**: `ValidationError` will be raised when `Settings()` is instantiated.

## Loading Workflow Diagram

```
┌─────────────────────────────────────────┐
│  settings = Settings()                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  1. Look for .env file                   │
│     Path: backend/.env                   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. Parse .env file                      │
│     REDIS_PASSWORD=secret                │
│     REDIS_HOST=10.0.0.5                  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. Check system environment             │
│     Override with env vars if present    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  4. Apply defaults                       │
│     Use default values if not found      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  5. Validate types                       │
│     Convert strings to int, bool, etc.   │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  6. Create Settings instance             │
│     settings.redis_password = "secret"   │
└─────────────────────────────────────────┘
```

## Real-World Examples

### Example 1: Local Development

**`backend/.env`**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
DEBUG=true
ENVIRONMENT=development
```

**Result**:
```python
settings.redis_host = "localhost"
settings.redis_port = 6379
settings.debug = True
settings.environment = "development"
```

### Example 2: Cloud Run Deployment

**No `.env` file** (use system environment variables)

Cloud Run sets:
```bash
REDIS_HOST=10.0.0.5
REDIS_PORT=6379
REDIS_PASSWORD=production-password
GOOGLE_CLOUD_PROJECT=my-project-id
ENVIRONMENT=production
DEBUG=false
```

**Result**:
```python
settings.redis_host = "10.0.0.5"
settings.redis_password = "production-password"
settings.debug = False
settings.environment = "production"
```

### Example 3: Override System Environment

**`backend/.env`**:
```bash
REDIS_HOST=localhost
```

**Terminal**:
```bash
export REDIS_HOST=10.0.0.5
python -m uvicorn app.main:app
```

**Result**:
```python
settings.redis_host = "10.0.0.5"  # System env wins!
```

## Security Best Practices

### 1. Never Commit `.env` to Git

Add to `.gitignore`:
```gitignore
.env
.env.local
.env.*.local
```

### 2. Use Environment Variables in Production

Don't use `.env` files in production. Instead, set environment variables directly:

```bash
# Cloud Run
gcloud run deploy ... --set-env-vars "REDIS_PASSWORD=secret"

# Docker
docker run -e REDIS_PASSWORD=secret ...

# Kubernetes
kubectl create secret generic app-secrets --from-literal=REDIS_PASSWORD=secret
```

### 3. Use Secrets Management

For sensitive values, use Secret Manager:

```bash
# Create secret
echo -n "my-password" | gcloud secrets create redis-password --data-file=-

# Cloud Run with secrets
gcloud run deploy ... --set-secrets "REDIS_PASSWORD=redis-password:latest"
```

## Debugging Configuration

### Print Current Configuration

```python
from app.config import settings

# Print all settings
print(settings.model_dump())

# Print specific values
print(f"Redis Host: {settings.redis_host}")
print(f"Redis Password: {'*' * len(settings.redis_password)}")  # Masked
print(f"Redis URL: {settings.redis_url}")
```

### Check Where Values Come From

```python
import os

# Check if value is in environment
print(f"REDIS_PASSWORD in env: {os.getenv('REDIS_PASSWORD')}")

# Check default
from app.config import Settings
print(f"Default redis_password: {Settings.model_fields['redis_password'].default}")
```

## Common Issues and Solutions

### Issue 1: `.env` File Not Found

**Error**: Settings use default values even though `.env` exists

**Solution**: Ensure `.env` is in the correct location
```bash
# Check current working directory
pwd

# Should be in backend/
ls -la .env
```

### Issue 2: Case Sensitivity

**Error**: `REDIS_PASSWORD` in `.env` but not loaded

**Solution**: With `case_sensitive=False`, this should work. Check for typos:
```bash
# Correct
REDIS_PASSWORD=secret

# Wrong (space before =)
REDIS_PASSWORD =secret
```

### Issue 3: Wrong Type

**Error**: `ValidationError` when loading settings

**Solution**: Check type matches:
```bash
# Wrong (string for int field)
REDIS_PORT=abc

# Correct
REDIS_PORT=6379
```

### Issue 4: Empty String vs Missing Value

```python
redis_password: str = "default"
```

**`.env`**:
```bash
# Empty string (explicit)
REDIS_PASSWORD=

# vs

# Missing value (uses default)
# (no REDIS_PASSWORD line)
```

**Result**:
```python
# With REDIS_PASSWORD=
settings.redis_password = ""  # Empty string

# Without REDIS_PASSWORD
settings.redis_password = "default"  # Default value
```

## Summary

The configuration loading in `backend/app/config.py`:

1. **Uses Pydantic Settings** for automatic environment variable loading
2. **Loads from `.env` file** automatically (if present)
3. **Prioritizes system environment** over `.env` file
4. **Falls back to defaults** if variable not found
5. **Validates and converts types** automatically
6. **Case-insensitive matching** for convenience
7. **Global `settings` instance** provides easy access throughout the app

This approach provides a robust, type-safe configuration system that works seamlessly in development (`.env` file) and production (environment variables).
