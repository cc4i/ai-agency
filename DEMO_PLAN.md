# AI Agency - Demo Flow Walkthrough

## Overview

This document describes the complete "Aura Smart Sneaker" demo flow - a 9-minute end-to-end demonstration of the AI Agency system where a user (Creative Director) directs an AI-powered agency to launch a complete marketing campaign through voice conversation.

**Demo Duration**: 9 minutes
**Product**: Aura Smart Sneaker
**Theme**: Tokyo neon, futuristic urban athlete
**Key Feature**: Glowing sole with smart tracking

---

## Demo Architecture

```
User (Creative Director)
    ↓ (Voice commands)
Executive Producer (Gemini Live)
    ↓ (Delegates tasks)
┌──────────────────────────────────────┐
│ Specialist Agents (5)                │
│                                      │
│ • Strategy Agent (Gemini Pro)        │
│ • Art Director (Imagen)              │
│ • Video Producer (Veo)               │
│ • Audio Team (Lyria)                 │
│ • Web Dev (Code Assist)              │
└──────────────────────────────────────┘
    ↓
Complete Marketing Campaign
```

---

## PHASE 1: The Handoff & Planning (2-3 minutes)

### Step 1: Welcome Screen (0:00)

**User Sees:**
```
┌─────────────────────────────────────────────┐
│                                             │
│     Welcome, Creative Director.             │
│                                             │
│           ╔═══════════╗                     │
│           ║    🎤     ║                     │
│           ╚═══════════╝                     │
│              (glowing)                      │
│                                             │
│  Click the mic and say "Let's get started"  │
│                                             │
└─────────────────────────────────────────────┘
```

**User Action:** 🎤 "Let's get started"

---

### Step 2: Producer Introduction (0:30)

**Producer (Voice + Text):**
> "Welcome. I'm your Executive Producer. Our first project is the 'Aura Smart Sneaker' launch. I've pulled up the initial sketch."

**UI Updates:**
```
┌──────────────────┬──────────────────────────────┐
│ Project Brief    │  Workspace                   │
│                  │                              │
│ Product:         │  [SKETCH IMAGE]              │
│ Aura Smart       │                              │
│ Sneaker          │  Tokyo neon scene            │
│                  │  with glowing sneaker        │
│ Theme:           │                              │
│ Tokyo neon       │                              │
│                  │                              │
└──────────────────┴──────────────────────────────┘
```

**Producer continues:**
> "To start, I need to build out the core marketing strategy for this footwear campaign. Shall I proceed?"

**User Action:** 🎤 "Yes, go ahead"

---

### Step 3: Plan Presentation - Chain-of-Thought (1:00)

**Producer (Voice + Text):**
> "Great. To launch the 'Aura Smart Sneaker', I've broken the project into 5 phases:
>
> **Phase 1:** Our Strategy Agent [Gemini Pro] will analyze the sketch and define customer personas and slogans.
>
> **Phase 2:** Our Art Director [Imagen] will create the hero image based on your selected slogan.
>
> **Phase 3:** Our Video Producer [Veo] will generate the social media clip.
>
> **Phase 4:** Simultaneously, our Audio Team [Lyria] will compose the jingle and podcast ad.
>
> **Phase 5:** Finally, our Web Dev Agent [Gemini Code Assist] will build the landing page.
>
> This plan is now in your Project Brief. Shall I task the Strategy Agent to begin?"

**UI Updates:**
```
┌──────────────────┬──────────────────────────────┐
│ Project Brief    │  Campaign Plan               │
│                  │                              │
│ ✅ Plan Created  │  ┌─────────────────────────┐ │
│                  │  │ Phase 1: Strategy       │ │
│ Campaign Plan:   │  │ [Gemini Pro]            │ │
│ • Strategy       │  │ Generate personas       │ │
│ • Art Director   │  │ and slogans             │ │
│ • Video          │  └─────────────────────────┘ │
│ • Audio          │                              │
│ • Web Dev        │  ┌─────────────────────────┐ │
│                  │  │ Phase 2: Art Director   │ │
│                  │  │ [Imagen]                │ │
│                  │  │ Create hero images      │ │
│                  │  └─────────────────────────┘ │
│                  │                              │
│                  │  [... phases 3-5 ...]       │
└──────────────────┴──────────────────────────────┘
```

**User Action:** 🎤 "Yes, task the Strategy Agent"

**Key Feature Demonstrated:** ✅ Agentic Planning (Producer presents plan before execution)

---

## PHASE 2: The Agency Hub (5-7 minutes)

### Step 4: Strategy Agent Execution (2:00)

**Producer:**
> "Okay, I've tasked our Strategy Agent [Gemini Pro] with analyzing the sketch."

**UI Updates:**
```
┌──────────────────┬──────────────────────────────┐
│ Project Brief    │  Workspace                   │
│                  │                              │
│ Status:          │  [THINKING ANIMATION]        │
│ 🟡 Strategy      │                              │
│    Agent         │     ●  ●  ●                  │
│    Working...    │  (pulsing dots)              │
│                  │                              │
│                  │  Strategy Agent is           │
│                  │  analyzing the sketch...     │
└──────────────────┴──────────────────────────────┘
```

**Backend Action:** (15-30 seconds)
- Gemini Pro Vision analyzes the sketch image
- Gemini Pro generates personas + slogans based on analysis

**Producer (2:30):**
> "It's generated three key customer personas and five potential slogans. They are on your screen now."

**UI Updates:**
```
┌──────────────────┬──────────────────────────────────────────────┐
│ Project Brief    │  Strategy Output                             │
│                  │                                              │
│ ✅ Strategy      │  CUSTOMER PERSONAS (3)                       │
│    Complete      │  ┌────────────────────────────────────────┐  │
│                  │  │ 1. Alex "The Night Runner"             │  │
│ Personas: 3      │  │    Age: 25-32, Urban professional      │  │
│ Slogans: 5       │  │    Motivation: Late-night city runs    │  │
│                  │  │    Pain Point: Visibility & safety     │  │
│                  │  └────────────────────────────────────────┘  │
│                  │  ┌────────────────────────────────────────┐  │
│                  │  │ 2. Maya "The Tech Explorer"            │  │
│                  │  │    Age: 18-24, Early adopter           │  │
│                  │  │    Motivation: Latest fitness tech     │  │
│                  │  └────────────────────────────────────────┘  │
│                  │  ┌────────────────────────────────────────┐  │
│                  │  │ 3. Jordan "The Fitness Innovator"      │  │
│                  │  │    Age: 28-35, Fitness enthusiast      │  │
│                  │  │    Motivation: Performance tracking    │  │
│                  │  └────────────────────────────────────────┘  │
│                  │                                              │
│                  │  SLOGANS (5)                                 │
│                  │  1. "Step Into Tomorrow"                     │
│                  │  2. "Light Up Your Run"                      │
│                  │  3. "Run on Light"          ⭐               │
│                  │  4. "Glow Forward"                           │
│                  │  5. "The Future at Your Feet"                │
└──────────────────┴──────────────────────────────────────────────┘
```

**User Action (3:00):** 🎤 "I like slogan number three: 'Run on light'"

**Key Feature Demonstrated:** ✅ Specific Agent Outputs (exactly 3 personas, 5 slogans)

---

### Step 5: Art Director Execution (3:30)

**Producer:**
> "Excellent choice. Now, I'm sending this slogan to our Art Director Agent [Imagen] to generate the hero image."

**UI Updates:**
```
┌──────────────────┬──────────────────────────────┐
│ Project Brief    │  Workspace                   │
│                  │                              │
│ ✅ Strategy      │  [THINKING ANIMATION]        │
│ 🟡 Art Director  │                              │
│    Working...    │     ●  ●  ●                  │
│                  │                              │
│ Selected Slogan: │  Art Director is             │
│ "Run on light"   │  creating hero images...     │
│                  │                              │
│ Brief Updated! ✨ │                              │
└──────────────────┴──────────────────────────────┘
```

**Backend Action:** (30-60 seconds)
- Imagen generates 4 photorealistic images
- Theme: Tokyo neon street scene with glowing sneaker
- Each variation slightly different angle/composition

**Producer (4:30):**
> "Our Art Director has created four stunning hero images. Take a look and let me know which one resonates with you."

**UI Updates:**
```
┌──────────────────┬────────────────────────────────────────┐
│ Project Brief    │  Hero Images (4)                       │
│                  │                                        │
│ ✅ Strategy      │  ┌──────────┬──────────┐              │
│ ✅ Art Director  │  │  Image 1 │ Image 2  │ ⭐           │
│                  │  │          │          │              │
│ Selected:        │  │  [IMG]   │  [IMG]   │              │
│ (pending)        │  │          │          │              │
│                  │  └──────────┴──────────┘              │
│ Slogans: 5       │  ┌──────────┬──────────┐              │
│ Images: 4        │  │  Image 3 │  Image 4 │              │
│                  │  │          │          │              │
│                  │  │  [IMG]   │  [IMG]   │              │
│                  │  │          │          │              │
│                  │  └──────────┴──────────┘              │
│                  │                                        │
│                  │  All images: Tokyo neon theme,         │
│                  │  glowing sole, urban runner            │
└──────────────────┴────────────────────────────────────────┘
```

**User Action (5:00):** 🎤 "The one on the top right is perfect" (Image 2)

**Key Feature Demonstrated:** ✅ Real-time Project Brief Updates

---

### Step 6: Proactive Collaboration Announcement (5:30)

**Producer:**
> "Got it. I've added that to the project brief. Our Video Producer Agent [Veo] and Web Dev Agent [Gemini Code Assist] have already been notified and are using that image as their style reference.
>
> While they work, our Audio Agent [Lyria] has a proactive suggestion: based on the 'Tokyo neon' theme and the 'Run on light' slogan, it recommends an 'uplifting, futuristic, electronic beat'. Do you want to hear a sample?"

**UI Updates:**
```
┌──────────────────┬────────────────────────────────────────┐
│ Project Brief    │  Workspace                             │
│                  │                                        │
│ ✅ Strategy      │  [AUDIO AGENT SUGGESTION]              │
│ ✅ Art Director  │                                        │
│ 🟡 Video         │  💡 Proactive Suggestion:              │
│ 🟡 Audio         │                                        │
│ 🟡 Web Dev       │  "Based on your Tokyo neon theme,      │
│                  │   I recommend an uplifting,            │
│ Selected Image:  │   futuristic electronic beat."         │
│ Image 2          │                                        │
│                  │  ▶️ [Play Sample]                       │
│ All agents       │                                        │
│ working in       │                                        │
│ parallel!        │                                        │
└──────────────────┴────────────────────────────────────────┘
```

**User Action (6:00):** 🎤 "Yes"

**Audio sample plays (5 seconds)**

**User continues:** 🎤 "That's great. Now show me the video."

**Key Feature Demonstrated:** ✅ Proactive Collaboration (Audio Agent makes autonomous suggestion)

---

### Step 7: Video Producer with Internal Critique Loop (6:30)

**Producer:**
> "Okay, our Video Producer Agent [Veo] has a first pass..."

**Video plays (15 seconds) - First Draft**

**UI Updates:**
```
┌──────────────────┬────────────────────────────────────────┐
│ Project Brief    │  Video Review                          │
│                  │                                        │
│ 🟡 Video         │  [VIDEO PLAYER - First Draft]          │
│    Under Review  │                                        │
│                  │  Duration: 15s                         │
│                  │  ▶️ [Play]                              │
│                  │                                        │
│ Producer is      │  Producer analyzing against brief...   │
│ analyzing...     │                                        │
└──────────────────┴────────────────────────────────────────┘
```

**Producer (Internal Critique - 7:00):**
> "Hmm, I'm analyzing it against our brief. The 'Tokyo neon' theme is strong, but it doesn't clearly show the 'glowing sole'. I'm sending it back to the agent with instructions for a 2-second close-up."

**UI Updates:**
```
┌──────────────────┬────────────────────────────────────────┐
│ Project Brief    │  Video Review                          │
│                  │                                        │
│ 🟡 Video         │  [VIDEO PLAYER - First Draft]          │
│    Revision 1    │                                        │
│                  │  ⚠️  Producer Critique:                │
│ Producer         │  "Theme is strong, but missing         │
│ identified       │   glowing sole close-up"               │
│ issue!           │                                        │
│                  │  [THINKING ANIMATION]                  │
│                  │  Requesting revision with specific     │
│                  │  instructions...                       │
└──────────────────┴────────────────────────────────────────┘
```

**Backend Action:** (30-45 seconds)
- Producer sends critique to Video Producer Agent
- Veo regenerates with specific instructions: "Add 2-second close-up of glowing sole"
- Max 2 revisions allowed per agent

**Producer (8:00):**
> "Okay, the revision is complete. Here is the new version."

**Revised video plays (15 seconds) - Now includes glowing sole close-up**

**UI Updates:**
```
┌──────────────────┬────────────────────────────────────────┐
│ Project Brief    │  Video Review                          │
│                  │                                        │
│ ✅ Video         │  [VIDEO PLAYER - Revised]              │
│    Complete      │                                        │
│    (Revision 1)  │  ✅ Producer Approved                  │
│                  │                                        │
│ Revision Notes:  │  15-second social media clip           │
│ "Added 2-sec     │  • Tokyo neon cityscape                │
│  glowing sole    │  • Runner in motion                    │
│  close-up"       │  • 2-second glowing sole close-up ✨   │
│                  │                                        │
│                  │  Duration: 15s                         │
│                  │  ▶️ [Play]                              │
└──────────────────┴────────────────────────────────────────┘
```

**User Action:** 🎤 "That's perfect. Let's get the audio and landing page finalized."

**Key Feature Demonstrated:** ✅ Internal Critique Loop (Producer autonomously evaluates and requests revision)

---

### Step 8: Final Asset Delivery (8:30)

**Producer:**
> "On it. Our Audio Team has composed the custom jingle with Lyria, generated the TTS voiceover for the podcast ad, and prepared the transcription for the global launch.
>
> Simultaneously, our Web Dev Agent [Gemini Code Assist] has generated the code for the 'Coming Soon' page, using our hero image and slogan. The code is generated. I'm deploying a live preview for you now."

**UI Updates:**
```
┌──────────────────┬────────────────────────────────────────┐
│ Project Brief    │  Final Assets                          │
│                  │                                        │
│ ✅ Strategy      │  AUDIO ASSETS                          │
│ ✅ Art Director  │  ┌──────────────────────────────────┐  │
│ ✅ Video         │  │ 🎵 Jingle (10s)                  │  │
│ ✅ Audio         │  │    Uplifting electronic beat     │  │
│ ✅ Web Dev       │  │    ▶️ [Play]                      │  │
│                  │  └──────────────────────────────────┘  │
│ Campaign         │  ┌──────────────────────────────────┐  │
│ COMPLETE! 🎉     │  │ 🎙️ Podcast Ad (8s)               │  │
│                  │  │    TTS voiceover                 │  │
│                  │  │    ▶️ [Play]                      │  │
│                  │  └──────────────────────────────────┘  │
│                  │  ┌──────────────────────────────────┐  │
│                  │  │ 📝 Transcription                 │  │
│                  │  │    SRT format for global launch  │  │
│                  │  │    📥 [Download]                  │  │
│                  │  └──────────────────────────────────┘  │
│                  │                                        │
│                  │  LANDING PAGE                          │
│                  │  ┌───────────┬──────────────────────┐  │
│                  │  │ Code      │ Live Preview         │  │
│                  │  │           │                      │  │
│                  │  │ HTML      │  [Hero Image #2]     │  │
│                  │  │ CSS       │                      │  │
│                  │  │ JS        │  "Run on light"      │  │
│                  │  │           │                      │  │
│                  │  │ [Tabs]    │  [Countdown: 30d]    │  │
│                  │  │           │                      │  │
│                  │  │           │  [Email Signup]      │  │
│                  │  │           │                      │  │
│                  │  └───────────┴──────────────────────┘  │
└──────────────────┴────────────────────────────────────────┘
```

**Key Feature Demonstrated:** ✅ Parallel Agent Execution (Video, Audio, Web Dev all working simultaneously)

---

## PHASE 3: Launch Party (1 minute)

### Step 9: Campaign Completion (9:00)

**Producer:**
> "And with that, our campaign is complete. We've gone from a sketch to a full product launch in just a few minutes. All assets are available in your project brief."

**UI Transition to Final Summary:**
```
┌─────────────────────────────────────────────────────────────┐
│                 🎉 Campaign Complete! 🎉                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Aura Smart Sneaker - Full Marketing Campaign              │
│  Theme: Tokyo Neon | Slogan: "Run on Light"                │
│                                                             │
│  ┌───────────────┬───────────────┬───────────────┐         │
│  │ STRATEGY      │ ART DIRECTOR  │ VIDEO         │         │
│  │               │               │               │         │
│  │ ✅ 3 Personas │ ✅ 4 Images   │ ✅ 15s Clip   │         │
│  │ ✅ 5 Slogans  │ Tokyo neon    │ Social media  │         │
│  │               │ theme         │ (Revised)     │         │
│  │               │               │               │         │
│  │ [View]        │ [View]        │ [Play]        │         │
│  └───────────────┴───────────────┴───────────────┘         │
│                                                             │
│  ┌───────────────────────┬───────────────────────┐         │
│  │ AUDIO TEAM            │ WEB DEV               │         │
│  │                       │                       │         │
│  │ ✅ Jingle (10s)       │ ✅ Landing Page       │         │
│  │ ✅ Podcast Ad (8s)    │ HTML/CSS/JS Code      │         │
│  │ ✅ Transcription      │ Live Preview          │         │
│  │                       │                       │         │
│  │ [Play All]            │ [View Code/Preview]   │         │
│  └───────────────────────┴───────────────────────┘         │
│                                                             │
│  ┌─────────────────────────────────────────────┐           │
│  │ Project Brief (Final)                       │           │
│  │                                             │           │
│  │ • Product: Aura Smart Sneaker               │           │
│  │ • Category: Footwear                        │           │
│  │ • Theme: Tokyo neon, futuristic athlete     │           │
│  │ • Selected Slogan: "Run on light"           │           │
│  │ • Selected Image: #2 (Tokyo street scene)   │           │
│  │ • All Assets: 5/5 agents complete           │           │
│  │ • Timeline: 9 minutes (sketch → launch)     │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
│  [Download All Assets]  [Share Campaign]  [New Project]    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Feature Demonstrated:** ✅ Complete Multi-Agent Campaign

---

## Timeline Summary

```
0:00 ─ Welcome screen
0:30 ─ Producer introduction + sketch display
1:00 ─ Plan presentation (5 phases)
1:30 ─ User approves plan
       │
2:00 ─ Strategy Agent working
2:30 ─ 3 personas + 5 slogans displayed
3:00 ─ User selects "Run on light"
       │
3:30 ─ Art Director working
4:30 ─ 4 hero images displayed
5:00 ─ User selects Image 2
       │
5:30 ─ Proactive collaboration announcement
6:00 ─ Audio suggestion + sample plays
       │
6:30 ─ Parallel agents working (Video/Audio/Web)
7:00 ─ Video first draft + Producer critique
7:30 ─ Video revision in progress
8:00 ─ Revised video approved
       │
8:30 ─ All final assets delivered
       │
9:00 ─ Launch Party summary screen
```

---

## Critical Demo Features Demonstrated

### 1. ✅ Audio-First Interaction
- All user commands via voice microphone
- Producer responds with voice + synchronized text transcript
- Natural conversation flow

### 2. ✅ Agentic Planning (Chain-of-Thought)
- Producer presents 5-phase plan before execution
- User must approve plan ("Shall I task the Strategy Agent to begin?")
- Plan visible in Project Brief throughout

### 3. ✅ Internal Critique Loop
- Producer autonomously evaluates Video Producer output
- Identifies missing "glowing sole" close-up
- Sends specific revision instructions
- Shows autonomous reasoning: "I'm analyzing it against our brief"

### 4. ✅ Proactive Collaboration
- Audio Agent makes suggestion without being asked
- Video/Web Dev agents auto-notified when image selected
- Parallel work without explicit user commands
- Demonstrates agent-to-agent communication

### 5. ✅ Parallel Agent Execution
- 3 agents work simultaneously (Video, Audio, Web Dev)
- Real-time status updates for each
- Efficient workflow (not sequential)

### 6. ✅ Real-time Project Brief Updates
- Brief updates as user makes selections
- "I've added that to the project brief"
- Visual updates with animations
- Single source of truth for all agents

### 7. ✅ Specific Agent Outputs
- Strategy: Exactly 3 personas + 5 slogans
- Art Director: Exactly 4 images
- Audio Team: 3 distinct outputs (jingle, ad, transcription)
- Video: 15-second clip with revision capability
- Web Dev: Complete HTML/CSS/JS code + live preview

---

## Required Demo Assets

### Pre-seeded Campaign Data

```python
AURA_CAMPAIGN = {
    "product_name": "Aura Smart Sneaker",
    "product_category": "footwear",
    "theme": "Tokyo neon",
    "key_features": [
        "glowing sole",
        "smart tracking",
        "adaptive cushioning"
    ],
    "brand_tone": "futuristic, energetic, tech-forward",
    "target_market": "Urban athletes aged 18-35",
    "initial_sketch_url": "gs://ai-agency-demo/aura_sketch.png"
}
```

### Initial Sketch Requirements

**File**: `demo_assets/aura_sketch.png`

**Description**:
- Tokyo neon street scene at night
- Runner wearing futuristic sneakers
- Visible glowing sole on sneaker
- Urban, cyberpunk aesthetic
- High quality, photorealistic style

### Expected Agent Outputs

#### Strategy Agent
```python
{
    "personas": [
        {
            "name": "Alex 'The Night Runner'",
            "age_range": "25-32",
            "description": "Urban professional who runs late at night",
            "pain_points": ["Visibility", "Safety", "Motivation"],
            "motivations": ["Stress relief", "Fitness goals"]
        },
        {
            "name": "Maya 'The Tech Explorer'",
            "age_range": "18-24",
            "description": "Early adopter who loves fitness tech",
            "pain_points": ["Boredom", "Tracking accuracy"],
            "motivations": ["Latest technology", "Social sharing"]
        },
        {
            "name": "Jordan 'The Fitness Innovator'",
            "age_range": "28-35",
            "description": "Fitness enthusiast seeking performance edge",
            "pain_points": ["Performance plateaus", "Data insights"],
            "motivations": ["Optimization", "Competition"]
        }
    ],
    "slogans": [
        "Step Into Tomorrow",
        "Light Up Your Run",
        "Run on Light",  # User selects this one
        "Glow Forward",
        "The Future at Your Feet"
    ]
}
```

#### Art Director
- 4 photorealistic images
- All featuring Tokyo neon theme
- Glowing sole visible in each
- Urban runner in motion or posed
- High quality Imagen-generated

#### Video Producer
- **First Draft**: 15s clip, Tokyo neon theme, BUT missing glowing sole close-up
- **Revised**: 15s clip with 2-second glowing sole close-up added
- Social media format (vertical or square)

#### Audio Team
- **Jingle**: 10-second uplifting electronic beat
- **Podcast Ad**: 8-second TTS voiceover
- **Transcription**: SRT format transcription file

#### Web Dev
- HTML/CSS/JavaScript landing page
- Features: Hero image, slogan, countdown timer, email signup
- Tokyo neon color scheme (neon blue/purple)
- Responsive design

---

## Demo Execution Modes

### Mode 1: Automated Demo (No User Input Required)
```python
# Pre-configured selections
user_selections = {
    "slogan": "Run on light",  # Slogan #3
    "image": 1,  # Image #2 (top right)
    "audio_sample": True
}

await demo_flow.run_demo(user_selections)
```

### Mode 2: Interactive Demo (Real User Voice Commands)
```python
# User speaks at each decision point
await demo_flow.run_demo()
```

### Mode 3: Guided Demo (Voice prompts + Auto-advance)
```python
# Hybrid: Voice prompts with timeout auto-advance
await demo_flow.run_demo(guided_mode=True, timeout=5)
```

---

## Technical Requirements

### Backend (Python)
```bash
# Verify Redis is running (existing service)
redis-cli ping  # Should return "PONG"

# Seed demo data
uv run python scripts/seed_demo_data.py --campaign=aura

# Start FastAPI server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)
```bash
cd frontend

# Start development server
npm run dev
```

### Environment Variables
```bash
# Required API Keys
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GEMINI_API_KEY=your_gemini_api_key
REDIS_URL=redis://localhost:6379

# Demo Configuration
DEMO_MODE=aura_smart_sneaker
AUTO_ADVANCE=false
```

---

## Success Criteria

The demo is successful when:

1. ✅ User completes full 9-minute flow via voice commands
2. ✅ All 5 specialist agents execute and generate outputs
3. ✅ Producer demonstrates chain-of-thought planning
4. ✅ Internal critique loop triggers (video revision)
5. ✅ Proactive collaboration visible (audio suggestion, parallel work)
6. ✅ Project Brief updates in real-time throughout
7. ✅ Final Launch Party screen shows all completed assets
8. ✅ No errors or timeouts during execution
9. ✅ Audio quality is clear and natural
10. ✅ Generated assets match expected quality standards

---

## Demo Variations

### Alternative Product Campaigns

Following the product-agnostic design, demo can be run with:

**Ember Energy Drink** (Beverage)
- Theme: Volcanic energy, extreme sports
- Key features: Natural caffeine, zero sugar, volcanic minerals
- Brand tone: Edgy, intense

**Luxe Minimalist Watch** (Fashion)
- Theme: Scandinavian minimalism
- Key features: Automatic movement, sapphire crystal, 40mm case
- Brand tone: Luxury, refined

**Nova Smart Home Hub** (Electronics)
- Theme: Ambient intelligence
- Key features: Voice control, AI learning, seamless integration
- Brand tone: Professional, innovative

---

## Troubleshooting

### Common Issues

**Issue**: Audio not streaming properly
- Check microphone permissions
- Verify WebSocket connection to Gemini Live
- Check audio encoding format (PCM16)

**Issue**: Agents timeout
- Verify Google AI API keys
- Check rate limits
- Ensure Redis is running
- Check network connectivity

**Issue**: Images not generating
- Verify Imagen API access
- Check prompt clarity
- Ensure sufficient API quota

**Issue**: Video generation fails
- Veo API may have longer processing time (60-90s)
- Check reference image URL is accessible
- Verify video generation parameters

---

## Next Steps After Demo

1. **Showcase "Show Me the API"** - Reveal implementation code
2. **Try alternative product** - Run Ember or Luxe campaign
3. **Customize campaign** - Upload custom sketch and parameters
4. **Export assets** - Download all generated assets
5. **Share results** - Social media integration

---

## Implementation Checklist

### Phase 1: Foundation
- [x] Backend infrastructure (FastAPI, Redis)
- [x] Google AI SDK integration
- [x] Agent base classes
- [ ] Demo seed data script ⚠️

### Phase 2: Agent Layer
- [x] Strategy Agent (Gemini Pro)
- [x] Art Director (Imagen)
- [x] Video Producer (Veo)
- [x] Audio Team (Lyria)
- [x] Web Dev (Code Assist)
- [x] Agent orchestration system
- [x] Event-driven architecture

### Phase 3: Executive Producer
- [x] Gemini Live integration
- [x] Producer logic and planner
- [x] Critique system
- [x] Conversation manager

### Phase 4: Frontend
- [x] Next.js UI with microphone interface
- [x] Project Brief panel
- [x] Asset display components
- [x] WebSocket audio streaming
- [ ] Launch Party summary screen ⚠️

### Phase 5: Demo & Polish
- [x] Demo flow orchestration (`demo_flow.py`)
- [ ] Automated demo mode ⚠️
- [ ] "Show Me the API" feature ⚠️
- [ ] End-to-end testing ⚠️
- [ ] Documentation

---

## Appendix: Voice Command Reference

### User Commands During Demo

| Timestamp | User Says | Expected Response |
|-----------|-----------|-------------------|
| 0:00 | "Let's get started" | Producer welcomes, shows sketch |
| 1:30 | "Yes, go ahead" | Producer presents 5-phase plan |
| 2:00 | "Yes, task the Strategy Agent" | Strategy Agent begins working |
| 3:00 | "I like slogan number three" / "Run on light" | Producer tasks Art Director |
| 5:00 | "The one on the top right" / "Image 2" | Producer notifies agents, Audio suggestion |
| 6:00 | "Yes" (to audio sample) | Audio sample plays |
| 6:30 | "Show me the video" | Video first draft plays |
| 8:00 | "That's perfect" | Producer finalizes remaining assets |

---

**Document Version**: 1.0
**Last Updated**: 2025-01-01
**Status**: Implementation Ready
