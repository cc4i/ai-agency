# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the "AI Agency" project - a multi-agent system where users act as Creative Directors, directing an AI-powered agency through a conversational interface. The system uses Gemini Live as the Executive Producer/Account Manager that coordinates specialist agents to complete creative campaign tasks.

**Product-Agnostic Design**: The system supports ANY product category (footwear, beverage, electronics, fashion, beauty, food, automotive, etc.), not just the default "Aura Smart Sneaker" demo. All agents adapt their outputs based on product_category, brand_tone, and theme.

## Architecture Concept

The system follows an agentic architecture with these key components:

### Core Agent Roles
- **Executive Producer (Gemini Live)**: Primary user interface via streaming voice conversation; manages task delegation and agent coordination
- **Strategy Agent (Gemini Pro)**: Generates customer personas, marketing copy, and campaign slogans
- **Art Director Agent (Imagen)**: Creates hero images and visual assets
- **Video Producer Agent (Veo)**: Generates social media video clips
- **Audio Team Agent (Lyria)**: Composes jingles, generates TTS voiceovers, creates podcast ads
- **Web Dev Agent (Gemini Code Assist)**: Generates and deploys landing page code

### Key Design Principles
1. **Agentic Planning**: The Producer presents a chain-of-thought plan before execution, requiring user approval
2. **Proactive Collaboration**: Agents work in parallel and share context autonomously without waiting for user commands
3. **Internal Critique Loop**: The Producer reviews agent outputs against the project brief before presenting to the user, with autonomous self-correction
4. **Continuous Conversation**: All interaction happens through Gemini Live streaming voice interface with persistent microphone

### Workflow Phases
1. **Phase 1 - Handoff & Planning**: User approval of agentic execution plan
2. **Phase 2 - Agency Hub**: Continuous Gemini Live session with task delegation and agent collaboration
3. **Phase 3 - Launch Party**: Final asset summary and presentation

## Project State

**Current Status**: Planning phase - contains design document and comprehensive implementation plan

**Key Files**:
- `design.md`: Original conceptual design and user flow
- `IMPLEMENTATION_PLAN.md`: Detailed 5-phase technical implementation plan (10 weeks)
- `DESIGN_REVIEW.md`: Alignment review between design and implementation plan

## Implementation Approach

**Technology Stack**:
- **Backend**: Python 3.13+ with FastAPI, uv for package management, Redis-only state management, Celery for async tasks
- **Frontend**: Next.js 14+ (App Router) with React 18+, TypeScript 5+, Tailwind CSS 3+, shadcn/ui, Zustand
- **Real-time**: WebSocket for bidirectional audio streaming and project brief updates
- **APIs**: Google AI services (Gemini Live, Gemini Pro, Imagen, Veo, Lyria, Code Assist)

**Critical Technical Requirements**:
1. **Audio-First Interface**: Bidirectional voice streaming via WebSocket (NOT text chat)
2. **Project Brief**: Real-time updating UI panel visible to user throughout workflow
3. **Event-Driven Architecture**: Redis Pub/Sub for autonomous agent notifications
4. **Critique Loop**: Producer autonomously evaluates agent outputs before presenting to user
5. **Proactive Collaboration**: Agents start work in parallel without explicit user commands

## Development Commands

When implemented, common commands will include:

```bash
# Backend (Python 3.13+ with uv)
cd backend

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh  # macOS/Linux
# or: pip install uv

# Create virtual environment
uv venv --python 3.13
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
uv pip install -e ".[dev]"

# Run FastAPI server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker
uv run celery -A app.celery worker --loglevel=info

# Run backend tests
uv run pytest -v

# Seed demo data (Aura Smart Sneaker campaign)
uv run python scripts/seed_demo_data.py

# Code formatting & linting
uv run black .
uv run ruff check . --fix
uv run mypy app/

# Add new package
uv pip install <package-name>

# Frontend (Next.js 14+ with Turbopack)
cd frontend
npm install

# Development server (with Turbopack)
npm run dev

# Production build
npm run build
npm start

# Run frontend tests
npm test

# Lint TypeScript
npm run lint

# Type checking
npm run type-check
```

## Redis Management

```bash
# Start Redis (Docker)
docker run -d -p 6379:6379 redis:latest --appendonly yes

# Connect to Redis CLI
redis-cli

# Monitor Redis commands
redis-cli MONITOR

# Check Redis memory usage
redis-cli INFO memory

# Flush all data (development only)
redis-cli FLUSHALL
```

## Key Implementation Phases

1. **Phase 1 (Weeks 1-2)**: Audio pipeline, Redis schema, Google AI SDK integration, demo seed data
2. **Phase 2 (Weeks 3-4)**: All 5 agents with Pydantic schemas, event-driven triggers, critique system
3. **Phase 3 (Weeks 5-6)**: Executive Producer with Gemini Live, prompt engineering, Project Brief management
4. **Phase 4 (Weeks 7-8)**: UI with persistent microphone, Project Brief panel, asset displays, Aura demo flow
5. **Phase 5 (Weeks 9-10)**: Integration testing, "Show Me the API" feature, polish

## Testing Strategy

- Unit tests with pytest for all agents and services
- Integration tests with fakeredis for Redis operations
- E2E tests with Playwright for complete Aura demo flow
- Mock Google AI API calls during development
