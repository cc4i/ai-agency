# AI Agency Architecture Diagrams

This document provides comprehensive Mermaid diagrams visualizing the AI Agency system architecture, data flow, and component relationships.

**Generated:** 2025-01-04
**Repository:** AI Agency - Multi-Agent Creative Campaign System

---

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend (Next.js)"
        UI[User Interface<br/>React Components]
        WS_CLIENT[WebSocket Client<br/>useWebSocket hook]
        STORE[State Management<br/>Zustand Store]
        MIC[Microphone Interface<br/>Audio Capture]

        UI --> STORE
        UI --> MIC
        WS_CLIENT --> STORE
        MIC --> WS_CLIENT
    end

    subgraph "Backend (FastAPI)"
        API[FastAPI Server<br/>:8000]
        WS_SERVER[WebSocket Handler<br/>/ws/adk]
        ADK[Google ADK Runner<br/>Executive Producer Agent]
        ORCHESTRATOR[Agent Orchestrator<br/>Task Delegation]

        API --> WS_SERVER
        WS_SERVER --> ADK
        ADK --> ORCHESTRATOR
    end

    subgraph "Agents (Python)"
        STRATEGY[Strategy Agent<br/>Personas & Slogans]
        ART[Art Director<br/>Hero Images]
        VIDEO[Video Producer<br/>Social Media Clips]
        AUDIO[Audio Team<br/>Jingles & Podcasts]
        WEBDEV[Web Dev<br/>Landing Pages]

        ORCHESTRATOR --> STRATEGY
        ORCHESTRATOR --> ART
        ORCHESTRATOR --> VIDEO
        ORCHESTRATOR --> AUDIO
        ORCHESTRATOR --> WEBDEV
    end

    subgraph "State Storage"
        REDIS[(Redis<br/>Project Briefs<br/>Assets<br/>Agent Status)]
        PUBSUB[Redis Pub/Sub<br/>Event Notifications]
    end

    subgraph "Google AI Services"
        GEMINI_LIVE[Gemini Live<br/>Voice Conversation]
        GEMINI_PRO[Gemini Pro<br/>Text Generation]
        IMAGEN[Imagen 3<br/>Image Generation]
        VEO[Veo 2<br/>Video Generation]
        LYRIA[Lyria<br/>Audio/Music]
        SPEECH_V2[Speech-to-Text v2<br/>Chirp Model]
        CODE_ASSIST[Code Assist<br/>Code Generation]
    end

    WS_CLIENT <-->|Bidirectional Audio<br/>+ JSON Messages| WS_SERVER
    ADK <-->|Streaming Audio| GEMINI_LIVE

    STRATEGY --> GEMINI_PRO
    ART --> IMAGEN
    VIDEO --> VEO
    AUDIO --> LYRIA
    AUDIO --> SPEECH_V2
    WEBDEV --> CODE_ASSIST

    ORCHESTRATOR --> REDIS
    ORCHESTRATOR --> PUBSUB
    WS_SERVER --> REDIS

    style UI fill:#2563eb,color:#fff
    style ADK fill:#dc2626,color:#fff
    style REDIS fill:#dc2626,color:#fff
    style GEMINI_LIVE fill:#10b981,color:#fff
```

---

## 2. Agent Workflow & Communication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant WebSocket
    participant Producer as Executive Producer<br/>(Gemini Live + ADK)
    participant Orchestrator
    participant Agent as Specialist Agent
    participant GoogleAI as Google AI API
    participant Redis

    User->>Frontend: Speak "Create campaign for Aura sneakers"
    Frontend->>WebSocket: Send audio_input (base64 PCM)
    WebSocket->>Producer: Forward audio to Gemini Live
    Producer->>Producer: Understand intent via Gemini Live

    Producer->>Producer: Generate execution plan
    Producer->>WebSocket: Announce plan to user
    WebSocket->>Frontend: Display plan (producer_announcement)

    User->>Frontend: Approve "Yes, proceed"
    Frontend->>WebSocket: Send audio_input
    WebSocket->>Producer: Approval received

    Producer->>Producer: Call update_project_brief tool
    Producer->>Redis: Save project brief

    Producer->>Producer: Call create_campaign_strategy tool
    Producer->>Orchestrator: Execute strategy agent
    Orchestrator->>Agent: Run with task & context
    Agent->>GoogleAI: Generate personas (Gemini Pro)
    GoogleAI-->>Agent: Return personas
    Agent->>GoogleAI: Generate slogans (Gemini Pro)
    GoogleAI-->>Agent: Return slogans
    Agent->>Orchestrator: Return StrategyAgentOutput

    Orchestrator->>Orchestrator: Run critique loop
    alt Critique PASS
        Orchestrator->>Redis: Save strategy assets
        Orchestrator->>WebSocket: Broadcast asset_added
        WebSocket->>Frontend: Display slogans & personas
        Orchestrator-->>Producer: Return success
    else Critique FAIL
        Orchestrator->>Agent: Regenerate with feedback
    end

    Producer->>Producer: Present results to user via Gemini Live
    Producer->>WebSocket: Stream audio response
    WebSocket->>Frontend: Play audio (producer speaking)

    User->>Frontend: Select "Slogan 3"
    Frontend->>WebSocket: Send selection
    WebSocket->>Producer: Update brief with selected_slogan
    Producer->>Redis: Update project brief

    Producer->>Producer: Call generate_hero_images tool
    Producer->>Orchestrator: Execute art_director agent
    Orchestrator->>Agent: Run with slogan context
    Agent->>GoogleAI: Generate 4 images (Imagen)
    GoogleAI-->>Agent: Return image URLs
    Agent->>Orchestrator: Return ArtDirectorOutput
    Orchestrator->>Redis: Save image assets
    Orchestrator->>WebSocket: Broadcast asset_added
    WebSocket->>Frontend: Display hero images

    Note over Producer,Agent: Process continues for Video, Audio, Web Dev agents...
```

---

## 3. WebSocket Communication Protocol

```mermaid
graph LR
    subgraph "Frontend → Backend Messages"
        F1[audio_input<br/>base64 PCM audio]
        F2[update_brief<br/>field updates]
        F3[turn_complete<br/>VAD signal]
    end

    subgraph "Backend → Frontend Messages"
        B1[audio_output<br/>base64 PCM audio]
        B2[text_output<br/>transcript fragments]
        B3[turn_complete<br/>end of turn]
        B4[brief_init<br/>initial project data]
        B5[brief_update<br/>changed fields]
        B6[asset_added<br/>new agent output]
        B7[agent_status<br/>thinking/complete/error]
        B8[producer_announcement<br/>info/success/error]
        B9[interrupted<br/>turn cancelled]
        B10[error<br/>error details]
    end

    F1 --> WS[WebSocket<br/>/ws/adk/:session/:project]
    F2 --> WS
    F3 --> WS

    WS --> B1
    WS --> B2
    WS --> B3
    WS --> B4
    WS --> B5
    WS --> B6
    WS --> B7
    WS --> B8
    WS --> B9
    WS --> B10

    style WS fill:#8b5cf6,color:#fff
    style F1 fill:#3b82f6,color:#fff
    style F2 fill:#3b82f6,color:#fff
    style F3 fill:#3b82f6,color:#fff
```

---

## 4. Data Models & Redis Schema

```mermaid
erDiagram
    ProjectBrief ||--o{ Asset : contains
    ProjectBrief {
        string project_id PK
        string product_name
        string product_category
        string theme
        string brand_tone
        string target_market
        list key_features
        string selected_slogan
        string selected_image_url
        datetime created_at
        datetime updated_at
    }

    Asset ||--|| ImageAsset : is
    Asset ||--|| VideoAsset : is
    Asset ||--|| AudioAsset : is
    Asset ||--|| CodeAsset : is
    Asset {
        string asset_id PK
        string asset_type
        string agent_id FK
        datetime created_at
    }

    ImageAsset {
        string asset_id PK
        string url
        string description
        dict generation_params
    }

    VideoAsset {
        string asset_id PK
        string url
        int duration_seconds
        string description
        dict generation_params
    }

    AudioAsset {
        string asset_id PK
        string url
        int duration_seconds
        string format
        string script
    }

    CodeAsset {
        string asset_id PK
        string html
        string css
        string javascript
        string preview_url
    }

    AgentStatus ||--|| ProjectBrief : tracks
    AgentStatus {
        string agent_id PK
        string status
        string current_task
        datetime last_updated
    }

    ConversationMessage }o--|| Session : belongs_to
    ConversationMessage {
        string role
        string text
        datetime timestamp
        bool is_partial
    }

    Session {
        string session_id PK
        string project_id FK
        string user_id
        datetime created_at
    }
```

**Redis Key Structure:**
```
project:{project_id}:brief             → ProjectBrief JSON
project:{project_id}:assets            → List[asset_id]
asset:{asset_id}                       → Asset JSON
agent:{agent_id}:status                → AgentStatus JSON
session:{session_id}                   → Session metadata
session:{session_id}:conversation      → List[ConversationMessage]
pubsub:agent_events                    → Pub/Sub channel
```

---

## 5. Frontend Component Hierarchy

```mermaid
graph TD
    APP[app/page.tsx<br/>Main Application]

    APP --> WORKSPACE[WorkspaceClient<br/>Client-side container]

    WORKSPACE --> LEFT[Left Panel]
    WORKSPACE --> CENTER[Center Panel]
    WORKSPACE --> RIGHT[Right Panel]

    LEFT --> BRIEF[ProjectBriefPanel<br/>Brief display & updates]

    CENTER --> STATUS[AgentStatusBar<br/>5 agent status indicators]
    CENTER --> ASSETS[AssetDisplay<br/>Generated content]
    CENTER --> MIC[MicrophoneInterface<br/>Audio controls]
    CENTER --> ANNOUNCEMENTS[ProducerAnnouncements<br/>Toast notifications]

    ASSETS --> STRATEGY_VIEW[StrategyAssets<br/>Personas & Slogans]
    ASSETS --> ART_VIEW[ArtDirectorAssets<br/>Hero Images]
    ASSETS --> VIDEO_VIEW[VideoProducerAssets<br/>Social Videos]
    ASSETS --> AUDIO_VIEW[AudioTeamAssets<br/>Jingles & Podcasts]
    ASSETS --> WEB_VIEW[WebDevAssets<br/>Landing Page iframe]

    RIGHT --> TRANSCRIPT[TranscriptDisplay<br/>Conversation history<br/>Collapsible]

    WORKSPACE --> HOOKS[Custom Hooks]
    HOOKS --> WS_HOOK[useWebSocket<br/>Bidirectional communication]
    HOOKS --> MIC_HOOK[useMicrophone<br/>Audio capture]

    WORKSPACE --> STORE_CONN[Zustand Store Connection]
    STORE_CONN --> STORE[useProjectStore<br/>Global state]

    STORE --> STATE_BRIEF[brief: ProjectBrief]
    STORE --> STATE_ASSETS[assets: Record<agent, Asset[]>]
    STORE --> STATE_AGENT[agentStatus: Record<agent, Status>]
    STORE --> STATE_TRANSCRIPT[transcript: Message[]]
    STORE --> STATE_ANNOUNCE[announcements: Announcement[]]
    STORE --> STATE_CONN[connected: boolean]
    STORE --> STATE_SPEAKING[producerSpeaking: boolean]

    style APP fill:#2563eb,color:#fff
    style WORKSPACE fill:#7c3aed,color:#fff
    style STORE fill:#dc2626,color:#fff
```

---

## 6. End-to-End Request Flow (Example: Generate Hero Images)

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Browser
    participant MicInterface as MicrophoneInterface
    participant WSHook as useWebSocket
    participant Backend as FastAPI Server
    participant ADKRunner as ADK Runner
    participant Tool as generate_hero_images
    participant Orchestrator
    participant Agent as ArtDirectorAgent
    participant Imagen as Imagen API
    participant Redis
    participant Frontend as Zustand Store
    participant UI as AssetDisplay

    User->>Browser: Click microphone
    Browser->>MicInterface: Start recording
    MicInterface->>WSHook: sendAudio(PCM buffer)
    WSHook->>Backend: WebSocket: audio_input (base64)
    Backend->>ADKRunner: Stream to Gemini Live
    ADKRunner->>ADKRunner: Parse intent: "generate hero images"
    ADKRunner->>Tool: Call generate_hero_images(product, slogan, theme)

    Tool->>Redis: Fetch project brief
    Redis-->>Tool: Return brief data

    Tool->>Backend: Broadcast agent_status(art_director, "thinking")
    Backend->>Frontend: Update agentStatus.art_director
    Frontend->>UI: Show "thinking" indicator

    Tool->>Orchestrator: execute_agent(art_director, task, context)
    Orchestrator->>Agent: execute(task, context)

    loop For each of 4 images
        Agent->>Imagen: POST /generate (prompt, style, aspect_ratio)
        Imagen-->>Agent: Return image data URI
        Agent->>Agent: Create ImageAsset
    end

    Agent-->>Orchestrator: Return ArtDirectorOutput {images: [4]}

    Orchestrator->>Orchestrator: critique(output, brief)
    alt Critique Score >= 0.7
        Orchestrator->>Redis: Save assets
        Orchestrator-->>Tool: Return output
    else Critique Score < 0.7
        Orchestrator->>Agent: Regenerate with feedback
        Note over Agent,Imagen: Retry with improved prompts
    end

    Tool->>Backend: Broadcast asset_added(art_director, images, data)
    Backend->>Frontend: Add to assets.art_director
    Frontend->>UI: Render ArtDirectorAssets component
    UI->>Browser: Display 4 hero images in grid

    Tool->>Backend: Broadcast agent_status(art_director, "complete")
    Backend->>Frontend: Update agentStatus.art_director
    Frontend->>UI: Show checkmark

    Tool-->>ADKRunner: Return tool result {success: true}
    ADKRunner->>ADKRunner: Generate response via Gemini Live
    ADKRunner->>Backend: Stream audio_output (PCM)
    Backend->>WSHook: WebSocket: audio_output (base64)
    WSHook->>WSHook: Decode & queue AudioBuffer
    WSHook->>Browser: Play audio "I've generated 4 hero images..."

    User->>UI: Click on image 2
    UI->>WSHook: sendMessage({type: update_brief, selected_image_url})
    WSHook->>Backend: WebSocket: update_brief
    Backend->>Redis: Update project brief
    Backend->>Frontend: brief_update({selected_image_url})
    Frontend->>UI: Highlight selected image
```

---

## 7. Agent Execution Pipeline

```mermaid
graph TB
    START[Producer calls tool<br/>e.g. generate_hero_images] --> FETCH[Fetch Project Brief<br/>from Redis]

    FETCH --> STATUS1[Broadcast agent_status<br/>thinking]

    STATUS1 --> ORCHESTRATE[Orchestrator.execute_agent<br/>agent_id, task, context]

    ORCHESTRATE --> AGENT_INIT[Agent.execute<br/>with_critique=True]

    AGENT_INIT --> GENERATE[Agent-specific generation<br/>Strategy: Gemini Pro<br/>Art: Imagen<br/>Video: Veo<br/>Audio: Lyria<br/>Web: Code Assist]

    GENERATE --> OUTPUT[Create typed output<br/>StrategyAgentOutput<br/>ArtDirectorOutput<br/>etc.]

    OUTPUT --> CRITIQUE{Critique Loop<br/>Score >= 0.7?}

    CRITIQUE -->|FAIL| FEEDBACK[Generate feedback<br/>via Gemini Pro]
    FEEDBACK --> RETRY{Retry count<br/>< 3?}
    RETRY -->|Yes| GENERATE
    RETRY -->|No| FAIL[Return with issues]

    CRITIQUE -->|PASS| SAVE[Save to Redis<br/>asset:{asset_id}<br/>project:{id}:assets]

    SAVE --> BROADCAST[Broadcast asset_added<br/>via WebSocket]

    BROADCAST --> STATUS2[Broadcast agent_status<br/>complete]

    STATUS2 --> RETURN[Return to Producer<br/>Tool result]

    RETURN --> PRESENT[Producer presents<br/>via Gemini Live]

    FAIL --> STATUS_ERR[Broadcast agent_status<br/>error]
    STATUS_ERR --> RETURN

    style START fill:#2563eb,color:#fff
    style CRITIQUE fill:#dc2626,color:#fff
    style BROADCAST fill:#10b981,color:#fff
    style PRESENT fill:#8b5cf6,color:#fff
```

---

## 8. Audio Processing Pipeline (Frontend)

```mermaid
graph LR
    subgraph "Audio Input"
        MIC[Microphone] --> CAPTURE[MediaRecorder<br/>48kHz mono]
        CAPTURE --> DOWNSAMPLE[Downsample to 16kHz<br/>via AudioContext]
        DOWNSAMPLE --> PCM16[Convert to PCM16<br/>Little-endian]
        PCM16 --> BASE64_IN[Base64 encode]
        BASE64_IN --> WS_SEND[WebSocket send<br/>audio_input]
    end

    subgraph "Audio Output"
        WS_RECV[WebSocket receive<br/>audio_output] --> BASE64_OUT[Base64 decode]
        BASE64_OUT --> PCM_DECODE[PCM16 decode<br/>Little-endian]
        PCM_DECODE --> FLOAT32[Convert to Float32<br/>-1.0 to 1.0]
        FLOAT32 --> BUFFER[Create AudioBuffer<br/>24kHz mono]
        BUFFER --> QUEUE[Add to queue]

        QUEUE --> PROCESSING{Audio processing<br/>enabled?}
        PROCESSING -->|Yes| FILTER[BiquadFilter<br/>Lowpass 8kHz]
        FILTER --> COMPRESS[DynamicsCompressor<br/>-18dB threshold]
        COMPRESS --> SPEAKERS[AudioContext.destination<br/>Play audio]

        PROCESSING -->|No| SPEAKERS
    end

    SPEAKERS --> NEXT{Queue has<br/>more buffers?}
    NEXT -->|Yes| QUEUE
    NEXT -->|No| DONE[Set producerSpeaking<br/>= false]

    style MIC fill:#10b981,color:#fff
    style SPEAKERS fill:#3b82f6,color:#fff
    style PROCESSING fill:#f59e0b,color:#fff
```

---

## 9. Memory Bank Migration (Planned)

```mermaid
graph TB
    subgraph "Current: Redis-based"
        REDIS_SAVE[Manual save_transcript<br/>to Redis list]
        REDIS_GET[get_conversation_history<br/>offset + limit]
        REDIS_STORE[(Redis<br/>session:*:conversation)]

        REDIS_SAVE --> REDIS_STORE
        REDIS_GET --> REDIS_STORE
    end

    subgraph "Future: Vertex AI Memory Bank"
        CALLBACK[after_agent_callback<br/>Auto-save after each turn]
        PRELOAD[PreloadMemoryTool<br/>Auto-retrieve at start]
        LOAD_MEM[load_memory<br/>Manual search]
        MEMORY_BANK[(Vertex AI<br/>Memory Bank)]

        CALLBACK --> SAVE_API[memory_service<br/>.add_session_to_memory]
        SAVE_API --> MEMORY_BANK

        PRELOAD --> SEARCH_API[memory_service<br/>.search_memory]
        LOAD_MEM --> SEARCH_API
        SEARCH_API --> MEMORY_BANK
    end

    ADK_AGENT[Executive Producer<br/>ADK Agent] -->|Current| REDIS_SAVE
    ADK_AGENT -->|Future| CALLBACK
    ADK_AGENT -->|Future| PRELOAD

    MEMORY_BANK -->|Semantic search<br/>Cross-session memory| CONTEXT[Agent Context<br/>Enriched with memories]

    style REDIS_STORE fill:#dc2626,color:#fff
    style MEMORY_BANK fill:#10b981,color:#fff
    style CALLBACK fill:#8b5cf6,color:#fff
```

---

## 10. Technology Stack

```mermaid
mindmap
  root((AI Agency))
    Frontend
      Next.js 14+
      React 18+
      TypeScript 5+
      Tailwind CSS
      Zustand State
      WebSocket Client
      Web Audio API
    Backend
      Python 3.13+
      FastAPI
      uv Package Manager
      Pydantic Models
      AsyncIO
      WebSocket Server
    Agents
      Google ADK
      Gemini Live Native Audio
      Gemini Pro
      Imagen 3
      Veo 2
      Lyria Music/TTS
      Speech-to-Text v2 Chirp
      Code Assist
    Storage
      Redis 7+
        Project Briefs
        Assets
        Agent Status
        Pub/Sub Events
      Vertex AI Memory Bank Planned
        Long-term memories
        Semantic search
        Cross-session context
    Infrastructure
      GCP Project
      Vertex AI APIs
      Cloud Storage
      WebSocket
      RESTful API
```

---

## Key Architectural Principles

### 1. **Agentic Architecture**
- Executive Producer (Gemini Live) as orchestrator
- 5 specialist agents with distinct responsibilities
- Tool-based function calling for agent coordination

### 2. **Event-Driven Communication**
- WebSocket for real-time bidirectional streaming
- Redis Pub/Sub for agent event notifications
- Async/await throughout the stack

### 3. **Critique Loop**
- Producer evaluates agent outputs against brief
- Automatic regeneration if quality score < 0.7
- Max 3 retries with feedback

### 4. **Audio-First Interface**
- Streaming PCM audio (16kHz input, 24kHz output)
- Gapless playback via scheduled AudioBuffers
- Voice Activity Detection (VAD) for turn management

### 5. **Type Safety**
- Pydantic models for all data structures
- TypeScript throughout frontend
- Validated WebSocket messages

### 6. **Product-Agnostic Design**
- Supports ANY product category (not just sneakers)
- Dynamic prompts based on product_category, brand_tone, theme
- Extensible agent system

---

## Deployment Architecture (Production)

```mermaid
graph TB
    subgraph "Client"
        BROWSER[Web Browser<br/>Next.js SSR]
    end

    subgraph "Load Balancer"
        LB[Cloud Load Balancer<br/>SSL/TLS Termination]
    end

    subgraph "Frontend Tier"
        NEXT1[Next.js Server 1<br/>:3000]
        NEXT2[Next.js Server 2<br/>:3000]
        NEXT3[Next.js Server 3<br/>:3000]
    end

    subgraph "Backend Tier"
        API1[FastAPI + Uvicorn 1<br/>:8000]
        API2[FastAPI + Uvicorn 2<br/>:8000]
        API3[FastAPI + Uvicorn 3<br/>:8000]
    end

    subgraph "Worker Tier"
        CELERY1[Celery Worker 1]
        CELERY2[Celery Worker 2]
        CELERY3[Celery Worker 3]
    end

    subgraph "Persistence"
        REDIS_CLUSTER[(Redis Cluster<br/>Sentinel HA)]
        GCS[(Cloud Storage<br/>Audio/Video/Images)]
    end

    subgraph "External Services"
        VERTEX[Vertex AI<br/>All Google AI APIs]
    end

    BROWSER <-->|HTTPS<br/>WSS| LB
    LB <--> NEXT1
    LB <--> NEXT2
    LB <--> NEXT3

    NEXT1 <-->|WS/HTTP| API1
    NEXT2 <-->|WS/HTTP| API2
    NEXT3 <-->|WS/HTTP| API3

    API1 --> REDIS_CLUSTER
    API2 --> REDIS_CLUSTER
    API3 --> REDIS_CLUSTER

    API1 --> GCS
    API2 --> GCS
    API3 --> GCS

    API1 <--> VERTEX
    API2 <--> VERTEX
    API3 <--> VERTEX

    CELERY1 --> REDIS_CLUSTER
    CELERY2 --> REDIS_CLUSTER
    CELERY3 --> REDIS_CLUSTER

    style LB fill:#10b981,color:#fff
    style REDIS_CLUSTER fill:#dc2626,color:#fff
    style VERTEX fill:#8b5cf6,color:#fff
```

---

**Document Version:** 1.0
**Last Updated:** 2025-01-04
**Total Diagrams:** 10
**Coverage:** Frontend + Backend + Agents + Infrastructure
