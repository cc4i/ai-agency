# Memory Bank Implementation Analysis

**Date**: 2025-11-08
**Analyst**: Claude Code
**Purpose**: Understand why Memory Bank only persists conversational text but not structured project data

---

## SECTION 1: Current Memory Bank Architecture

### How Does Memory Bank Work?

Memory Bank is a semantic memory layer built on top of Vertex AI's Memory Bank service, integrated via Google ADK (Agent Development Kit). Here's the architecture:

```
User Input (Voice/Text)
    ↓
ADK Session (InMemorySessionService)
    ↓
Events with Content (role + parts)
    ↓
Turn Complete Event
    ↓
add_session_to_memory() → Filtering
    ↓
Vertex AI Memory Bank (Long-term storage)
```

### What Triggers Persistence?

**Location**: `/Users/chuancc/mywork/ai/ai-agency/backend/app/services/gemini_live_adk.py`
**Lines**: 1853-1976

Persistence is triggered when:
1. A `turn_complete` event is detected in the live event stream (line 1855)
2. AND `ENABLE_MEMORY_BANK=true` in settings
3. AND `MEMORY_CALLBACK_ENABLED=true` in settings

**Important Note**: The ADK's `after_agent_callback` doesn't work in `run_live()` mode, so manual persistence is implemented in `_agent_to_client_messaging()` on turn_complete.

### What Filtering Happens?

**Location**: `/Users/chuancc/mywork/ai/ai-agency/backend/app/services/memory_service.py`
**Lines**: 206-278

The filtering logic in `add_session_to_memory()` validates each event:

```python
# Valid events MUST have:
1. content attribute that is not None
2. content.parts that exists
3. At least one part with:
   - text (hasattr(part, 'text') and part.text) OR
   - inline_data (hasattr(part, 'inline_data') and part.inline_data) OR
   - file_data (hasattr(part, 'file_data') and part.file_data)
```

**Explicitly Filtered Out** (lines 238-241):
- Events with `function_call` parts
- Events with `function_response` parts
- Events with no parts
- Events with empty content

---

## SECTION 2: Data Flow Analysis

### What Events Are Created During a Conversation?

Based on the code analysis, the ADK session contains these event types:

#### 1. **User Text Events** (Manually Added)
- **Location**: Lines 1797-1805
- **Trigger**: When `input_transcription` provides user speech-to-text
- **Structure**:
  ```python
  Event(
      author="user",
      content=types.Content(
          role="user",
          parts=[types.Part.from_text(text=user_text)]
      )
  )
  ```
- **Memory Bank Status**: ✅ SAVED (has text part)

#### 2. **Assistant Text Events** (Manually Added)
- **Location**: Lines 1822-1829
- **Trigger**: When `output_transcription` provides assistant speech-to-text
- **Structure**:
  ```python
  Event(
      author="model",
      content=types.Content(
          role="model",
          parts=[types.Part.from_text(text=transcript_text)]
      )
  )
  ```
- **Memory Bank Status**: ✅ SAVED (has text part)

#### 3. **Function Call Events** (ADK Auto-Generated)
- **Source**: ADK automatically creates these when tools are invoked
- **Structure**:
  ```python
  Event(
      content=Content(
          parts=[Part(function_call={...})]
      )
  )
  ```
- **Memory Bank Status**: ❌ FILTERED OUT (function_call parts explicitly excluded)

#### 4. **Function Response Events** (ADK Auto-Generated)
- **Source**: ADK automatically creates these when tools return results
- **Structure**:
  ```python
  Event(
      content=Content(
          parts=[Part(function_response={
              "name": "create_campaign_strategy",
              "response": {
                  "success": True,
                  "slogans": ["...", "...", "..."],
                  "personas": [...]
              }
          })]
      )
  )
  ```
- **Memory Bank Status**: ❌ FILTERED OUT (function_response parts explicitly excluded)

#### 5. **User Selection Events** (Manually Added)
- **Location**: Lines 1671-1678 (image), 1731-1738 (slogan)
- **Trigger**: When user clicks an image or slogan in the UI
- **Structure**:
  ```python
  Event(
      author="user",
      content=types.Content(
          role="user",
          parts=[types.Part.from_text(text="Selected hero image: img_abc123 - Hero image")]
      )
  )
  ```
- **Memory Bank Status**: ✅ SAVED (has text part)

#### 6. **Project State Snapshot** (Manually Injected)
- **Location**: Lines 1913-1946
- **Trigger**: On every turn_complete, before persistence
- **Structure**:
  ```python
  Content(
      role='model',
      parts=[Part(text="""[PROJECT STATE SNAPSHOT]
Product: Aura Smart Sneaker
Category: smart sneaker
Theme: futuristic
Brand Tone: cutting-edge
Target Market: urban athletes 18-35
Key Features: glowing sole, run tracking
Selected Slogan: "Step Into Your Aura"
Hero Image: Selected (variation 2)
""")]
  )
  ```
- **Memory Bank Status**: ✅ SAVED (has text part)

---

## SECTION 3: What IS Being Saved (Current State)

Memory Bank currently persists:

### 1. Conversational Dialogue
- User voice input transcriptions
- Assistant voice output transcriptions
- Example: "I'm launching a smart sneaker called Aura" → Saved
- Example: "Tell me more about the glowing sole feature" → Saved

### 2. User Selections (Text Format)
- Slogan selection: "Selected campaign slogan: 'Step Into Your Aura'"
- Image selection: "Selected hero image: img_abc123 - Hero image"

### 3. Project State Snapshots (Every Turn)
```
[PROJECT STATE SNAPSHOT]
Product: Chronos
Category: luxury watch
Theme: timeless elegance
Brand Tone: sophisticated
Target Market: successful executives
Key Features: AI health tracking, titanium frame
Selected Slogan: "Time, Perfected"
Hero Image: Selected (variation 3)
```

**Why This Works**: All three use `types.Part.from_text()` or `Part(text=...)`, which Memory Bank's filter accepts.

---

## SECTION 4: What IS NOT Being Saved (Missing Data)

### 1. Tool Call Results (Complete Loss)

When `create_campaign_strategy` executes, it returns:

```python
{
    "success": True,
    "message": "Strategy Agent generated 5 slogans and 3 personas...",
    "slogans": [
        "Step Into Your Aura",
        "Glow with the Flow",
        "The Future at Your Feet",
        "Run Illuminated",
        "Your Energy, Visualized"
    ],
    "personas": [
        {
            "name": "Marcus the Urban Runner",
            "age_range": "25-35",
            "description": "Tech-savvy fitness enthusiast...",
            "pain_points": ["Visibility during night runs", "Boring workout gear"],
            "motivations": ["Stand out", "Track performance"],
            "product_usage_context": "Early morning jogs in the city"
        },
        {...},
        {...}
    ]
}
```

**Memory Bank Status**: ❌ **COMPLETELY FILTERED OUT**
**Reason**: This data is in a `function_response` part, which Memory Bank intentionally excludes (line 240-241)

### 2. Image Generation Results

When `generate_hero_images` executes, it returns:

```python
{
    "success": True,
    "message": "Art Director generated 4 hero images...",
    "image_summaries": [
        {
            "description": "Futuristic urban athlete in motion with glowing sneakers",
            "variation": 1,
            "score": 0.92,
            "approved": False
        },
        {...},
        {...},
        {...}
    ]
}
```

**Memory Bank Status**: ❌ **COMPLETELY FILTERED OUT**
**Reason**: Function response part

**Note**: The actual image data (base64) is sent to frontend via `send_asset_added()` WebSocket message, but this never touches the ADK session at all.

### 3. Project Brief Updates

When `update_project_brief` is called:

```python
{
    "success": True,
    "message": "Updated project brief for Aura",
    "updated_fields": ["theme", "target_market", "key_features"],
    "brief": {
        "product_name": "Aura",
        "product_category": "smart sneaker",
        "theme": "futuristic",
        "key_features": ["glowing sole", "run tracking"],
        "brand_tone": "cutting-edge",
        "target_market": "urban athletes 18-35",
        "slogans": [],
        "selected_slogan": None,
        "hero_images": [],
        "selected_image": None,
        ...
    }
}
```

**Memory Bank Status**: ❌ **COMPLETELY FILTERED OUT**
**Reason**: Function response part

**Workaround**: The Project State Snapshot (added at line 1914) partially compensates by injecting a text summary, but it's a simplified snapshot, not the full brief.

### 4. Video/Audio/Landing Page Results

Same issue - all tool results are filtered out:
- `generate_social_video` → VideoAsset with URL, duration, params
- `generate_audio_assets` → Jingle, podcast ad, transcription
- `generate_landing_page` → CodeAsset with HTML/CSS/JS

**Memory Bank Status**: ❌ **ALL FILTERED OUT**

### 5. Agent Critiques and Revisions

When agents undergo critique cycles (strategy, art director, video producer all have critique enabled):

```python
# Critique result structure
{
    "status": "REVISE",
    "score": 0.65,
    "issues": [
        "Slogan 3 doesn't match futuristic theme",
        "Persona 2 age range too broad"
    ],
    "revision_instructions": "Regenerate slogan 3 with more tech-forward language..."
}
```

**Memory Bank Status**: ❌ **FILTERED OUT**
**Impact**: No record of quality control process or iteration history

---

## SECTION 5: Project Brief Snapshot Analysis

### When Does It Get Injected?

**Location**: Lines 1913-1946 in `gemini_live_adk.py`

**Timing**:
1. On every `turn_complete` event
2. BEFORE calling `memory_service.add_session_to_memory()`
3. After retrieving the latest session from ADK

### What Fields Are Included?

```python
summary_parts = [
    f"[PROJECT STATE SNAPSHOT]",
    f"Product: {brief.product_name or 'Not set'}",
    f"Category: {brief.product_category or 'Not set'}",
    f"Theme: {brief.theme or 'Not set'}",
    f"Brand Tone: {brief.brand_tone or 'Not set'}",
    f"Target Market: {brief.target_market or 'Not set'}",
]

# Conditionally added:
if brief.key_features:
    summary_parts.append(f"Key Features: {', '.join(brief.key_features)}")

if brief.selected_slogan:
    summary_parts.append(f'Selected Slogan: "{brief.selected_slogan}"')

if brief.selected_image:
    summary_parts.append(f"Hero Image: Selected (variation {brief.selected_image.generation_params.get('variation', 'unknown')})")
```

### Is It Working Correctly?

**Analysis**: ✅ Partially working

**What Works**:
- Snapshot is successfully created and injected
- Uses `latest_session.add_event()` which adds to session
- Format is text-based, so it passes Memory Bank's filter
- Provides high-level project state

**What's Missing**:
- No personas (3 detailed CustomerPersona objects)
- No slogans list (only selected slogan)
- No hero images list (only selected image variation number)
- No asset URLs or metadata
- No timestamps of when selections were made
- No completion status for different agents

### What's Missing from the Snapshot?

**Critical Missing Data**:

1. **All Generated Options** (not just selections):
   ```
   Missing: All 5 slogans that were presented
   Current: Only the 1 selected slogan
   Impact: Can't recall "What were the other slogan options?"
   ```

2. **Persona Details**:
   ```
   Missing: 3 CustomerPersona objects with pain points, motivations, usage context
   Current: Nothing about personas
   Impact: Can't recall "Who was Marcus the Urban Runner?"
   ```

3. **Asset Metadata**:
   ```
   Missing: Image URLs, descriptions, scores, variations
   Current: Only variation number
   Impact: Can't recall "What did variation 2 look like?"
   ```

4. **Agent Execution History**:
   ```
   Missing: Which agents ran, when, what they produced
   Current: Only final state
   Impact: Can't recall "When did we generate the video?"
   ```

5. **Critique/Revision History**:
   ```
   Missing: Why images were regenerated, what issues were found
   Current: Nothing
   Impact: Can't recall "Why did we reject the first batch of images?"
   ```

---

## SECTION 6: Root Cause Analysis

### Why Is Memory Bank Only Saving "Junk" Info?

**Root Cause**: **Architectural Mismatch Between ADK's Event Model and Memory Bank's Filter**

#### The Problem:

1. **ADK's Design Philosophy**:
   - ADK treats function calls/responses as "execution metadata"
   - Conversational content (text/audio/images) goes in `text`/`inline_data`/`file_data` parts
   - Tool results go in `function_response` parts
   - This separation is intentional for the ADK's execution model

2. **Memory Bank's Filter Philosophy**:
   - Memory Bank assumes it's storing "conversational content"
   - It filters out function calls/responses because they're "execution details"
   - Quote from `memory_service.py` line 216: `# Note: function_call parts are intentionally filtered out by ADK`

3. **The Mismatch**:
   ```
   AI Agency Data Flow:
   User says "Create slogans"
       → create_campaign_strategy() executes
       → Returns 5 slogans + 3 personas [STRUCTURED DATA]
       → Stored as function_response part
       → Memory Bank filters it out ❌

   What Memory Bank Expects:
   User says "Create slogans"
       → Agent says "Here are 5 slogans: ..." [TEXT]
       → Stored as text part
       → Memory Bank saves it ✅
   ```

#### Why the Current Workaround Is Insufficient:

The Project State Snapshot (line 1914) is a **band-aid**, not a solution:

```python
# What it does:
summary = """[PROJECT STATE SNAPSHOT]
Product: Aura
Selected Slogan: "Step Into Your Aura"
Hero Image: Selected (variation 2)
"""

# What it's missing:
- The actual 5 slogans that were generated
- The 3 personas with their pain points and motivations
- The 4 hero images with their descriptions and scores
- Why the user selected variation 2 instead of 1, 3, or 4
- When each agent executed
- What the critique system said
```

**The snapshot is like saving a screenshot of the final score instead of recording the entire game.**

#### The "Junk" Info Being Saved:

What the user calls "junk" is actually the **conversational metadata**:
- "Tell me more about your product" → "It's a smart sneaker with a glowing sole"
- "Should I create slogans?" → "Yes, let's see the slogans"
- "Which image do you prefer?" → "I like variation 2"

This **is** useful for conversational context, but it's missing **all the actual creative work** (slogans, personas, images, videos, etc.).

---

## SECTION 7: Recommendations

### Option 1: Inject Tool Results as Text (Quick Fix)

**Implementation**: After each tool execution, manually add a text event to the session with the structured data serialized as markdown/text.

**Example**:
```python
# In create_campaign_strategy() tool (line 573):
tool_result = {
    "success": True,
    "slogans": ["Slogan 1", "Slogan 2", ...],
    "personas": [...]
}

# NEW: Add text summary to session for Memory Bank
summary_text = f"""
Strategy Agent Results:

SLOGANS:
1. {slogans[0]}
2. {slogans[1]}
3. {slogans[2]}
4. {slogans[3]}
5. {slogans[4]}

PERSONAS:
1. {personas[0].name} ({personas[0].age_range})
   - Pain Points: {', '.join(personas[0].pain_points)}
   - Motivations: {', '.join(personas[0].motivations)}
...
"""

if hasattr(create_campaign_strategy, '_session'):
    from google.adk.events import Event
    memory_event = Event(
        author="model",
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=summary_text)]
        )
    )
    await session_service.append_event(session, memory_event)

return validate_tool_result(tool_result)
```

**Pros**:
- ✅ Quick to implement
- ✅ Works with current Memory Bank filter
- ✅ Semantic search will work on text descriptions

**Cons**:
- ❌ Duplicates data (tool result + text summary)
- ❌ Loses structured format (JSON → text)
- ❌ Manual serialization needed for each tool
- ❌ Image URLs/base64 would be truncated in text format

---

### Option 2: Extend Memory Bank Filter (Medium Effort)

**Implementation**: Modify `memory_service.py` to accept function_response parts and extract structured data.

**Example**:
```python
# In memory_service.py, line 217:
has_valid_data = any(
    hasattr(part, 'text') and part.text or
    hasattr(part, 'inline_data') and part.inline_data or
    hasattr(part, 'file_data') and part.file_data or
    # NEW: Accept function responses
    (hasattr(part, 'function_response') and
     part.function_response and
     _is_meaningful_function_response(part.function_response))
)

def _is_meaningful_function_response(response):
    """Check if function response contains user-facing data."""
    # Filter out internal tool responses (like update_project_brief)
    # Keep creative outputs (slogans, images, videos, etc.)
    meaningful_tools = [
        'create_campaign_strategy',
        'generate_hero_images',
        'generate_social_video',
        'generate_audio_assets',
        'generate_landing_page'
    ]
    return response.get('name') in meaningful_tools
```

**Pros**:
- ✅ Preserves structured data format
- ✅ No duplication
- ✅ Centralizes filtering logic

**Cons**:
- ❌ Modifies ADK's intended filtering behavior
- ❌ May break if ADK Memory Bank service has server-side filtering
- ❌ Still need to handle large payloads (base64 images)

---

### Option 3: Hybrid Approach (Recommended)

**Implementation**: Combine text summaries for semantics + structured storage in Redis.

**Architecture**:
```
Tool Execution
    ↓
├─ Return structured result to ADK (function_response)
├─ Broadcast to frontend (WebSocket)
├─ Save to Redis (persistent storage) ← NEW
└─ Add text summary to session (Memory Bank)

Memory Bank Search Results
    ↓
Include pointer to Redis: "See full details at redis://brief:{project_id}"
```

**Example**:
```python
# In create_campaign_strategy():

# 1. Execute agent
result = await orchestrator.execute_agent("strategy", task, project_id)

# 2. Store full structured data in Redis
await redis_client.store_agent_output(
    project_id=project_id,
    agent_id="strategy",
    output=result,
    timestamp=datetime.now()
)

# 3. Add searchable text summary to session for Memory Bank
summary = f"""
[STRATEGY OUTPUT - {project_id}]
Generated 5 slogans: {', '.join(result['slogans'])}
Created 3 personas: {', '.join([p['name'] for p in result['personas']])}
Full details: redis://agent_outputs:{project_id}:strategy
"""
# ... append to session

# 4. Return to ADK
return validate_tool_result(result)
```

**Pros**:
- ✅ Best of both worlds: semantic search + structured storage
- ✅ Memory Bank can reference full data via pointers
- ✅ No data duplication in Memory Bank
- ✅ Structured data queryable via Redis
- ✅ Doesn't modify ADK's filtering logic

**Cons**:
- ⚠️ More complex architecture
- ⚠️ Need to implement Redis storage layer
- ⚠️ Search results require follow-up Redis queries

---

### Option 4: Post-Process Memory Bank Queries (Augmentation)

**Implementation**: When `load_memory` tool is called, augment results with Redis data.

**Example**:
```python
# In load_memory tool:
async def load_memory(query: str, user_id: str) -> Dict[str, Any]:
    # 1. Search Memory Bank (gets text summaries)
    memories = await memory_service.search_memory(query, user_id)

    # 2. Extract project IDs from memories
    project_ids = extract_project_ids(memories)

    # 3. Fetch full structured data from Redis for those projects
    for project_id in project_ids:
        brief = await redis_client.get_project_brief(project_id)
        agent_outputs = await redis_client.get_agent_outputs(project_id)
        # ... attach to memory results

    return {
        "memories": memories,
        "full_project_data": {...}  # Structured data
    }
```

**Pros**:
- ✅ Doesn't change persistence logic
- ✅ Only loads full data when needed (efficient)
- ✅ Keeps Memory Bank simple (text-only)

**Cons**:
- ❌ Doesn't solve the persistence problem
- ❌ Relies on Redis TTL matching Memory Bank retention
- ❌ Complex query augmentation logic

---

## Summary & Next Steps

### The Core Issue:
Memory Bank is working as designed - it's saving conversational text. The problem is that **structured creative outputs (slogans, images, personas) are in function_response parts that Memory Bank intentionally filters out**.

### Current State:
- ✅ Conversational dialogue is saved
- ✅ User selections (text format) are saved
- ✅ Project state snapshots (high-level) are saved
- ❌ Tool results (slogans, personas, images) are filtered out
- ❌ Agent outputs (videos, audio, landing pages) are filtered out
- ❌ Critique/revision history is lost

### Recommended Solution:
**Option 3 (Hybrid Approach)**:
1. Add text summaries of tool results to session (for Memory Bank semantic search)
2. Store full structured data in Redis (for precise retrieval)
3. Include Redis pointers in Memory Bank summaries
4. When loading memory, augment with Redis data

### Implementation Priority:
1. **High Priority**: Add text summaries for `create_campaign_strategy` and `generate_hero_images` (most critical for user experience)
2. **Medium Priority**: Store agent outputs in Redis with project_id keys
3. **Low Priority**: Augment `load_memory` to fetch full data from Redis

### Code Locations to Modify:
1. `/Users/chuancc/mywork/ai/ai-agency/backend/app/services/gemini_live_adk.py` - Tool functions (lines 401-1041)
2. `/Users/chuancc/mywork/ai/ai-agency/backend/app/services/redis_client.py` - Add agent output storage methods
3. `/Users/chuancc/mywork/ai/ai-agency/backend/app/services/gemini_live_adk.py` - Add helper for text summary injection (like `add_memory_summary` at line 324)
