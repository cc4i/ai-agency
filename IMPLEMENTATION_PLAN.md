# AI Agency - Implementation Plan

## Overview
This document outlines the implementation plan for the AI Agency system, a multi-agent platform where users direct creative campaigns through conversational AI.

## Technology Stack Recommendations

### Backend
- **Runtime**: Python 3.13+ (leveraging PEP 701 f-string improvements, better error messages, PEP 695 type parameter syntax, and optimized asyncio performance)
- **Package Manager**: uv (fast Rust-based package installer and resolver by Astral)
  - **Why uv?**: 10-100x faster than pip/Poetry, drop-in replacement for pip/pip-tools/Poetry, unified toolchain, automatic Python version management, deterministic dependency resolution with lock files
- **Framework**: FastAPI 0.109+ for REST endpoints and WebSocket support
- **WebSocket Server**: FastAPI WebSocket for Gemini Live streaming conversation
- **State Management**: Redis for all state (sessions, projects, assets, cache)
- **Message Queue**: Celery with Redis broker for agent task coordination
- **Async Runtime**: asyncio with redis-py (async support) for high-performance async operations
- **Audio Processing**: Python audio libraries for encoding/decoding

### Frontend
- **Framework**: Next.js 14+ (App Router) with React 18+
- **Language**: TypeScript 5+
- **Styling**: Tailwind CSS 3+ for utility-first styling
- **UI Components**: shadcn/ui (Radix UI primitives)
- **Real-time**: WebSocket client for Gemini Live audio streaming
- **Audio**: Web Audio API for voice input/output processing
- **State Management**: Zustand for lightweight client state
- **Build Tool**: Turbopack (Next.js native)

### Google AI Services Integration
- Gemini Live API (WebSocket streaming)
- Gemini Pro API (text generation)
- Imagen API (image generation)
- Veo API (video generation)
- Lyria API (audio generation)
- Gemini Code Assist API (code generation)

## Implementation Phases

### Phase 1: Foundation & Infrastructure (Week 1-2)

#### 1.1 Project Setup
- Initialize project structure (backend/ + frontend/)
- Set up Python environment with **uv** (fast Rust-based package manager)
  - Benefits: 10-100x faster than pip/Poetry, automatic Python version management, lock file support
- Configure Python tooling:
  - Black for code formatting
  - Ruff for linting (also by Astral, written in Rust)
  - mypy for type checking
  - pytest for testing
- Create pyproject.toml with dependencies (PEP 621 format for uv compatibility)
- Initialize Git repository with proper .gitignore
- Set up pre-commit hooks

#### 1.2 Google AI SDK Integration
- Set up authentication for Google AI services
- Create API client wrappers for each service
- Implement rate limiting and error handling
- Create mock/stub implementations for development
- Write integration tests for each API client

#### 1.3 Core Backend Services
- Set up FastAPI application with basic routing
- Implement WebSocket endpoint for Gemini Live
- Create session management system with Redis
- Set up Redis data structures:
  - Hashes for project briefs and session state
  - Lists for conversation history
  - Sets for agent status tracking
  - Sorted Sets for asset versioning
  - Streams for event logs
- Configure Redis persistence (AOF + RDB snapshots)
- Implement environment configuration management (.env with pydantic-settings)
- Set up Celery worker for background agent tasks

#### 1.4 Audio Pipeline Architecture

**CRITICAL**: The entire user interaction is audio-first (bidirectional voice streaming), not text-based chat.

**Backend Audio Processing**
- Research Gemini Live API audio format requirements:
  - Supported audio encodings (PCM, Opus, WebM, etc.)
  - Sample rate and bit depth
  - Chunk size and streaming protocol
- Implement audio encoding/decoding pipeline:
  - Receive audio chunks from WebSocket
  - Encode for Gemini Live transmission
  - Decode Gemini Live audio responses
  - Stream to frontend via WebSocket
- Audio buffering strategy for low latency
- Handle audio stream synchronization with agent events

**Python Libraries**
- `pydub` or `soundfile` for audio format conversion
- `numpy` for audio data manipulation
- Research Gemini Live SDK audio utilities

**WebSocket Audio Protocol**
- Define message format for audio chunks:
  ```python
  {
    "type": "audio_input",
    "data": base64_encoded_audio,
    "sample_rate": 16000,
    "encoding": "pcm_s16le"
  }
  ```
- Implement chunked streaming (not full files)
- Handle connection drops and resumption

**Frontend Integration Points**
- WebSocket endpoint for audio streaming: `/ws/audio/{session_id}`
- Events: `audio_chunk_received`, `audio_playback_ready`
- Error handling for audio pipeline failures

#### 1.5 Initial Asset Management

**The "Sketch" Requirement**
- Producer says "I've pulled up the initial sketch"
- Strategy Agent "analyzes the sketch" (requires vision capability)

**Implementation Approach**
- Pre-seed demo with "Aura Smart Sneaker" initial sketch
- Support asset upload endpoint: `POST /api/assets/upload`
- Store in cloud storage (Google Cloud Storage recommended)
- Save metadata in Redis:
  ```
  asset:{asset_id} -> Hash {
    type: "image",
    url: "gs://bucket/sketch.png",
    description: "Aura Smart Sneaker Tokyo neon sketch",
    created_at: timestamp
  }
  ```
- Include asset URLs in agent context

**Strategy Agent Vision Capability**
- Use Gemini Pro Vision for sketch analysis
- Include image URL in prompt context
- Extract visual elements (Tokyo neon theme, glowing sole, etc.)

#### 1.6 Redis Data Schema Design
Design Redis key structure for efficient queries:

**Session Management**
```
session:{session_id} -> Hash {user_id, created_at, last_active, status}
session:{session_id}:conversation -> List [message_1, message_2, ...]
```

**Project Brief**
```
project:{project_id} -> Hash {name, status, created_at, updated_at}
project:{project_id}:brief -> Hash {theme, slogan, selected_assets, ...}
project:{project_id}:assets -> Sorted Set {score=timestamp, value=asset_id}
```

**Agent State**
```
agent:{agent_id}:status -> String {idle, working, completed, failed}
agent:{agent_id}:tasks -> List [task_1, task_2, ...]
agent:{agent_id}:result:{task_id} -> Hash {output, metadata, timestamp}
```

**Event Streaming**
```
events:{project_id} -> Stream {event_type, agent_id, data, timestamp}
```

**Asset Storage**
```
asset:{asset_id} -> Hash {type, url, metadata, created_at}
asset:{asset_id}:versions -> Sorted Set {score=version, value=data}
```

#### 1.7 Demo Seed Data - Multiple Product Examples

**Purpose**: Pre-configured campaigns for demonstration and testing across different product categories

**Product-Agnostic Campaign Schema**
```python
class CampaignTemplate(BaseModel):
    product_name: str
    product_category: str  # "footwear", "beverage", "electronics", "fashion", etc.
    theme: str
    key_features: List[str]
    target_market: str
    initial_sketch_url: str
    brand_tone: str  # "playful", "professional", "luxury", "edgy", etc.
```

**Demo Campaign 1: "Aura Smart Sneaker" (Default)**
- Category: Footwear
- Image: Tokyo neon street scene with glowing smart sneaker
- Theme: Futuristic, urban, neon-lit
- Key features visible: Glowing sole, sleek design
- File: `demo_assets/aura_sneaker_sketch.png`

```python
AURA_CAMPAIGN = {
    "product_name": "Aura Smart Sneaker",
    "product_category": "footwear",
    "theme": "Tokyo neon",
    "key_features": ["glowing sole", "smart tracking", "urban design"],
    "target_market": "Urban runners, tech enthusiasts, night joggers",
    "initial_sketch_url": "gs://ai-agency-demo/aura_sneaker_sketch.png",
    "brand_tone": "futuristic"
}
```

**Demo Campaign 2: "Ember Energy Drink"**
- Category: Beverage
- Theme: Volcanic power, extreme sports
- File: `demo_assets/ember_drink_sketch.png`

```python
EMBER_CAMPAIGN = {
    "product_name": "Ember Energy Drink",
    "product_category": "beverage",
    "theme": "Volcanic energy",
    "key_features": ["natural caffeine", "zero sugar", "volcanic minerals"],
    "target_market": "Athletes, gamers, extreme sports enthusiasts",
    "initial_sketch_url": "gs://ai-agency-demo/ember_drink_sketch.png",
    "brand_tone": "edgy"
}
```

**Demo Campaign 3: "Luxe Minimalist Watch"**
- Category: Fashion/Accessories
- Theme: Scandinavian minimalism
- File: `demo_assets/luxe_watch_sketch.png`

```python
LUXE_CAMPAIGN = {
    "product_name": "Luxe Minimalist Watch",
    "product_category": "fashion",
    "theme": "Scandinavian minimalism",
    "key_features": ["automatic movement", "sapphire crystal", "40mm case"],
    "target_market": "Young professionals, design enthusiasts, minimalists",
    "initial_sketch_url": "gs://ai-agency-demo/luxe_watch_sketch.png",
    "brand_tone": "luxury"
}
```

**Demo Campaign 4: "Nova Smart Home Hub"**
- Category: Electronics/Smart Home
- Theme: Ambient intelligence
- File: `demo_assets/nova_hub_sketch.png`

```python
NOVA_CAMPAIGN = {
    "product_name": "Nova Smart Home Hub",
    "product_category": "electronics",
    "theme": "Ambient intelligence",
    "key_features": ["voice control", "AI learning", "seamless integration"],
    "target_market": "Tech-savvy homeowners, early adopters, families",
    "initial_sketch_url": "gs://ai-agency-demo/nova_hub_sketch.png",
    "brand_tone": "professional"
}
```

**Expected Outputs (Product-Agnostic Test Fixtures)**

Strategy Agent (adapts to product category):
- 3 customer personas tailored to product category and target market
- 5 product-specific slogans
- Market analysis based on product category and demographics

Art Director (theme-based):
- 4 photorealistic images matching the product theme
- Prominent key product features
- Setting appropriate to theme and product category

Video Producer (category-aware):
- 15-second social media clip
- Close-up of key product features (per critique requirement)
- Background matching product theme

Audio Team (tone-adaptive):
- Jingle matching brand tone (uplifting/edgy/luxury/playful)
- Podcast ad with TTS voiceover appropriate to product
- Chirp transcription for international markets

Web Dev (category-styled):
- "Coming Soon" landing page
- Features: Hero image, slogan, countdown timer, email signup
- Color scheme matching product theme

**Seed Script Structure**
Create `scripts/seed_demo_data.py` with:
- Default: Aura Smart Sneaker campaign
- Command-line options to seed other product examples
- Function to create custom campaigns on-the-fly

```python
# Usage examples:
# python scripts/seed_demo_data.py --campaign=aura  # Default sneaker
# python scripts/seed_demo_data.py --campaign=ember  # Energy drink
# python scripts/seed_demo_data.py --campaign=luxe  # Watch
# python scripts/seed_demo_data.py --campaign=nova  # Smart home
# python scripts/seed_demo_data.py --custom --name="Product Name" --category="category"
```

### Phase 2: Agent Layer (Week 3-4)

#### 2.1 Agent Abstraction Layer
- Define base Agent interface/abstract class
- Implement agent lifecycle (initialize, execute, critique)
- Create agent registry system
- Build task queue for agent work items
- Implement agent-to-agent communication protocol

#### 2.2 Individual Agent Implementation
Each agent follows this structure (Python ABC):
```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class AgentBase(ABC):
    @abstractmethod
    async def execute(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's primary task"""
        pass

    @abstractmethod
    async def critique(self, result: Dict[str, Any], brief: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the result against project brief"""
        pass

    @abstractmethod
    async def revise(self, result: Dict[str, Any], critique: Dict[str, Any]) -> Dict[str, Any]:
        """Revise the result based on critique"""
        pass
```

**Strategy Agent (Gemini Pro with Vision) - PRODUCT-AGNOSTIC**
- Input: Product sketch (image URL), campaign requirements, **product_category**, **brand_tone**
- Output: Exactly 3 personas + exactly 5 slogans + market analysis
- API: Gemini Pro Vision (for sketch analysis) + Gemini Pro (for strategy)
- Adapts to: Any product category (footwear, beverage, electronics, fashion, beauty, food, automotive, etc.)

```python
from pydantic import BaseModel, Field
from typing import List

class CustomerPersona(BaseModel):
    name: str
    age_range: str
    description: str
    pain_points: List[str]
    motivations: List[str]
    product_usage_context: str  # How they would use THIS product

class StrategyAgentOutput(BaseModel):
    personas: List[CustomerPersona] = Field(..., min_length=3, max_length=3)
    slogans: List[str] = Field(..., min_length=5, max_length=5)
    market_analysis: str
    visual_theme_extracted: str  # From sketch analysis
    category_insights: str  # Category-specific market insights

# Example prompt template (product-agnostic)
STRATEGY_PROMPT_TEMPLATE = """
Analyze this {product_category} product sketch: {sketch_url}

Product: {product_name}
Category: {product_category}
Theme: {theme}
Key Features: {key_features}
Brand Tone: {brand_tone}
Target Market: {target_market}

Visual Analysis Instructions:
- Extract visual theme and aesthetics from the sketch
- Identify key product features visible in the image
- Understand the product context and usage environment

Generate:
1. Exactly 3 customer personas specific to {product_category} buyers
   - Consider category-specific behaviors and needs
   - Include product usage contexts (e.g., when/where/how they'd use it)
2. Exactly 5 catchy slogans that resonate with {brand_tone} tone
   - Adapt language to product category conventions
3. Market analysis summary for the {product_category} category
   - Include category trends and competitive landscape
"""
```

**Art Director Agent (Imagen) - PRODUCT-AGNOSTIC**
- Input: Selected slogan, theme, **product_category**, **brand_tone**, style references
- Output: Exactly 4 photorealistic images
- API: Imagen 3 image generation
- Adapts to: Product-specific visual requirements (e.g., food styling, fashion photography, product placement)

```python
class ImageAsset(BaseModel):
    asset_id: str
    url: str
    generation_params: dict
    description: str

class ArtDirectorOutput(BaseModel):
    images: List[ImageAsset] = Field(..., min_length=4, max_length=4)
    style_guide: str

# Example prompt template (product-agnostic)
ART_DIRECTOR_PROMPT_TEMPLATE = """
Create a photorealistic hero image for a {product_category} campaign.

Product: {product_name}
Category: {product_category}
Slogan: "{slogan}"
Theme: {theme}
Brand Tone: {brand_tone}
Key Features to highlight: {key_features}

Category-Specific Guidelines:
{category_visual_guidelines}

Style: {style_description}
Setting: {setting_description}
Composition: Product should be the focal point
Lighting: Professional {category}-appropriate lighting
"""

# Category-specific visual guidelines
CATEGORY_VISUAL_GUIDELINES = {
    "footwear": "Show product in action or lifestyle context, emphasize texture and materials",
    "beverage": "Focus on condensation, pour shots, refreshment appeal, vibrant colors",
    "electronics": "Clean product shots, emphasize sleek design, modern tech environment",
    "fashion": "Lifestyle imagery, model interaction, emphasis on fabric and fit",
    "beauty": "Close-up product shots, elegant presentation, skin/texture focus",
    "food": "Appetizing food styling, fresh ingredients, warm inviting lighting",
    "automotive": "Dynamic angles, motion blur or still power shots, environment context",
}
```

**Video Producer Agent (Veo)**
- Input: Selected hero image, campaign brief
- Output: Social media video clip (with critique/revision capability)
- API: Veo 2 video generation
- Feature: Internal critique and revision loop (max 2 revisions)

```python
class VideoAsset(BaseModel):
    asset_id: str
    url: str
    duration_seconds: float
    generation_params: dict
    revision_number: int = 0

class VideoProducerOutput(BaseModel):
    video: VideoAsset
    critique_notes: Optional[str] = None
    revision_history: List[str] = []
```

**Audio Team Agent (Lyria + Chirp)**
- Input: Theme, slogan, brand guidelines
- Output: 3 distinct assets (jingle, podcast ad, transcription)
- API: Lyria (music + TTS), Chirp (transcription)
- Feature: Proactive suggestions based on theme

```python
class AudioAsset(BaseModel):
    asset_id: str
    url: str
    duration_seconds: float
    audio_type: str  # "jingle", "podcast_ad"

class TranscriptionAsset(BaseModel):
    asset_id: str
    text: str
    language: str
    format: str  # "srt", "vtt", "txt"

class AudioTeamOutput(BaseModel):
    jingle: AudioAsset
    podcast_ad: AudioAsset
    transcription: TranscriptionAsset
    proactive_suggestion: Optional[str] = None  # E.g., beat style recommendation
```

**Web Dev Agent (Code Assist)**
- Input: Hero image URL, slogan, brand assets
- Output: Landing page HTML/CSS/JS code
- API: Gemini Code Assist
- Feature: Live code rendering in sandboxed iframe

```python
class CodeAsset(BaseModel):
    asset_id: str
    html: str
    css: str
    javascript: str
    preview_url: Optional[str] = None  # If deployed

class WebDevOutput(BaseModel):
    code: CodeAsset
    framework: str = "vanilla"  # or "react", "vue", etc.
    deployment_status: str = "preview"  # or "deployed"
```

#### 2.3 Agent Orchestration System

**Task Dependency Graph**
- Define agent execution order and dependencies
- Support parallel execution where possible
- Example flow:
  ```
  Strategy Agent (sequential)
    ↓
  User selects slogan
    ↓
  Art Director (sequential)
    ↓
  User selects image
    ↓
  [Video Producer || Audio Team || Web Dev] (parallel)
  ```

**Event-Driven Trigger System**

Use Redis Pub/Sub for real-time agent notifications:

```python
# Event types
AGENT_EVENTS = {
    "slogan_selected": ["art_director"],
    "image_selected": ["video_producer", "web_dev"],
    "theme_detected": ["audio_team"],  # Proactive
    "brief_updated": ["all_agents"]
}

# Publisher (Producer)
async def publish_event(event_type: str, data: dict):
    await redis.publish(f"events:{event_type}", json.dumps(data))

# Subscriber (Agents)
async def agent_event_listener(agent_id: str):
    pubsub = redis.pubsub()
    for event in get_subscriptions(agent_id):
        await pubsub.subscribe(f"events:{event}")

    async for message in pubsub.listen():
        await handle_agent_trigger(agent_id, message)
```

**Proactive Collaboration Rules**

Autonomous triggers (no user command required):
1. **Image Selected** → Auto-notify Video Producer and Web Dev
   - They receive image URL and start work in parallel
2. **Theme Detected** → Audio Team proactive suggestion
   - Audio Agent analyzes theme and suggests beat style
   - Sends suggestion to Producer for user approval
3. **Brief Updated** → All agents receive context update
   - Agents can adjust in-progress work

**Context Sharing Mechanism**

Centralized Project Brief with versioning:
```python
class ProjectBrief(BaseModel):
    project_id: str
    product_name: str
    theme: str
    selected_slogan: Optional[str] = None
    selected_image: Optional[ImageAsset] = None
    target_personas: List[CustomerPersona] = []
    version: int = 1
    updated_at: datetime

# Store in Redis with versioning
async def update_brief(project_id: str, updates: dict):
    brief = await get_brief(project_id)
    brief.version += 1
    brief.updated_at = datetime.utcnow()
    # Merge updates
    for key, value in updates.items():
        setattr(brief, key, value)

    # Save to Redis
    await redis.hset(f"project:{project_id}:brief", mapping=brief.dict())

    # Publish update event
    await publish_event("brief_updated", {"project_id": project_id, "version": brief.version})
```

**Internal Critique Loop System**

Producer evaluates agent outputs before presenting to user:

```python
class CritiqueSystem:
    async def evaluate(self, agent_output: Any, brief: ProjectBrief) -> CritiqueResult:
        """
        Producer analyzes agent output against project brief
        """
        prompt = f"""
        Analyze this {agent_output.__class__.__name__} against the project brief.

        Project Brief: {brief.dict()}
        Agent Output: {agent_output.dict()}

        Evaluate:
        1. Does it match the theme? ({brief.theme})
        2. Does it include required features?
        3. Is the quality acceptable?

        Return: PASS or specific revision instructions
        """

        critique = await gemini_pro.generate(prompt)
        return CritiqueResult.parse(critique)

class CritiqueResult(BaseModel):
    status: str  # "PASS" or "REVISE"
    score: float  # 0.0 to 1.0
    issues: List[str] = []
    revision_instructions: Optional[str] = None

# Example: Video Producer critique (from design.md)
# "The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'.
# I'm sending it back to the agent with instructions for a 2-second close-up."
```

**Revision Workflow**
- Max 2 revisions per agent task
- After 2 failed revisions, escalate to user for guidance
- Track revision history in agent output

#### 2.4 Parallel Execution Engine

Use Celery for async agent task execution:

```python
from celery import group

# Execute multiple agents in parallel
@celery.task
def execute_agent(agent_id: str, task: dict, context: dict):
    agent = agent_registry.get(agent_id)
    result = await agent.execute(task, context)

    # Store result
    await redis.hset(f"agent:{agent_id}:result:{task['id']}", mapping=result.dict())

    # Publish completion event
    await publish_event("agent_completed", {"agent_id": agent_id, "task_id": task['id']})

    return result

# Parallel execution
async def run_parallel_agents(agents: List[str], task: dict, context: dict):
    job = group(execute_agent.s(agent_id, task, context) for agent_id in agents)
    result = job.apply_async()
    return await result.get()
```

### Phase 3: Executive Producer Logic (Week 5-6)

#### 3.1 Gemini Live Integration

**Connection Architecture: Frontend ↔ Backend ↔ Gemini Live**

```
┌──────────┐         ┌──────────┐         ┌──────────────┐
│          │         │          │         │              │
│ Frontend │◄───────►│ FastAPI  │◄───────►│ Gemini Live  │
│  (Next)  │ WebSocket│ Backend  │ WebSocket│     API      │
│          │         │          │         │              │
└──────────┘         └──────────┘         └──────────────┘
     ▲                    │                      │
     │                    │                      │
     │                    ▼                      ▼
  Audio +            Redis Cache           Audio + Text
   Text           (Conversation            (Streaming)
 Display           History)
```

**Dual Output Support: Audio + Text**

Gemini Live API provides both audio and text in real-time:
- **Audio Stream**: For speaking/listening experience
- **Text Transcript**: For reading, accessibility, and conversation history

**WebSocket Endpoint: `/ws/live/{session_id}`**

Single WebSocket connection handles:
1. User audio input → Gemini Live
2. Gemini Live audio output → User
3. Gemini Live text transcript → User (simultaneous)
4. User text transcript (from STT) → Display

**Backend Connection Handler**

```python
from fastapi import WebSocket
import asyncio
import json

class GeminiLiveConnection:
    """Manages bidirectional connection between frontend and Gemini Live"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.frontend_ws: Optional[WebSocket] = None
        self.gemini_ws: Optional[WebSocket] = None
        self.conversation_history: List[dict] = []

    async def connect(self, frontend_websocket: WebSocket):
        """Establish connection chain: Frontend → Backend → Gemini Live"""

        # Accept frontend connection
        await frontend_websocket.accept()
        self.frontend_ws = frontend_websocket

        # Connect to Gemini Live API
        self.gemini_ws = await self._connect_to_gemini_live()

        # Start bidirectional streaming
        await asyncio.gather(
            self._handle_frontend_to_gemini(),
            self._handle_gemini_to_frontend(),
            return_exceptions=True
        )

    async def _connect_to_gemini_live(self) -> WebSocket:
        """Establish WebSocket connection to Gemini Live API"""
        import websockets

        gemini_ws = await websockets.connect(
            GEMINI_LIVE_WS_URL,
            extra_headers={
                "Authorization": f"Bearer {GEMINI_API_KEY}",
                "Content-Type": "application/json"
            }
        )

        # Send initial configuration
        await gemini_ws.send(json.dumps({
            "setup": {
                "model": "gemini-2.0-flash-exp",
                "generation_config": {
                    "response_modalities": ["AUDIO", "TEXT"],  # CRITICAL: Request both
                    "speech_config": {
                        "voice_config": {"prebuilt_voice_config": {"voice_name": "Puck"}}
                    }
                }
            }
        }))

        return gemini_ws

    async def _handle_frontend_to_gemini(self):
        """Forward user input (audio) to Gemini Live"""
        async for message in self.frontend_ws.iter_json():
            if message['type'] == 'audio_input':
                # User speaking
                audio_data = base64.b64decode(message['data'])

                # Forward to Gemini Live
                await self.gemini_ws.send(json.dumps({
                    "realtime_input": {
                        "media_chunks": [{
                            "data": base64.b64encode(audio_data).decode(),
                            "mime_type": "audio/pcm"
                        }]
                    }
                }))

    async def _handle_gemini_to_frontend(self):
        """Receive from Gemini Live and forward BOTH audio and text to frontend"""
        async for message in self.gemini_ws:
            data = json.loads(message)

            # Gemini Live sends multiple message types
            if "serverContent" in data:
                content = data["serverContent"]

                # Extract audio if present
                if "modelTurn" in content:
                    for part in content["modelTurn"].get("parts", []):

                        # Audio stream
                        if "inlineData" in part:
                            audio_b64 = part["inlineData"]["data"]

                            # Send audio to frontend
                            await self.frontend_ws.send_json({
                                "type": "audio_output",
                                "data": audio_b64,
                                "mime_type": part["inlineData"]["mimeType"]
                            })

                        # Text transcript (simultaneous with audio)
                        if "text" in part:
                            text_content = part["text"]

                            # Send text to frontend for display
                            await self.frontend_ws.send_json({
                                "type": "text_output",
                                "text": text_content,
                                "role": "assistant",
                                "timestamp": datetime.utcnow().isoformat()
                            })

                            # Save to conversation history
                            await self._save_to_history("assistant", text_content)

            # Turn complete event
            if "turnComplete" in data:
                await self.frontend_ws.send_json({
                    "type": "turn_complete"
                })

    async def _save_to_history(self, role: str, text: str):
        """Save conversation to Redis for persistence"""
        message = {
            "role": role,
            "text": text,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.conversation_history.append(message)

        # Store in Redis
        await redis.lpush(
            f"session:{self.session_id}:conversation",
            json.dumps(message)
        )
```

**Audio Input Processing (with STT for text display)**

```python
async def handle_user_audio_with_transcript(audio_chunk: bytes, session_id: str):
    """
    Process user audio and generate text transcript for display
    """
    # Send audio to Gemini Live (for voice processing)
    await send_to_gemini_live(audio_chunk)

    # ALSO: Generate text transcript for user's speech (optional but recommended)
    # This can be done via:
    # 1. Gemini Live's built-in STT
    # 2. Google Speech-to-Text API
    # 3. Extract from Gemini's understanding

    # For now, rely on Gemini Live's interpretation
    # It will echo back what it understood in the conversation
```

**Connection Management**
- Handle WebSocket reconnection
- Buffer audio during network issues
- Synchronize audio state across reconnects
- Implement heartbeat/ping-pong

**Turn-Taking Logic**
- Voice Activity Detection (VAD) on backend
- End-of-speech detection
- Interruption handling (user can interrupt Producer mid-speech)
- Manage conversation flow state

**Research Tasks**
- [ ] Determine Gemini Live audio format (PCM/Opus/WebM)
- [ ] Identify sample rate and encoding requirements
- [ ] Test latency and buffering strategies
- [ ] Verify bi-directional streaming protocol

#### 3.2 Producer Intelligence Layer

**Chain-of-Thought Planning Generation**

Producer presents plan before execution:

```python
class ProducerPlanner:
    async def generate_plan(self, campaign_brief: dict) -> CampaignPlan:
        """Generate 5-phase execution plan"""
        system_prompt = """
        You are an Executive Producer managing a creative agency.
        Given a campaign brief, create a detailed 5-phase execution plan.

        Present the plan in this format:
        "To launch the [PRODUCT], I've broken the project into 5 phases:

        First, our Strategy Agent [Gemini Pro] will [TASK].
        Then, our Art Director [Imagen] will [TASK].
        After that, our Video Producer [Veo] will [TASK].
        Simultaneously, our Audio Team [Lyria] will [TASK].
        Finally, our Web Dev Agent [Gemini Code Assist] will [TASK].

        This plan is now in your Project Brief. Shall I task the Strategy Agent to begin?"
        """

        plan = await gemini_pro.generate(
            system=system_prompt,
            prompt=f"Campaign: {campaign_brief}"
        )

        return CampaignPlan.parse(plan)

class CampaignPlan(BaseModel):
    phases: List[PlanPhase]
    approval_status: str = "pending"  # pending, approved, rejected

class PlanPhase(BaseModel):
    phase_number: int
    agent: str
    task_description: str
    dependencies: List[int] = []  # Which phases must complete first
```

**Task Delegation Logic**

```python
class ProducerDelegator:
    async def delegate_task(self, agent_id: str, task: dict):
        """Announce task delegation via voice and execute"""

        # Generate voice announcement
        announcement = f"Okay, I've tasked our {agent_id} with {task['description']}"

        # Convert to speech (Gemini Live TTS)
        await self.speak(announcement)

        # Execute agent task
        result = await execute_agent.delay(agent_id, task, context)

        # Monitor progress
        await self.monitor_agent(agent_id, task['id'])

        return result
```

**Agent Status Monitoring**

```python
async def monitor_agent(self, agent_id: str, task_id: str):
    """Monitor agent progress and provide updates to user"""

    # Show thinking animation
    await self.send_ui_event("agent_thinking", {"agent_id": agent_id})

    # Poll for completion
    while True:
        status = await redis.get(f"agent:{agent_id}:status")

        if status == "completed":
            result = await redis.hgetall(f"agent:{agent_id}:result:{task_id}")

            # Run critique if applicable
            if agent_id in ["video_producer"]:
                critique = await self.critique_system.evaluate(result, brief)

                if critique.status == "REVISE":
                    await self.speak(critique.revision_instructions)
                    await self.request_revision(agent_id, critique)
                    continue  # Wait for revision

            # Present to user
            await self.present_result(agent_id, result)
            break

        await asyncio.sleep(1)
```

**Critique and Revision Orchestration**

Example from design (Video Producer):

```python
async def present_video_result(self, result: VideoProducerOutput):
    """Present video with autonomous critique"""

    # Announce completion
    await self.speak("Okay, our Video Producer Agent has a first pass...")

    # Show video to user
    await self.send_ui_event("video_ready", result.dict())

    # Internal critique
    critique = await self.critique_system.evaluate(result, self.brief)

    if critique.status == "REVISE":
        # Producer explains the issue
        await self.speak(f"Hmm, I'm analyzing it against our brief. {critique.issues[0]}. I'm sending it back to the agent with instructions for {critique.revision_instructions}.")

        # Request revision
        revised = await self.video_producer.revise(result, critique)

        # Present revision
        await self.speak("Okay, the revision is complete. Here is the new version.")
        await self.send_ui_event("video_ready", revised.dict())
    else:
        # Pass, no revision needed
        pass
```

**Proactive Suggestion System**

Audio Team proactive suggestion example:

```python
async def handle_audio_suggestion(self):
    """Audio Agent makes proactive suggestion based on detected theme"""

    # Audio Agent analyzes brief and generates suggestion
    suggestion = await self.audio_team.generate_suggestion(self.brief)

    if suggestion:
        # Producer relays suggestion to user
        await self.speak(f"While they work, our Audio Agent has a proactive suggestion: {suggestion.text}. Do you want to hear a sample?")

        # Wait for user response
        response = await self.wait_for_voice_input()

        if "yes" in response.lower():
            # Generate and play sample
            sample = await self.audio_team.generate_sample(suggestion)
            await self.send_ui_event("audio_sample", sample.dict())
```

#### 3.2.1 Executive Producer Personality & Prompts

**System Prompt**

```
You are the Executive Producer of a creative AI agency. Your role is to:
1. Present clear, professional plans to the Creative Director (user)
2. Delegate tasks to specialist agents (Strategy, Art Director, Video, Audio, Web Dev)
3. Provide status updates as agents work
4. Evaluate agent outputs and request revisions when needed
5. Explain your reasoning when critiquing work

Tone: Professional, collaborative, explanatory
Voice: First-person ("I've tasked...", "I'm analyzing...")
Style: Announce actions before performing them, explain agent roles

Example dialogue:
- "Welcome. I'm your Executive Producer. Our first project is the 'Aura' Smart Sneaker launch."
- "Okay, I've tasked our Strategy Agent [Gemini Pro] with analyzing the sketch."
- "Excellent choice. Now, I'm sending this slogan to our Art Director Agent."
- "I'm analyzing it against our brief. The theme is strong, but it doesn't show the glowing sole."
```

**Response Templates**

Planning:
```
"To launch the {PRODUCT}, I've broken the project into 5 phases:

First, our Strategy Agent [Gemini Pro] will {TASK}.
Then, our Art Director [Imagen] will {TASK}.
After that, our Video Producer [Veo] will {TASK}.
Simultaneously, our Audio Team [Lyria] will {TASK}.
Finally, our Web Dev Agent [Gemini Code Assist] will {TASK}.

This plan is now in your Project Brief. Shall I task the Strategy Agent to begin?"
```

Task Delegation:
```
"Okay, I've tasked our {AGENT} with {TASK}."
```

Result Presentation:
```
"{AGENT} has generated {OUTPUT}. {DESCRIPTION}. They are on your screen now."
```

Critique:
```
"Hmm, I'm analyzing it against our brief. {ISSUE}. I'm sending it back to the agent with instructions for {FIX}."
```

Completion:
```
"And with that, our campaign is complete. All assets are available in your project brief."
```

#### 3.3 Project Brief Management

**CRITICAL**: The Project Brief is a **user-visible living document** that updates in real-time.

**Project Brief Schema (Product-Agnostic)**
```python
class ProjectBrief(BaseModel):
    # Identifiers
    project_id: str
    session_id: str

    # Campaign basics (PRODUCT-AGNOSTIC)
    product_name: str
    product_category: str  # "footwear", "beverage", "electronics", "fashion", "beauty", etc.
    theme: str
    key_features: List[str]
    brand_tone: str  # "futuristic", "luxury", "playful", "edgy", "professional", etc.
    target_market: str
    initial_sketch_url: Optional[str] = None

    # Strategy outputs
    personas: List[CustomerPersona] = []
    slogans: List[str] = []
    selected_slogan: Optional[str] = None

    # Art outputs
    hero_images: List[ImageAsset] = []
    selected_image: Optional[ImageAsset] = None

    # Execution plan
    campaign_plan: Optional[CampaignPlan] = None
    plan_approved: bool = False

    # Asset tracking
    completed_assets: Dict[str, Any] = {}  # {agent_id: asset}

    # Metadata
    version: int = 1
    created_at: datetime
    updated_at: datetime
    status: str = "planning"  # planning, executing, completed
```

**Brief Update and Real-Time Sync**

When Producer updates the brief, it must sync to the UI immediately:

```python
async def update_project_brief(project_id: str, updates: dict):
    """Update brief and notify frontend"""

    # Get current brief
    brief = await get_brief(project_id)

    # Apply updates
    for key, value in updates.items():
        setattr(brief, key, value)

    brief.version += 1
    brief.updated_at = datetime.utcnow()

    # Save to Redis
    await redis.hset(f"project:{project_id}:brief", mapping=brief.dict())

    # Publish WebSocket event for real-time UI update
    await websocket_manager.broadcast(
        project_id,
        {
            "type": "brief_updated",
            "brief": brief.dict(),
            "changed_fields": list(updates.keys())
        }
    )

    # Publish Redis event for agents
    await publish_event("brief_updated", {"project_id": project_id, "version": brief.version})

    return brief
```

**Key Brief Update Moments** (from design):

1. **Plan Created**: "This plan is now in your Project Brief"
   ```python
   await update_project_brief(project_id, {"campaign_plan": plan, "status": "planning"})
   ```

2. **Slogan Selected**: "I've added that to the project brief"
   ```python
   await update_project_brief(project_id, {"selected_slogan": "Run on light"})
   ```

3. **Image Selected**: "I've added that to the project brief"
   ```python
   await update_project_brief(project_id, {"selected_image": image})
   ```

4. **Asset Completed**: Each agent completion updates brief
   ```python
   await update_project_brief(project_id, {"completed_assets": {agent_id: asset}})
   ```

**Asset Tracking System**

Track all generated assets with lineage:

```python
class AssetTracker:
    async def register_asset(self, project_id: str, agent_id: str, asset: Any):
        """Register asset and update brief"""

        asset_id = generate_asset_id()

        # Store asset in Redis
        await redis.hset(f"asset:{asset_id}", mapping={
            "type": asset.__class__.__name__,
            "data": asset.json(),
            "agent_id": agent_id,
            "project_id": project_id,
            "created_at": datetime.utcnow().isoformat()
        })

        # Add to project's asset list
        await redis.zadd(f"project:{project_id}:assets", {asset_id: time.time()})

        # Update brief
        brief = await get_brief(project_id)
        brief.completed_assets[agent_id] = asset
        await update_project_brief(project_id, {"completed_assets": brief.completed_assets})

        return asset_id
```

### Phase 4: Frontend Implementation (Week 7-8)

**Tech Stack Specifics**:
- Next.js 14+ with App Router (Server Components + Client Components)
- TypeScript 5+ for type safety
- Tailwind CSS 3+ for styling
- shadcn/ui (Radix UI primitives) for accessible components
- Zustand for lightweight client-side state
- Web Audio API for audio processing
- WebSocket for real-time communication

**Next.js App Router Architecture**

```typescript
// src/app/layout.tsx (Root Layout - Server Component)
export default function RootLayout({ children }: { children: React.Node }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
      </body>
    </html>
  );
}

// src/app/page.tsx (Main Page - Server Component wrapper)
import { WorkspaceClient } from '@/components/WorkspaceClient';

export default function Home() {
  return <WorkspaceClient />;
}

// src/components/WorkspaceClient.tsx (Client Component for interactivity)
'use client';

export function WorkspaceClient() {
  const projectBrief = useProjectStore();

  return (
    <div className="flex h-screen">
      <ProjectBriefPanel brief={projectBrief} />
      <Workspace />
      <PersistentMicrophone />
    </div>
  );
}
```

**Zustand Store for Project State**

```typescript
// src/lib/stores/projectStore.ts
import { create } from 'zustand';

interface ProjectStore {
  brief: ProjectBrief | null;
  assets: Record<string, any>;
  currentAgent: string | null;
  isListening: boolean;
  isThinking: boolean;

  setBrief: (brief: ProjectBrief) => void;
  updateBrief: (updates: Partial<ProjectBrief>) => void;
  addAsset: (agentId: string, asset: any) => void;
  setCurrentAgent: (agentId: string | null) => void;
  setListening: (isListening: boolean) => void;
  setThinking: (isThinking: boolean) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  brief: null,
  assets: {},
  currentAgent: null,
  isListening: false,
  isThinking: false,

  setBrief: (brief) => set({ brief }),
  updateBrief: (updates) => set((state) => ({
    brief: state.brief ? { ...state.brief, ...updates } : null
  })),
  addAsset: (agentId, asset) => set((state) => ({
    assets: { ...state.assets, [agentId]: asset }
  })),
  setCurrentAgent: (agentId) => set({ currentAgent: agentId }),
  setListening: (isListening) => set({ isListening }),
  setThinking: (isThinking) => set({ isThinking }),
}));
```

**Conversation Panel Component**

```typescript
// src/components/ConversationPanel.tsx
'use client';

import { useConversationStore } from '@/lib/stores/conversationStore';

interface Message {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
  isPartial?: boolean;  // For streaming text
}

export function ConversationPanel() {
  const { messages, currentMessage } = useConversationStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentMessage]);

  return (
    <div className="conversation-panel h-full flex flex-col">
      <div className="header p-4 border-b border-slate-700">
        <h3 className="text-lg font-semibold">Conversation</h3>
        <p className="text-sm text-slate-400">Audio + Text Transcript</p>
      </div>

      <div className="messages flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div
            key={index}
            className={`message ${message.role}`}
          >
            <div className="flex items-start gap-3">
              <div className="avatar">
                {message.role === 'user' ? '👤' : '🤖'}
              </div>
              <div className="content flex-1">
                <div className="role text-sm font-medium text-slate-400">
                  {message.role === 'user' ? 'You' : 'Producer'}
                </div>
                <div className="text text-slate-100 mt-1">
                  {message.text}
                </div>
                <div className="timestamp text-xs text-slate-500 mt-1">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* Current streaming message */}
        {currentMessage && (
          <div className="message assistant streaming">
            <div className="flex items-start gap-3">
              <div className="avatar">🤖</div>
              <div className="content flex-1">
                <div className="role text-sm font-medium text-slate-400">
                  Producer
                </div>
                <div className="text text-slate-100 mt-1">
                  {currentMessage}
                  <span className="cursor-blink">▌</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={scrollRef} />
      </div>
    </div>
  );
}
```

**Conversation Store (Zustand)**

```typescript
// src/lib/stores/conversationStore.ts
import { create } from 'zustand';

interface Message {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
}

interface ConversationStore {
  messages: Message[];
  currentMessage: string;  // Streaming text
  addMessage: (message: Message) => void;
  updateCurrentMessage: (text: string) => void;
  commitCurrentMessage: () => void;
  clearConversation: () => void;
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
  messages: [],
  currentMessage: '',

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),

  updateCurrentMessage: (text) => set({ currentMessage: text }),

  commitCurrentMessage: () => set((state) => ({
    messages: [
      ...state.messages,
      {
        role: 'assistant',
        text: state.currentMessage,
        timestamp: new Date().toISOString()
      }
    ],
    currentMessage: ''
  })),

  clearConversation: () => set({ messages: [], currentMessage: '' })
}));
```

**WebSocket Hook for Audio + Text**

```typescript
// src/lib/websocket.ts
import { useEffect, useRef } from 'react';
import { useProjectStore } from '@/lib/stores/projectStore';
import { useConversationStore } from '@/lib/stores/conversationStore';
import { AudioPlayback } from '@/lib/audio';

export function useGeminiLiveConnection(sessionId: string) {
  const projectStore = useProjectStore();
  const conversationStore = useConversationStore();
  const audioPlayback = useRef(new AudioPlayback());

  useEffect(() => {
    // Single WebSocket for everything
    const ws = new WebSocket(`ws://localhost:8000/ws/live/${sessionId}`);

    ws.onopen = () => {
      console.log('Connected to Gemini Live');
    };

    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        // Audio output from Gemini Live
        case 'audio_output':
          // Play audio
          await audioPlayback.current.playAudioChunk(message.data);
          break;

        // Text transcript from Gemini Live (simultaneous with audio)
        case 'text_output':
          if (message.role === 'assistant') {
            // Update streaming text display
            conversationStore.updateCurrentMessage(message.text);
          } else if (message.role === 'user') {
            // User's speech was transcribed
            conversationStore.addMessage({
              role: 'user',
              text: message.text,
              timestamp: message.timestamp
            });
          }
          break;

        // Turn complete - commit streaming message
        case 'turn_complete':
          conversationStore.commitCurrentMessage();
          break;

        // Project brief updates
        case 'brief_updated':
          projectStore.updateBrief(message.brief);
          break;

        // Agent status
        case 'agent_thinking':
          projectStore.setCurrentAgent(message.agent_id);
          projectStore.setThinking(true);
          break;

        case 'agent_completed':
          projectStore.setThinking(false);
          break;

        // Asset ready events
        case 'strategy_complete':
        case 'images_ready':
        case 'video_ready':
        case 'audio_ready':
        case 'code_ready':
          projectStore.addAsset(message.agent_id, message.output);
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return () => {
      ws.close();
      audioPlayback.current.stop();
    };
  }, [sessionId]);

  // Return function to send audio
  return {
    sendAudio: (audioData: ArrayBuffer) => {
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.dumps({
          type: 'audio_input',
          data: btoa(String.fromCharCode(...new Uint8Array(audioData)))
        }));
      }
    }
  };
}
```

#### 4.1 Core UI Structure

**Main Layout (with Conversation Transcript)**
```
┌─────────────────────────────────────────────────────────────────────┐
│  Header: "Welcome, Creative Director"              [Show API]      │
├──────────────────┬─────────────────────┬────────────────────────────┤
│                  │                     │                            │
│  Project Brief   │   Workspace         │   Conversation             │
│  Panel           │   (Asset Display)   │   Transcript               │
│  (Left sidebar)  │                     │   (Right panel)            │
│                  │                     │                            │
│  - Campaign Plan │   - Text outputs    │  👤 User:                  │
│  - Personas      │   - Image gallery   │  "Let's get started"       │
│  - Slogans       │   - Video player    │                            │
│  - Assets        │   - Audio player    │  🤖 Producer:              │
│                  │   - Code + Preview  │  "Welcome. I'm your        │
│                  │                     │   Executive Producer..."   │
│                  │                     │                            │
│                  │                     │  👤 User:                  │
│                  │                     │  "Yes, go ahead"           │
│                  │                     │                            │
│                  │                     │  🤖 Producer:              │
│                  │                     │  "Great. To launch the..." │
│                  │                     │  [Auto-scrolling]          │
│                  │                     │                            │
├──────────────────┴─────────────────────┴────────────────────────────┤
│  Footer: Persistent Microphone (centered) + Live Transcript        │
│                   ╔═══════════╗                                     │
│                   ║    🎤     ║   "Listening..."                    │
│                   ╚═══════════╝                                     │
│            [Real-time text: "I'm analyzing the sketch..."]          │
└─────────────────────────────────────────────────────────────────────┘
```

**Responsive Behavior:**
- Desktop: 3-column layout (Brief | Workspace | Conversation)
- Tablet: Conversation panel becomes collapsible drawer
- Mobile: Single column, swipeable panels

**Project Brief Panel Component**

Real-time updating panel showing campaign state:

```typescript
interface ProjectBrief {
  projectId: string;
  productName: string;
  theme: string;
  campaignPlan?: CampaignPlan;
  personas: CustomerPersona[];
  slogans: string[];
  selectedSlogan?: string;
  heroImages: ImageAsset[];
  selectedImage?: ImageAsset;
  completedAssets: Record<string, any>;
  status: 'planning' | 'executing' | 'completed';
  version: number;
}

// Component
function ProjectBriefPanel({ brief }: { brief: ProjectBrief }) {
  return (
    <div className="project-brief-panel">
      <h2>{brief.productName}</h2>
      <div className="theme-badge">{brief.theme}</div>

      {/* Campaign Plan Section */}
      {brief.campaignPlan && (
        <section>
          <h3>Campaign Plan</h3>
          <PhaseList phases={brief.campaignPlan.phases} />
        </section>
      )}

      {/* Strategy Outputs */}
      {brief.personas.length > 0 && (
        <section>
          <h3>Target Personas</h3>
          <PersonaList personas={brief.personas} />
        </section>
      )}

      {brief.slogans.length > 0 && (
        <section>
          <h3>Slogans</h3>
          <SloganList
            slogans={brief.slogans}
            selected={brief.selectedSlogan}
          />
        </section>
      )}

      {/* Asset Tracker */}
      <section>
        <h3>Campaign Assets</h3>
        <AssetTracker assets={brief.completedAssets} />
      </section>
    </div>
  );
}
```

**WebSocket Integration for Real-Time Updates**

```typescript
function useProjec tBrief(projectId: string) {
  const [brief, setBrief] = useState<ProjectBrief | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/project/${projectId}`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'brief_updated') {
        setBrief(message.brief);

        // Highlight changed fields with animation
        message.changed_fields.forEach((field: string) => {
          highlightField(field);
        });
      }
    };

    return () => ws.close();
  }, [projectId]);

  return brief;
}
```

**Persistent Microphone Component**

Glowing, animated microphone icon (always visible):

```typescript
function PersistentMicrophone() {
  const [isListening, setIsListening] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  return (
    <div className="microphone-container">
      <div
        className={`microphone-icon ${isListening ? 'pulsing' : 'glowing'}`}
        onClick={toggleListening}
      >
        {/* Animated glow effect */}
        <div className="glow-ring" style={{ opacity: audioLevel }} />

        {/* Microphone SVG */}
        <MicrophoneIcon />

        {/* Thinking animation */}
        {isThinking && <ThinkingDots />}
      </div>

      {/* Status text */}
      <div className="mic-status">
        {isListening && "Listening..."}
        {isThinking && "Thinking..."}
        {!isListening && !isThinking && "Click to speak"}
      </div>
    </div>
  );
}
```

**CSS Animations**

```css
/* Glowing microphone (idle state) */
.microphone-icon.glowing {
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
  50% { box-shadow: 0 0 40px rgba(59, 130, 246, 0.8); }
}

/* Pulsing (listening state) */
.microphone-icon.pulsing {
  animation: pulse 1s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

/* Field highlight (when brief updates) */
.field-updated {
  animation: highlight-flash 0.8s ease-out;
}

@keyframes highlight-flash {
  0% { background-color: rgba(59, 130, 246, 0.3); }
  100% { background-color: transparent; }
}
```

**Asset Gallery View**

4-up grid for Art Director images:

```typescript
function ImageGallery({ images }: { images: ImageAsset[] }) {
  const [selectedImage, setSelectedImage] = useState<ImageAsset | null>(null);

  return (
    <div className="image-gallery grid grid-cols-2 gap-4">
      {images.map((image, index) => (
        <div
          key={image.assetId}
          className={`image-card ${selectedImage?.assetId === image.assetId ? 'selected' : ''}`}
          onClick={() => setSelectedImage(image)}
        >
          <img src={image.url} alt={image.description} />
          <div className="image-number">Image {index + 1}</div>
        </div>
      ))}
    </div>
  );
}
```

#### 4.2 Voice Interface

**Microphone Input Capture**

```typescript
class AudioCapture {
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;
  private ws: WebSocket;

  async startRecording() {
    // Request microphone access
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Create audio context for processing
    this.audioContext = new AudioContext({ sampleRate: 16000 });

    // Create media recorder
    this.mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'  // Or PCM based on Gemini requirements
    });

    // Handle audio chunks
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.sendAudioChunk(event.data);
      }
    };

    // Start recording with time slice (send chunks every 100ms)
    this.mediaRecorder.start(100);
  }

  private async sendAudioChunk(audioBlob: Blob) {
    // Convert to base64
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1];

      // Send via WebSocket
      this.ws.send(JSON.stringify({
        type: 'audio_chunk',
        data: base64,
        timestamp: Date.now()
      }));
    };
    reader.readAsDataURL(audioBlob);
  }
}
```

**Voice Activity Detection (VAD)**

```typescript
class VoiceActivityDetector {
  private analyser: AnalyserNode;
  private threshold = 0.02;  // Adjust based on testing

  constructor(stream: MediaStream) {
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    this.analyser = audioContext.createAnalyser();
    this.analyser.fftSize = 512;
    source.connect(this.analyser);
  }

  isVoiceDetected(): boolean {
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);

    // Calculate average volume
    const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
    const normalized = average / 255;

    return normalized > this.threshold;
  }

  getAudioLevel(): number {
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);
    return dataArray.reduce((a, b) => a + b) / dataArray.length / 255;
  }
}
```

**Audio Output Playback**

```typescript
class AudioPlayback {
  private audioQueue: AudioBuffer[] = [];
  private isPlaying = false;

  async playAudioChunk(base64Audio: string) {
    // Decode base64 to audio buffer
    const audioData = atob(base64Audio);
    const arrayBuffer = new Uint8Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      arrayBuffer[i] = audioData.charCodeAt(i);
    }

    // Create audio context
    const audioContext = new AudioContext();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.buffer);

    // Queue for playback
    this.audioQueue.push(audioBuffer);

    // Start playback if not already playing
    if (!this.isPlaying) {
      this.playQueue(audioContext);
    }
  }

  private async playQueue(audioContext: AudioContext) {
    this.isPlaying = true;

    while (this.audioQueue.length > 0) {
      const buffer = this.audioQueue.shift()!;
      const source = audioContext.createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext.destination);

      // Play and wait for completion
      source.start();
      await new Promise(resolve => {
        source.onended = resolve;
      });
    }

    this.isPlaying = false;
  }
}
```

**Thinking Animation**

```typescript
function ThinkingDots() {
  return (
    <div className="thinking-animation">
      <span className="dot dot-1"></span>
      <span className="dot dot-2"></span>
      <span className="dot dot-3"></span>
    </div>
  );
}
```

```css
.thinking-animation {
  display: flex;
  gap: 4px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #3b82f6;
  animation: thinking-bounce 1.4s infinite ease-in-out;
}

.dot-1 { animation-delay: 0s; }
.dot-2 { animation-delay: 0.2s; }
.dot-3 { animation-delay: 0.4s; }

@keyframes thinking-bounce {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}
```

#### 4.3 Asset Display Components

**Split-Screen Code + Preview**

```typescript
function CodePreviewSplitScreen({ code }: { code: CodeAsset }) {
  return (
    <div className="split-screen grid grid-cols-2 gap-4">
      {/* Left: Code Editor */}
      <div className="code-panel">
        <div className="tabs">
          <Tab active>HTML</Tab>
          <Tab>CSS</Tab>
          <Tab>JS</Tab>
        </div>

        <CodeEditor
          code={code.html}
          language="html"
          readonly
        />
      </div>

      {/* Right: Live Preview */}
      <div className="preview-panel">
        <div className="preview-header">
          <h3>Live Preview</h3>
        </div>

        {/* Sandboxed iframe for safe rendering */}
        <iframe
          srcDoc={generatePreviewHTML(code)}
          sandbox="allow-scripts"
          className="preview-iframe"
        />
      </div>
    </div>
  );
}

function generatePreviewHTML(code: CodeAsset): string {
  return `
    <!DOCTYPE html>
    <html>
      <head>
        <style>${code.css}</style>
      </head>
      <body>
        ${code.html}
        <script>${code.javascript}</script>
      </body>
    </html>
  `;
}
```

**Video Player with Revision History**

```typescript
function VideoPlayer({ video }: { video: VideoAsset }) {
  return (
    <div className="video-player">
      <video
        src={video.url}
        controls
        className="w-full rounded-lg"
      />

      {/* Revision indicator */}
      {video.revisionNumber > 0 && (
        <div className="revision-badge">
          Revision {video.revisionNumber}
        </div>
      )}

      {/* Revision history */}
      {video.revisionHistory.length > 0 && (
        <div className="revision-history">
          <h4>Revisions:</h4>
          <ul>
            {video.revisionHistory.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

**Audio Player for Multiple Tracks**

```typescript
function AudioTeamPlayer({ output }: { output: AudioTeamOutput }) {
  return (
    <div className="audio-team-output">
      {/* Jingle */}
      <div className="audio-track">
        <h4>Jingle</h4>
        <audio src={output.jingle.url} controls />
        <p>Duration: {output.jingle.durationSeconds}s</p>
      </div>

      {/* Podcast Ad */}
      <div className="audio-track">
        <h4>Podcast Ad (TTS)</h4>
        <audio src={output.podcastAd.url} controls />
        <p>Duration: {output.podcastAd.durationSeconds}s</p>
      </div>

      {/* Transcription */}
      <div className="transcription">
        <h4>Transcription (Chirp)</h4>
        <pre>{output.transcription.text}</pre>
        <a href={`/download/${output.transcription.assetId}`}>
          Download {output.transcription.format.toUpperCase()}
        </a>
      </div>
    </div>
  );
}
```

#### 4.4 Interaction Flow

**Welcome/Handoff Screen**

```typescript
function WelcomeScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="welcome-screen">
      <h1 className="text-4xl font-bold">Welcome, Creative Director.</h1>

      {/* Persistent glowing microphone */}
      <PersistentMicrophone />

      <p className="cta">Click the mic and say "Let's get started".</p>
    </div>
  );
}
```

**Plan Approval Interface**

After Producer presents the 5-phase plan:

```typescript
function PlanApprovalScreen({ plan }: { plan: CampaignPlan }) {
  const [approved, setApproved] = useState(false);

  return (
    <div className="plan-approval">
      <h2>Campaign Plan</h2>

      {/* Display 5 phases */}
      <div className="phases">
        {plan.phases.map((phase, i) => (
          <div key={i} className="phase-card">
            <div className="phase-number">Phase {i + 1}</div>
            <div className="agent-name">{phase.agent}</div>
            <p>{phase.taskDescription}</p>
          </div>
        ))}
      </div>

      {/* Voice approval (user says "Yes, task the Strategy Agent") */}
      <div className="approval-status">
        {!approved && "Waiting for approval..."}
        {approved && "Plan approved! Starting execution..."}
      </div>
    </div>
  );
}
```

**Real-Time Asset Streaming Display**

As agents complete work, assets stream into the workspace:

```typescript
function WorkspaceAssetStream() {
  const { projectId } = useProject();
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [assets, setAssets] = useState<Record<string, any>>({});

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/project/${projectId}`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'agent_thinking':
          setCurrentAgent(message.agent_id);
          break;

        case 'strategy_complete':
          setAssets(prev => ({ ...prev, strategy: message.output }));
          break;

        case 'images_ready':
          setAssets(prev => ({ ...prev, images: message.output }));
          break;

        case 'video_ready':
          setAssets(prev => ({ ...prev, video: message.output }));
          break;

        // ... other asset types
      }
    };

    return () => ws.close();
  }, [projectId]);

  return (
    <div className="workspace">
      {/* Show thinking animation for current agent */}
      {currentAgent && <AgentThinkingIndicator agent={currentAgent} />}

      {/* Display assets as they arrive */}
      {assets.strategy && <StrategyOutput output={assets.strategy} />}
      {assets.images && <ImageGallery images={assets.images} />}
      {assets.video && <VideoPlayer video={assets.video} />}
      {/* ... */}
    </div>
  );
}
```

**Final Summary View (Launch Party)**

```typescript
function LaunchPartyScreen({ brief }: { brief: ProjectBrief }) {
  return (
    <div className="launch-party">
      <h1 className="text-3xl font-bold mb-4">
        Campaign Complete! 🎉
      </h1>

      <p className="mb-8">
        We've gone from a sketch to a full product launch. All assets are available below.
      </p>

      {/* All Assets Grid */}
      <div className="assets-grid grid grid-cols-2 gap-6">
        <AssetCard
          title="Marketing Copy"
          agent="Strategy Agent"
          asset={brief.completedAssets.strategy}
        />

        <AssetCard
          title="Hero Image"
          agent="Art Director"
          asset={brief.completedAssets.art}
        />

        <AssetCard
          title="Social Video"
          agent="Video Producer"
          asset={brief.completedAssets.video}
        />

        <AssetCard
          title="Audio Assets"
          agent="Audio Team"
          asset={brief.completedAssets.audio}
        />

        <AssetCard
          title="Landing Page"
          agent="Web Dev"
          asset={brief.completedAssets.web}
        />
      </div>
    </div>
  );
}
```

#### 4.5 "Aura Smart Sneaker" Demo Flow Implementation

**Complete Demo Walkthrough**

```typescript
// Demo orchestration script
class AuraDemoFlow {
  private producer: ExecutiveProducer;
  private brief: ProjectBrief;

  async runDemo() {
    // 1. Welcome Screen
    await this.showWelcome();
    await this.waitForVoice("let's get started");

    // 2. Producer Introduction
    await this.producer.speak(
      "Welcome. I'm your Executive Producer. Our first project is the 'Aura' Smart Sneaker launch. I've pulled up the initial sketch."
    );
    await this.displaySketch("demo_assets/aura_sketch.png");

    // 3. Present Plan
    await this.producer.speak(
      "To start, I need to build out the core marketing strategy. Shall I proceed?"
    );
    await this.waitForVoice("yes, go ahead");

    // 4. Generate and Present Plan
    const plan = await this.producer.generatePlan(AURA_CAMPAIGN);
    await this.producer.speak(plan.description);
    await this.displayPlan(plan);

    await this.producer.speak(
      "This plan is now in your Project Brief. Shall I task the Strategy Agent to begin?"
    );
    await this.waitForVoice("yes, task the strategy agent");

    // 5. Execute Strategy Agent
    await this.executeStrategyPhase();

    // 6. Execute Art Director
    await this.executeArtPhase();

    // 7. Execute Parallel Agents (Video, Audio, Web)
    await this.executeParallelPhase();

    // 8. Final Summary
    await this.showLaunchParty();
  }

  private async executeStrategyPhase() {
    await this.producer.speak(
      "Okay, I've tasked our Strategy Agent [Gemini Pro] with analyzing the sketch."
    );

    // Show thinking animation
    this.showAgentThinking("strategy");

    // Execute agent
    const result = await this.strategyAgent.execute({
      sketchUrl: this.brief.initialSketchUrl,
      campaign: AURA_CAMPAIGN
    });

    // Present results
    await this.producer.speak(
      "It's generated three key customer personas and five potential slogans. They are on your screen now."
    );
    await this.displayStrategyOutput(result);

    // Wait for user selection
    await this.waitForVoice("I like slogan number three");
    this.brief.selectedSlogan = "Run on light";
    await this.updateBrief({ selectedSlogan: "Run on light" });
  }

  private async executeArtPhase() {
    await this.producer.speak(
      "Excellent choice. Now, I'm sending this slogan to our Art Director Agent [Imagen] to generate the hero image."
    );

    this.showAgentThinking("art_director");

    const images = await this.artDirector.execute({
      slogan: this.brief.selectedSlogan,
      theme: "Tokyo neon"
    });

    await this.displayImageGallery(images);

    await this.waitForVoice("the one on the top right is perfect");
    this.brief.selectedImage = images[1];  // Top right
    await this.updateBrief({ selectedImage: images[1] });
  }

  private async executeParallelPhase() {
    // Proactive collaboration announcement
    await this.producer.speak(
      "Got it. I've added that to the project brief. Our Video Producer Agent and Web Dev Agent have already been notified and are using that image as their style reference."
    );

    // Start parallel agents
    const [videoResult, audioResult, webResult] = await Promise.all([
      this.executeVideoWithCritique(),
      this.executeAudioWithSuggestion(),
      this.executeWebDev()
    ]);

    return { videoResult, audioResult, webResult };
  }

  private async executeVideoWithCritique() {
    // First attempt
    let video = await this.videoProducer.execute({
      imageUrl: this.brief.selectedImage.url,
      brief: this.brief
    });

    // Producer's internal critique
    const critique = await this.producer.critique(video, this.brief);

    if (critique.status === "REVISE") {
      await this.producer.speak(
        "Hmm, I'm analyzing it against our brief. The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'. I'm sending it back to the agent with instructions for a 2-second close-up."
      );

      // Revision
      video = await this.videoProducer.revise(video, critique);

      await this.producer.speak(
        "Okay, the revision is complete. Here is the new version."
      );
    }

    await this.displayVideo(video);
    return video;
  }

  private async executeAudioWithSuggestion() {
    // Proactive suggestion
    const suggestion = await this.audioTeam.generateSuggestion(this.brief);

    await this.producer.speak(
      `While they work, our Audio Agent has a proactive suggestion: based on the 'Tokyo neon' theme and the 'Run on light' slogan, it recommends an 'uplifting, futuristic, electronic beat'. Do you want to hear a sample?`
    );

    await this.waitForVoice("yes");

    const sample = await this.audioTeam.generateSample(suggestion);
    await this.playAudioSample(sample);

    // Generate full assets
    const audioAssets = await this.audioTeam.execute(this.brief);
    return audioAssets;
  }

  private async showLaunchParty() {
    await this.producer.speak(
      "And with that, our campaign is complete. We've gone from a sketch to a full product launch in just a few minutes. All assets are available in your project brief."
    );

    await this.displayFinalSummary();
  }
}
```

### Phase 5: Integration & Polish (Week 9-10)

#### 5.1 End-to-End Workflow
- Complete "Aura Smart Sneaker" demo flow
- Test all three phases (Handoff, Hub, Launch)
- Validate agent collaboration
- Test critique and revision loops
- Verify proactive suggestions

#### 5.2 "Show Me the API" Feature

**Two-Level Code Reveal**

Per design: "reveals two levels of code"

**Level 1: Gemini Live WebSocket Code**

Shows how the Producer manages streaming conversation:

```typescript
function APICodeView({ showAPI }: { showAPI: boolean }) {
  if (!showAPI) return null;

  return (
    <div className="api-code-view">
      <Tabs>
        <Tab name="Gemini Live WebSocket">
          <CodeBlock language="python">
            {`
# Executive Producer - Gemini Live Integration

async def gemini_live_session(session_id: str):
    """Bidirectional audio streaming with Gemini Live"""

    # Establish WebSocket connection to Gemini Live
    async with websockets.connect(GEMINI_LIVE_URL) as gemini_ws:

        # Authenticate
        await gemini_ws.send(json.dumps({
            "type": "auth",
            "api_key": GEMINI_API_KEY
        }))

        # Start bidirectional streaming
        async def send_audio():
            """Forward user audio to Gemini Live"""
            async for audio_chunk in user_audio_stream:
                await gemini_ws.send(audio_chunk)

        async def receive_audio():
            """Receive Producer's voice from Gemini Live"""
            async for message in gemini_ws:
                audio_chunk = message['audio']
                await websocket.send_json({
                    "type": "audio_output",
                    "data": base64.b64encode(audio_chunk)
                })

        # Run both streams concurrently
        await asyncio.gather(send_audio(), receive_audio())
            `}
          </CodeBlock>
        </Tab>

        <Tab name="Strategy Agent API">
          <CodeBlock language="python">
            {`
# Strategy Agent - Gemini Pro Vision + Pro

async def execute_strategy_agent(sketch_url: str, campaign: dict):
    """Analyze sketch and generate personas + slogans"""

    # Step 1: Vision analysis of sketch
    vision_prompt = f"""
    Analyze this product sketch: {sketch_url}

    Extract:
    - Visual theme and aesthetics
    - Key product features visible
    - Target audience implications
    """

    vision_result = await gemini_pro_vision.generate_content(
        prompt=vision_prompt,
        image=sketch_url
    )

    # Step 2: Strategy generation
    strategy_prompt = f"""
    Product: {campaign['product_name']}
    Visual Analysis: {vision_result.text}
    Theme: {campaign['theme']}

    Generate:
    1. Exactly 3 customer personas with demographics, pain points, motivations
    2. Exactly 5 catchy product slogans
    3. Market analysis summary
    """

    strategy_result = await gemini_pro.generate_content(
        prompt=strategy_prompt
    )

    return StrategyAgentOutput.parse(strategy_result.text)
            `}
          </CodeBlock>
        </Tab>

        <Tab name="Art Director API">
          <CodeBlock language="python">
            {`
# Art Director - Imagen 3

async def execute_art_director(slogan: str, theme: str):
    """Generate 4 hero images"""

    prompt = f"""
    Create a photorealistic hero image for a smart sneaker campaign.

    Slogan: "{slogan}"
    Theme: {theme}
    Style: Urban, futuristic, neon-lit cityscape
    Key feature: Glowing sole on the sneaker
    Setting: Tokyo night street scene
    """

    # Generate 4 variations
    images = []
    for i in range(4):
        response = await imagen_client.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
            model="imagen-3.0-generate-001"
        )

        image_url = upload_to_gcs(response.images[0])
        images.append(ImageAsset(
            asset_id=generate_id(),
            url=image_url,
            description=f"Hero image variation {i+1}"
        ))

    return ArtDirectorOutput(images=images)
            `}
          </CodeBlock>
        </Tab>

        <Tab name="Video Producer API">
          <CodeBlock language="python">
            {`
# Video Producer - Veo 2

async def execute_video_producer(image_url: str, brief: dict):
    """Generate social media video"""

    prompt = f"""
    Create a 15-second social media video based on this hero image: {image_url}

    Campaign: {brief['product_name']}
    Theme: {brief['theme']}
    Required: 2-second close-up of glowing sneaker sole
    Setting: Tokyo cityscape at night
    Movement: Dynamic camera movement, runner in motion
    """

    response = await veo_client.generate_video(
        prompt=prompt,
        reference_image=image_url,
        duration_seconds=15,
        model="veo-2.0"
    )

    video_url = upload_to_gcs(response.video)

    return VideoProducerOutput(
        video=VideoAsset(
            asset_id=generate_id(),
            url=video_url,
            duration_seconds=15
        )
    )
            `}
          </CodeBlock>
        </Tab>

        <Tab name="Audio Team API">
          <CodeBlock language="python">
            {`
# Audio Team - Lyria + Chirp

async def execute_audio_team(brief: dict):
    """Generate jingle, podcast ad, and transcription"""

    # 1. Jingle (Lyria Music Generation)
    jingle_prompt = f"""
    Compose an uplifting, futuristic, electronic beat jingle.
    Theme: {brief['theme']}
    Mood: Energetic, inspiring, urban
    Duration: 10 seconds
    """

    jingle_response = await lyria_music.generate(
        prompt=jingle_prompt,
        duration_seconds=10
    )
    jingle_url = upload_to_gcs(jingle_response.audio)

    # 2. Podcast Ad (Lyria TTS)
    ad_script = f"Introducing {brief['product_name']}: {brief['slogan']}. The future of urban running."

    tts_response = await lyria_tts.synthesize(
        text=ad_script,
        voice="professional_female"
    )
    ad_url = upload_to_gcs(tts_response.audio)

    # 3. Transcription (Chirp)
    transcription = await chirp.transcribe(
        audio_url=ad_url,
        format="srt"
    )

    return AudioTeamOutput(
        jingle=AudioAsset(asset_id=gen_id(), url=jingle_url, duration_seconds=10),
        podcast_ad=AudioAsset(asset_id=gen_id(), url=ad_url, duration_seconds=8),
        transcription=TranscriptionAsset(asset_id=gen_id(), text=transcription.text)
    )
            `}
          </CodeBlock>
        </Tab>

        <Tab name="Web Dev API">
          <CodeBlock language="python">
            {`
# Web Dev Agent - Gemini Code Assist

async def execute_web_dev(image_url: str, slogan: str):
    """Generate landing page code"""

    prompt = f"""
    Generate a beautiful "Coming Soon" landing page.

    Requirements:
    - Hero image: {image_url}
    - Slogan: "{slogan}"
    - Countdown timer to launch date
    - Email signup form
    - Neon blue and purple color scheme (Tokyo neon theme)
    - Responsive design
    - Modern, futuristic aesthetic

    Generate complete HTML, CSS, and JavaScript.
    """

    response = await gemini_code_assist.generate_code(
        prompt=prompt,
        language="html"
    )

    # Parse response into components
    code = parse_code_response(response.text)

    return WebDevOutput(
        code=CodeAsset(
            asset_id=generate_id(),
            html=code['html'],
            css=code['css'],
            javascript=code['javascript']
        )
    )
            `}
          </CodeBlock>
        </Tab>

        <Tab name="Critique System">
          <CodeBlock language="python">
            {`
# Producer's Internal Critique Loop

async def critique_video(video: VideoAsset, brief: ProjectBrief) -> CritiqueResult:
    """Producer evaluates video against brief"""

    critique_prompt = f"""
    You are the Executive Producer evaluating agent work.

    Project Brief:
    - Product: {brief.product_name}
    - Theme: {brief.theme}
    - Key features: {brief.key_features}
    - Required: Glowing sole close-up

    Video URL: {video.url}
    Duration: {video.duration_seconds}s

    Evaluate:
    1. Does it match the Tokyo neon theme?
    2. Does it show the glowing sole clearly?
    3. Is the quality professional?

    If issues found, provide specific revision instructions.
    Otherwise, return PASS.
    """

    result = await gemini_pro.generate_content(critique_prompt)

    return CritiqueResult.parse(result.text)


# Example output:
# "The 'Tokyo neon' theme is strong, but it doesn't clearly show
#  the 'glowing sole'. Send back with instructions for a 2-second close-up."
            `}
          </CodeBlock>
        </Tab>
      </Tabs>
    </div>
  );
}
```

**Toggle Implementation**

```typescript
function APIToggle() {
  const [showAPI, setShowAPI] = useState(false);

  return (
    <>
      <button
        className="api-toggle-button"
        onClick={() => setShowAPI(!showAPI)}
      >
        {showAPI ? "Hide API Code" : "Show Me the API"}
      </button>

      <APICodeView showAPI={showAPI} />
    </>
  );
}
```

#### 5.3 Error Handling & Resilience
- API failure recovery
- Agent timeout handling
- WebSocket reconnection logic
- Graceful degradation
- User-friendly error messages

#### 5.4 Performance Optimization
- Asset caching strategy
- Streaming optimizations
- Parallel agent execution
- Resource pooling
- Bundle size optimization

#### 5.5 Testing & Documentation
- Unit tests for all agents
- Integration tests for workflows
- End-to-end tests for demo flow
- API documentation
- User guide for voice commands

## Key Technical Challenges

### 1. Real-time Conversation Coordination
**Challenge**: Managing bidirectional streaming audio while coordinating background agent tasks
**Solution**:
- Separate audio stream thread from agent orchestration
- Use event-driven architecture for agent status updates
- Queue voice responses while waiting for agent outputs

### 2. Context Sharing Across Agents
**Challenge**: Agents need to access and update shared project brief context
**Solution**:
- Centralized project brief store (Redis)
- Event-based context updates
- Immutable context snapshots per agent task

### 3. Internal Critique Loop
**Challenge**: Producer must autonomously evaluate agent outputs against brief
**Solution**:
- Create critique prompt templates
- Implement quality scoring system
- Define revision thresholds and max retry limits

### 4. Proactive Collaboration
**Challenge**: Agents suggesting and starting work without explicit user commands
**Solution**:
- Rule-based triggers (e.g., "when hero image selected, notify video/web agents")
- Agent subscription system to project brief updates
- Permission levels (auto-start vs. user-approval required)

### 5. Live Preview Rendering
**Challenge**: Rendering user-generated code safely in the browser
**Solution**:
- Sandboxed iframe for code execution
- Content Security Policy restrictions
- Input sanitization
- Resource limits

## Development Approach

### Iteration Strategy
1. **Vertical Slice First**: Implement minimal end-to-end flow with one agent
2. **Progressive Enhancement**: Add agents one at a time with full integration
3. **Parallel Development**: Frontend and backend can develop against mocks initially
4. **Integration Points**: Define clear API contracts between components

### Testing Strategy
- **Unit Tests**: pytest for all agent logic, API clients, utilities
- **Integration Tests**: pytest-asyncio for agent orchestration, WebSocket communication
- **Mocking**: pytest-mock and fakeredis for Redis operations
- **E2E Tests**: Complete user flows using Playwright
- **Load Testing**: locust for concurrent users, API rate limits
- **Coverage**: pytest-cov with minimum 80% coverage target

### Deployment Considerations
- **Environment Variables**: API keys, service endpoints
- **Secrets Management**: Use Google Secret Manager or similar
- **Scaling**: Stateless FastAPI services (multiple instances), Redis for shared state
- **Redis Persistence**:
  - Enable both AOF (append-only file) and RDB snapshots
  - Configure save intervals based on data criticality
  - Set up Redis backup strategy for project data
  - Consider Redis Cluster for high availability
- **Monitoring**:
  - Track API usage, response times, error rates
  - Monitor Redis memory usage and eviction policies
  - Set up alerts for Redis connection failures
  - Log Celery task failures and retries
- **Cost Management**: Monitor token usage across all Google AI services
- **Process Management**: Use supervisor or systemd for Celery workers and FastAPI

## Deliverables by Phase

**Phase 1**: Backend infrastructure + API clients + dev environment
**Phase 2**: All 5 agents functional + orchestration system
**Phase 3**: Gemini Live integration + Producer logic
**Phase 4**: Complete UI with voice interface + asset displays
**Phase 5**: Polished demo + documentation + "Show API" feature

## Success Criteria

The implementation is complete when:
1. User can complete the full "Aura Smart Sneaker" campaign via voice
2. All 5 specialist agents generate appropriate outputs
3. Producer demonstrates autonomous planning, critique, and revision
4. Agents show proactive collaboration (parallel work, context sharing)
5. "Show Me the API" reveals the underlying technical implementation
6. System handles errors gracefully with user-friendly messages

## Next Steps

To begin implementation:

### 1. Python Environment Setup (Python 3.13+ with uv)

```bash
# Install uv (if not already installed)
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv

# Create project directory
mkdir ai-agency && cd ai-agency
mkdir backend frontend

# Initialize Python project with uv
cd backend
uv venv --python 3.13  # Creates .venv with Python 3.13
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Initialize pyproject.toml
uv init
```

### 2. Install Core Dependencies

**Backend (pyproject.toml)**
```toml
[project]
name = "ai-agency"
version = "0.1.0"
description = "AI Agency - Multi-agent creative campaign system"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "websockets>=12.0",
    "redis>=5.0.1",
    "celery>=5.3.6",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.1.0",
    # Google AI SDKs
    "google-cloud-aiplatform>=1.42.0",
    "google-generativeai>=0.3.2",
    # Audio processing
    "pydub>=0.25.1",
    "soundfile>=0.12.1",
    "numpy>=1.26.3",
    # Cloud storage
    "google-cloud-storage>=2.14.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.3",
    "pytest-mock>=3.12.0",
    "fakeredis>=2.21.0",
    "black>=24.1.1",
    "ruff>=0.2.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.black]
line-length = 100
target-version = ["py313"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.mypy]
python_version = "3.13"
strict = true
```

**Install dependencies with uv**
```bash
# Sync dependencies from pyproject.toml (creates uv.lock)
uv sync

# Install with dev dependencies
uv sync --dev

# Or install in editable mode
uv pip install -e ".[dev]"

# Add a new package (updates pyproject.toml and uv.lock)
uv add fastapi

# Add a dev dependency
uv add --dev pytest

# Remove a package
uv remove <package-name>

# Update all dependencies
uv lock --upgrade

# Run commands in the virtual environment
uv run uvicorn app.main:app --reload
uv run pytest
uv run black .
```

**uv Workflow Benefits**
- **Speed**: 10-100x faster installs than pip/Poetry
- **Lock File**: `uv.lock` ensures reproducible builds across environments
- **Python Management**: Auto-downloads correct Python version if not available
- **Drop-in Replacement**: Works with existing `pip` and `pyproject.toml` workflows
- **Unified Tool**: Replaces pip, pip-tools, Poetry, virtualenv, pipx

### 3. Google AI API Credentials

- Create Google Cloud project
- Enable APIs:
  - Vertex AI API (for Gemini, Imagen, Veo)
  - Generative AI API
- Create service account and download credentials JSON
- Set environment variable: `GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json`

### 4. Redis Setup

**Local Development:**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest --appendonly yes

# Or install locally
brew install redis  # macOS
sudo apt-get install redis  # Ubuntu
```

**Redis Configuration (redis.conf):**
```
# Enable persistence
appendonly yes
appendfilename "appendonly.aof"

# RDB snapshots
save 900 1
save 300 10
save 60 10000
```

### 5. Frontend Setup

**Initialize Next.js 14+ with App Router**
```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app --use-npm
# When prompted:
# - TypeScript: Yes
# - ESLint: Yes
# - Tailwind CSS: Yes
# - src/ directory: Yes
# - App Router: Yes
# - Turbopack: Yes
# - Import alias: @/*
```

**Install Additional Dependencies**
```bash
# UI Components (shadcn/ui)
npx shadcn-ui@latest init

# State Management
npm install zustand

# WebSocket
npm install ws
npm install @types/ws --save-dev

# Audio Processing
npm install @types/audioworklet --save-dev

# Utilities
npm install clsx tailwind-merge
npm install class-variance-authority
```

**package.json (key dependencies)**
```json
{
  "dependencies": {
    "next": "^14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "zustand": "^4.5.0",
    "ws": "^8.16.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "class-variance-authority": "^0.7.0",
    "@radix-ui/react-*": "latest"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "@types/ws": "^8.5.0",
    "@types/audioworklet": "^0.0.50",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "eslint": "^8",
    "eslint-config-next": "14.1.0"
  }
}
```

### 6. Project Structure

```
ai-agency/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── strategy.py
│   │   │   ├── art_director.py
│   │   │   ├── video_producer.py
│   │   │   ├── audio_team.py
│   │   │   └── web_dev.py
│   │   ├── producer/
│   │   │   ├── __init__.py
│   │   │   ├── executive_producer.py
│   │   │   ├── planner.py
│   │   │   └── critique.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── gemini_live.py
│   │   │   ├── redis_client.py
│   │   │   └── storage.py
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── brief.py
│   │       └── assets.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_agents/
│   │   ├── test_producer/
│   │   └── test_services/
│   ├── scripts/
│   │   └── seed_demo_data.py
│   ├── demo_assets/
│   │   └── aura_sketch.png
│   ├── pyproject.toml
│   ├── uv.lock (auto-generated by uv)
│   ├── .env.example
│   ├── .python-version (3.13)
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── globals.css
│   │   │   └── api/
│   │   │       └── ws/
│   │   │           └── route.ts
│   │   ├── components/
│   │   │   ├── ui/ (shadcn/ui components)
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   └── tabs.tsx
│   │   │   ├── PersistentMicrophone.tsx
│   │   │   ├── ProjectBriefPanel.tsx
│   │   │   ├── ImageGallery.tsx
│   │   │   ├── VideoPlayer.tsx
│   │   │   ├── AudioPlayer.tsx
│   │   │   ├── CodePreview.tsx
│   │   │   └── ThinkingAnimation.tsx
│   │   ├── lib/
│   │   │   ├── audio.ts
│   │   │   ├── websocket.ts
│   │   │   ├── stores/
│   │   │   │   └── projectStore.ts (Zustand)
│   │   │   └── utils.ts
│   │   └── types/
│   │       ├── brief.ts
│   │       └── assets.ts
│   ├── public/
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── components.json (shadcn/ui config)
│   └── README.md
├── .gitignore
└── README.md
```

**Recommended .gitignore additions for uv**
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
.venv/
venv/
ENV/
env/

# uv
# Note: uv.lock should be committed for reproducible builds
# .python-version can be committed or ignored based on preference

# Environment variables
.env
.env.local

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# Build
dist/
build/
*.egg-info/
```

### 7. Start with Phase 1.1

**Quick Start Commands**
```bash
# Backend setup
cd backend
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e ".[dev]"

# Set up linting and formatting
uv run black .
uv run ruff check .
uv run mypy --install-types

# Create environment file
cp .env.example .env
# Edit .env with your API keys

# Initialize Git repository
git init
git add .
git commit -m "Initial commit"

# Set up pre-commit hooks
uv run pre-commit install
```

**Development Workflow**
```bash
# Run FastAPI server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest -v

# Format code
uv run black .

# Lint code
uv run ruff check . --fix

# Type check
uv run mypy app/
```

- Create first vertical slice: Strategy Agent
- Set up Redis connection
- Create demo seed data script

### 8. Critical Research Tasks Before Implementation

- [ ] **Gemini Live API Audio Format**: Determine exact audio encoding, sample rate, and streaming protocol
- [ ] **Chirp API Availability**: Verify if Chirp transcription API is accessible or use alternative (e.g., Google Speech-to-Text)
- [ ] **Lyria API Access**: Confirm access to Lyria music generation and TTS
- [ ] **Veo 2 API**: Verify video generation API availability and parameters
