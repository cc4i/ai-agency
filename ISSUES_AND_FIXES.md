# Issues and Fixes

## Issue 1: Noisy Audio Response ✅ FIXED

### Problem
Audio from Gemini has noise and is not clear.

### Root Cause
AudioBuffer was being created with `audioContextRef.current.sampleRate` which could mismatch Gemini's 24kHz output.

### Fix Applied
**File**: `frontend/src/hooks/useWebSocket.ts`

Changed from:
```typescript
audioBuffer = audioContextRef.current.createBuffer(
  1,
  float32.length,
  audioContextRef.current.sampleRate // This could be wrong!
);
```

To:
```typescript
audioBuffer = audioContextRef.current.createBuffer(
  1,
  float32.length,
  24000 // Gemini outputs at 24kHz - explicit!
);
```

**Why this fixes it:**
- Gemini Live **always** outputs at 24kHz
- We must create AudioBuffer at exactly 24kHz
- Mismatched sample rates cause noise/distortion

**Test**: Refresh page, audio should be clearer now.

---

## Issue 2: Agents Not Working ❌ NOT CONNECTED

### Problem
Agents (art director, etc.) appear to start but don't actually execute/complete tasks.

### Root Cause
**Gemini Live conversation is NOT integrated with the agent orchestration system.**

Current state:
- ✅ Gemini Live voice conversation works
- ✅ Agent code exists (art_director.py, strategy.py, etc.)
- ✅ Orchestration service exists
- ❌ **Gemini Live doesn't call the orchestration service**
- ❌ **No integration between conversation and agents**

### What's Missing

The system has two **separate, unconnected** parts:

```
Part 1: Voice Conversation (WORKING)
┌─────────────────────────────────────┐
│  User speaks → Gemini Live          │
│  Gemini Live responds (voice only)  │
│  No agent execution                 │
└─────────────────────────────────────┘

Part 2: Agent System (EXISTS BUT UNUSED)
┌─────────────────────────────────────┐
│  AgentOrchestrator                  │
│  ├─ Strategy Agent                  │
│  ├─ Art Director Agent              │
│  ├─ Video Producer Agent            │
│  └─ etc.                            │
│  (Never gets called!)               │
└─────────────────────────────────────┘
```

### What Needs to Happen

We need to connect Gemini Live's **Executive Producer persona** to the **actual agent orchestration**:

```
Desired Flow:
┌─────────────────────────────────────────────────────┐
│ 1. User speaks to Gemini Live                      │
│    "Create a campaign for my running shoes"        │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 2. Gemini Live (as Executive Producer)             │
│    Understands request, creates plan               │
│    Responds: "I'll task our Strategy team..."      │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 3. Backend calls AgentOrchestrator                 │
│    orchestrator.execute_agent("strategy", task)    │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 4. Strategy Agent executes                         │
│    Generates personas, slogans, etc.               │
│    Returns results                                 │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 5. Gemini Live announces results                   │
│    "Our Strategy team created 3 slogans..."        │
│    Frontend displays slogans in UI                 │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 6. User selects slogan (via voice)                 │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ 7. Backend triggers next agents                    │
│    Art Director, Video Producer (parallel)         │
└─────────────────────────────────────────────────────┘
```

### Implementation Needed

#### Option 1: Function Calling (Recommended)
Use Gemini's function calling to trigger agents:

```python
# In gemini_live.py

# Define tools/functions for Gemini
AGENT_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "create_campaign_strategy",
                "description": "Task the Strategy Agent to create campaign personas and slogans",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {"type": "string"},
                        "product_category": {"type": "string"},
                        "theme": {"type": "string"}
                    }
                }
            },
            {
                "name": "generate_hero_images",
                "description": "Task the Art Director to create hero images",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slogan": {"type": "string"},
                        "theme": {"type": "string"}
                    }
                }
            },
            # ... more agent functions
        ]
    }
]

# In setup message
setup_message = {
    "setup": {
        "model": "models/gemini-2.5-flash-native-audio-preview-09-2025",
        "tools": AGENT_TOOLS,  # ADD THIS
        "generation_config": {
            "response_modalities": ["AUDIO"],
            # ...
        }
    }
}

# Handle tool calls from Gemini
async def _handle_gemini_to_frontend(self):
    # ...
    if "toolCall" in data:
        tool_call = data["toolCall"]
        function_name = tool_call["functionCalls"][0]["name"]
        args = tool_call["functionCalls"][0]["args"]

        # Execute agent
        if function_name == "create_campaign_strategy":
            from app.services.orchestration import AgentOrchestrator
            orchestrator = AgentOrchestrator()
            result = await orchestrator.execute_agent(
                "strategy",
                task=args,
                project_id=self.project_id
            )

            # Send result back to Gemini
            await self._send_tool_response(tool_call["id"], result)
```

#### Option 2: Text Parsing (Simpler but Less Reliable)
Parse Gemini's text responses for agent trigger keywords:

```python
async def _process_text_output(self, text: str):
    # Check if Gemini wants to trigger agents
    if "tasked our Strategy Agent" in text or "Strategy team" in text:
        # Extract parameters from conversation context
        await self._trigger_strategy_agent()

    if "sending to our Art Director" in text:
        await self._trigger_art_director()
```

#### Option 3: Conversation Manager (Most Robust)
Create a conversation manager that understands user intent:

```python
class ConversationManager:
    async def process_user_message(self, text: str, audio: bytes):
        # Analyze intent
        intent = await self._analyze_intent(text)

        if intent == "create_campaign":
            # Extract parameters
            params = await self._extract_campaign_params(text)

            # Start workflow
            await self._start_campaign_workflow(params)
```

### Quick Test Solution

To test if agents work at all, you can manually trigger them:

**Add to `main.py`:**
```python
@app.post("/api/test/trigger-strategy")
async def test_trigger_strategy(project_id: str = "aura_smart_sneaker"):
    """Test endpoint to manually trigger Strategy Agent."""
    from app.services.orchestration import AgentOrchestrator

    orchestrator = AgentOrchestrator()

    task = {
        "product_name": "Aura Smart Sneaker",
        "product_category": "footwear",
        "theme": "futuristic urban athlete",
        "key_features": ["glowing sole", "smart tracking", "adaptive cushioning"],
        "brand_tone": "innovative, energetic, tech-forward",
        "target_market": "Urban athletes aged 18-35"
    }

    result = await orchestrator.execute_agent(
        "strategy",
        task=task,
        project_id=project_id,
        with_critique=False
    )

    return result
```

**Test it:**
```bash
curl -X POST "http://localhost:8000/api/test/trigger-strategy"
```

This will show if the Strategy Agent actually works.

---

## Summary

### Issue 1: Noisy Audio ✅
- **Status**: FIXED
- **Change**: Explicit 24kHz AudioBuffer creation
- **Action**: Refresh page to test

### Issue 2: Agents Not Working ❌
- **Status**: NOT IMPLEMENTED
- **Cause**: No integration between Gemini Live and AgentOrchestrator
- **Solution Needed**:
  1. Add function calling to Gemini Live setup
  2. Handle toolCall messages
  3. Call AgentOrchestrator when Gemini requests it
  4. Send results back through conversation

**Which would you like me to implement?**
1. Quick test endpoint to verify agents work
2. Full function calling integration
3. Both

Let me know and I'll implement the agent integration!
