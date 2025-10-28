# AI Agency

A multi-agent system where users act as Creative Directors, directing an AI-powered agency through a conversational interface. The system uses Gemini Live as the Executive Producer that coordinates specialist agents to complete creative campaign tasks.

## Project Overview

**Product-Agnostic Design**: The system supports ANY product category (footwear, beverage, electronics, fashion, beauty, food, automotive, etc.), not just the default "Aura Smart Sneaker" demo.

## Architecture

### Core Agent Roles

- **Executive Producer (Gemini Live)**: Primary user interface via streaming voice conversation
- **Strategy Agent (Gemini Pro)**: Generates customer personas, marketing copy, and campaign slogans
- **Art Director Agent (Imagen)**: Creates hero images and visual assets
- **Video Producer Agent (Veo)**: Generates social media video clips
- **Audio Team Agent (Lyria)**: Composes jingles, generates TTS voiceovers, creates podcast ads
- **Web Dev Agent (Gemini Code Assist)**: Generates and deploys landing page code

### Technology Stack

**Backend**:
- Python 3.13+ with FastAPI
- uv for package management
- Redis for state management
- Celery for async tasks
- WebSocket for bidirectional audio streaming

**Frontend**:
- Next.js 14+ (App Router)
- React 18+ with TypeScript 5+
- Tailwind CSS 3+ with shadcn/ui
- Zustand for state management
- WebSocket for real-time communication

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- Redis
- Google Cloud account with AI APIs enabled

### Backend Setup

```bash
cd backend

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux

# Create virtual environment
uv venv --python 3.13
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
uv sync --dev

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Start Redis
docker run -d -p 6379:6379 redis:latest --appendonly yes

# Run FastAPI server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Seed demo data (Aura Smart Sneaker campaign)
uv run python scripts/seed_demo_data.py --campaign=aura
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Open browser to http://localhost:3000
```

## Demo Campaigns

The system comes with multiple pre-configured demo campaigns:

- **Aura Smart Sneaker** (Default): Tokyo neon theme, futuristic footwear
- **Ember Energy Drink**: Volcanic energy theme, edgy beverage
- **Luxe Minimalist Watch**: Scandinavian minimalism, luxury fashion
- **Nova Smart Home Hub**: Ambient intelligence, professional electronics

Seed any campaign with:

```bash
python scripts/seed_demo_data.py --campaign=aura  # or ember, luxe, nova, all
```

## Development

### Backend Commands

```bash
# Run tests
uv run pytest -v

# Code formatting
uv run black .

# Linting
uv run ruff check . --fix

# Type checking
uv run mypy app/

# Start Celery worker
uv run celery -A app.celery worker --loglevel=info
```

### Frontend Commands

```bash
# Development server
npm run dev

# Production build
npm run build
npm start

# Run tests
npm test

# Lint TypeScript
npm run lint
```

## Project Status

**Current Phase**: Phase 2 Complete ✓ - Agent Layer

**Phase 1 Complete ✓ - Foundation & Infrastructure**:
- ✓ Project structure setup
- ✓ Python backend with uv and pyproject.toml
- ✓ Environment configuration
- ✓ Redis data schema and client service
- ✓ FastAPI application with WebSocket endpoints
- ✓ Pydantic models for Project Brief and Assets
- ✓ Base Agent abstraction class
- ✓ Google AI SDK integration stubs
- ✓ Demo seed data script with multiple product campaigns
- ✓ Next.js 14+ frontend with TypeScript and Tailwind CSS
- ✓ Git repository initialization

**Phase 2 Complete ✓ - Agent Layer**:
- ✓ Strategy Agent (Gemini Pro Vision + Pro)
- ✓ Art Director Agent (Imagen)
- ✓ Video Producer Agent (Veo with critique loop)
- ✓ Audio Team Agent (Lyria + Chirp with proactive suggestions)
- ✓ Web Dev Agent (Gemini Code Assist)
- ✓ Agent Registry system
- ✓ Agent Orchestration service (sequential + parallel execution)
- ✓ Event-driven trigger system (Redis Pub/Sub)
- ✓ Celery background task processing
- ✓ Unit test framework

**Next Steps**:
- Phase 3: Executive Producer Logic with Gemini Live
- Phase 4: Frontend Implementation with voice interface
- Phase 5: Integration & Polish

## Documentation

- [Design Document](./design.md)
- [Implementation Plan](./IMPLEMENTATION_PLAN.md)
- [Design Review](./DESIGN_REVIEW.md)
- [Product Flexibility](./PRODUCT_FLEXIBILITY.md)
- [Project Instructions](./CLAUDE.md)

## License

MIT
