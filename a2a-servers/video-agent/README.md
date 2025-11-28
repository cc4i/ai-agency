# A2A Video Producer Agent

A standalone A2A-compliant video generation agent server with SSE streaming support.

## Overview

This server implements the [A2A (Agent-to-Agent) Protocol](https://a2a-protocol.org/) for agent interoperability. It provides:

- **Agent Card Discovery** at `/.well-known/agent.json`
- **JSON-RPC 2.0 Endpoint** at `/a2a` for task management
- **SSE Streaming Endpoint** at `/a2a/stream` for real-time progress updates
- **Bearer Token Authentication**

## Quick Start

### Local Development

```bash
# Create virtual environment
cd a2a-servers/video-agent
uv venv && source .venv/bin/activate

# Install dependencies
uv pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Run the server
uvicorn app.main:app --reload --port 8001
```

### Docker

```bash
# Build and run
docker-compose up --build

# Or build manually
docker build -t a2a-video-agent .
docker run -p 8001:8001 a2a-video-agent
```

## API Endpoints

### Discovery

```bash
# Get Agent Card
curl http://localhost:8001/.well-known/agent.json
```

### Health Check

```bash
curl http://localhost:8001/health
```

### JSON-RPC (Synchronous)

```bash
# Send a message/task
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key_123" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req_001",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "msg_001",
        "role": "user",
        "parts": [
          {"type": "text", "text": "Create a 15s video for sneakers with Tokyo neon aesthetic"}
        ]
      }
    }
  }'
```

### SSE Streaming

```bash
# Stream task execution with real-time progress
curl -X POST http://localhost:8001/a2a/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test_api_key_123" \
  -H "Accept: text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req_001",
    "method": "message/stream",
    "params": {
      "message": {
        "messageId": "msg_001",
        "role": "user",
        "parts": [
          {"type": "text", "text": "Create a 15s video for sneakers with Tokyo neon aesthetic"}
        ]
      }
    }
  }'
```

## SSE Events

The streaming endpoint emits these events:

| Event | Description |
|-------|-------------|
| `task_created` | Task accepted and queued |
| `task_status` | Progress updates (0-100%) |
| `task_artifact` | Generated artifact |
| `task_completed` | Final result with all artifacts |
| `task_failed` | Error occurred |
| `task_cancelled` | Task was cancelled |
| `done` | Stream ended marker |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `http://localhost:8001` | Base URL for Agent Card |
| `API_KEY` | `test_api_key_123` | Bearer token for authentication |
| `PORT` | `8001` | Server port |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `MOCK_PROCESSING_DELAY` | `0.8` | Delay between progress updates (seconds) |

## Project Structure

```
video-agent/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings
│   ├── models/
│   │   ├── __init__.py
│   │   └── a2a.py           # A2A protocol models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── agent_card.py    # /.well-known/agent.json
│   │   ├── a2a.py           # /a2a JSON-RPC endpoint
│   │   └── a2a_stream.py    # /a2a/stream SSE endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   └── task_manager.py  # Task lifecycle management
│   └── core/
│       ├── __init__.py
│       └── auth.py          # Bearer token auth
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Converting to Real Implementation

To integrate real video generation:

1. Add your video generation service in `app/services/video_generator.py`
2. Update `task_manager.py` to call your service instead of mock delays
3. Configure cloud storage for artifact URLs
4. Update environment variables for your API keys

The A2A protocol interface remains unchanged — only the internal implementation changes.

## Testing

```bash
# Run tests
pytest -v

# With coverage
pytest --cov=app --cov-report=html
```

## License

Part of the AI Agency project.
