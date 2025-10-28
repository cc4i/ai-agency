# AI Agency Backend

Python 3.13+ backend for the AI Agency multi-agent system.

## Tech Stack

- **Runtime**: Python 3.13+
- **Package Manager**: uv (fast Rust-based installer)
- **Framework**: FastAPI with WebSocket support
- **State Management**: Redis (sessions, briefs, assets, events)
- **Background Tasks**: Celery with Redis broker
- **AI APIs**: Google AI (Gemini, Imagen, Veo, Lyria, Chirp)

## Project Structure

```
backend/
├── app/
│   ├── agents/              # Specialist AI agents
│   │   ├── base.py          # Base agent abstraction
│   │   ├── strategy.py      # Strategy Agent (Gemini Pro Vision + Pro)
│   │   ├── art_director.py  # Art Director Agent (Imagen)
│   │   ├── video_producer.py # Video Producer Agent (Veo)
│   │   ├── audio_team.py    # Audio Team Agent (Lyria + Chirp)
│   │   └── web_dev.py       # Web Dev Agent (Code Assist)
│   ├── producer/            # Executive Producer logic (Phase 3)
│   ├── services/            # Core services
│   │   ├── redis_client.py  # Redis data layer
│   │   ├── google_ai_client.py # Google AI API clients
│   │   ├── agent_registry.py # Agent management
│   │   ├── orchestration.py # Multi-agent coordination
│   │   └── event_bus.py     # Redis Pub/Sub event system
│   ├── models/              # Pydantic models
│   │   ├── brief.py         # Project Brief models
│   │   └── assets.py        # Asset and output models
│   ├── celery_app.py        # Celery configuration
│   ├── config.py            # Settings management
│   └── main.py              # FastAPI application
├── tests/                   # Unit tests
├── scripts/                 # Utility scripts
│   └── seed_demo_data.py    # Demo data seeder
├── pyproject.toml           # Dependencies (uv format)
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.13+
- Redis
- Google Cloud credentials with AI APIs enabled

### Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv --python 3.13
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
uv sync --dev
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials:
# - GOOGLE_APPLICATION_CREDENTIALS
# - GEMINI_API_KEY
# - REDIS_HOST/PORT
```

### Running

```bash
# Start Redis
docker run -d -p 6379:6379 redis:latest --appendonly yes

# Run FastAPI server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start Celery worker
uv run celery -A app.celery_app worker --loglevel=info

# Seed demo data
uv run python scripts/seed_demo_data.py --campaign=aura
```

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `WebSocket /ws/live/{session_id}` - Gemini Live streaming
- `WebSocket /ws/project/{project_id}` - Project brief updates
- `POST /api/sessions` - Create session
- `POST /api/projects` - Create project
- `POST /api/assets/upload` - Upload asset

## Development

### Code Quality

```bash
# Format code
uv run black .

# Lint code
uv run ruff check . --fix

# Type check
uv run mypy app/

# Run tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=app --cov-report=html
```

### Adding Dependencies

```bash
# Add runtime dependency
uv add <package-name>

# Add dev dependency
uv add --dev <package-name>

# Update all dependencies
uv lock --upgrade
```

## Architecture

### Agent System (Phase 2 ✓)

**5 Specialist Agents:**

1. **Strategy Agent** (`strategy.py`)
   - Analyzes product sketches with Gemini Pro Vision
   - Generates 3 customer personas
   - Creates 5 campaign slogans
   - Provides market analysis
   - Product-agnostic with category-specific guidelines

2. **Art Director Agent** (`art_director.py`)
   - Generates 4 hero images using Imagen
   - Adapts to product category visual guidelines
   - Creates style guide documentation
   - Theme and brand tone aware

3. **Video Producer Agent** (`video_producer.py`)
   - Generates 15-second social media videos with Veo
   - Internal critique loop (max 2 revisions)
   - Tracks revision history
   - Reference image-based generation

4. **Audio Team Agent** (`audio_team.py`)
   - Generates jingles with Lyria music generation
   - Creates TTS podcast ads with Lyria
   - Produces transcriptions with Chirp
   - Proactive suggestions based on theme analysis
   - Brand tone-adaptive music styles

5. **Web Dev Agent** (`web_dev.py`)
   - Generates landing page code (HTML/CSS/JS)
   - Product category-specific color schemes
   - Responsive design with countdown timer
   - Email signup form with validation

### Orchestration System

**Agent Registry** (`agent_registry.py`):
- Central registry for all agents
- Agent lookup and metadata
- Singleton access pattern

**Orchestration Service** (`orchestration.py`):
- Sequential and parallel agent execution
- Dependency management between agents
- Event-driven triggers
- Critique loop coordination
- Context sharing via Project Brief

**Event Bus** (`event_bus.py`):
- Redis Pub/Sub for real-time coordination
- Event publishing and subscription
- Async event listeners
- Agent collaboration triggers

**Celery Tasks** (`celery_app.py`):
- Background agent execution
- Parallel task processing
- Retry logic with exponential backoff
- Task queuing and routing

### Event-Driven Architecture

**Triggers:**
- `slogan_selected` → Art Director starts
- `image_selected` → Video Producer + Web Dev start (parallel)
- `theme_detected` → Audio Team proactive suggestion
- `brief_updated` → All agents receive context update

### Redis Data Schema

See `services/redis_client.py` for complete schema:
- Sessions: `session:{id}`
- Project Briefs: `project:{id}:brief`
- Agent State: `agent:{id}:status`
- Assets: `asset:{id}`
- Events: Pub/Sub channels `events:{type}`

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agents/test_strategy.py

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run with verbose output
uv run pytest -v -s
```

## Demo Data

Seed demo campaigns for testing:

```bash
# Aura Smart Sneaker (default)
uv run python scripts/seed_demo_data.py --campaign=aura

# All demo campaigns
uv run python scripts/seed_demo_data.py --campaign=all
```

Available campaigns:
- **aura**: Footwear, Tokyo neon, futuristic
- **ember**: Beverage, volcanic energy, edgy
- **luxe**: Fashion, Scandinavian minimalism, luxury
- **nova**: Electronics, ambient intelligence, professional

## Phase 2 Status ✓

**Completed:**
- ✓ All 5 specialist agents implemented
- ✓ Agent registry system
- ✓ Agent orchestration with dependencies
- ✓ Event-driven trigger system
- ✓ Celery background tasks
- ✓ Redis Pub/Sub event bus
- ✓ Critique loop for Video Producer
- ✓ Proactive collaboration (Audio Team)
- ✓ Product-agnostic agent design
- ✓ Unit test framework

**Next: Phase 3 - Executive Producer Logic**

## Troubleshooting

**Redis connection errors:**
```bash
# Check Redis is running
redis-cli ping  # Should return "PONG"

# Start Redis if needed
docker run -d -p 6379:6379 redis:latest --appendonly yes
```

**uv command not found:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# Add to PATH if needed
```

**Import errors:**
```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
uv sync --dev
```

## License

MIT
