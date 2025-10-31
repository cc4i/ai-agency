# Agent Workflow State Analysis

## Executive Summary

**Current Status**: ❌ **State continuity NOT implemented**

The backend tracks project state in Redis, but:
- Gemini Live is NOT aware of existing state
- Agents re-execute even when work is already done
- No logic to resume from last incomplete step
- System prompt doesn't mention state checking

## Current Implementation

### 1. State Model ✅ (EXISTS)
**File**: `app/models/brief.py:15-62`

```python
class ProjectBrief(BaseModel):
    # Campaign basics
    product_name: str
    product_category: str
    theme: str
    key_features: List[str]
    brand_tone: str
    target_market: str

    # Strategy outputs ← STATE TRACKED
    personas: List[CustomerPersona] = []
    slogans: List[str] = []
    selected_slogan: Optional[str] = None

    # Art outputs ← STATE TRACKED
    hero_images: List[ImageAsset] = []
    selected_image: Optional[ImageAsset] = None

    # Asset tracking ← STATE TRACKED
    completed_assets: Dict[str, Any] = {}  # {agent_id: asset}

    # Status
    status: str = "planning"  # planning, executing, completed
```

**State fields available**:
- ✅ `slogans` - List of generated slogans
- ✅ `selected_slogan` - User's choice
- ✅ `hero_images` - List of generated images
- ✅ `selected_image` - User's choice
- ✅ `completed_assets` - All agent outputs

### 2. State Persistence ✅ (EXISTS)
**File**: `app/services/redis_client.py`

```python
# Save/load brief from Redis
await redis_client.save_project_brief(brief)  # Line 99-114
brief = await redis_client.get_project_brief(project_id)  # Line 116-165

# Update brief with new data
await redis_client.update_project_brief(project_id, updates)  # Line 167-190

# Store agent results
await redis_client.store_agent_result(agent_id, task_id, result)  # Line 225-241
result = await redis_client.get_agent_result(agent_id, task_id)  # Line 243-264
```

**Redis schema**:
```
project:{project_id}:brief -> Hash (all ProjectBrief fields)
agent:{agent_id}:result:{task_id} -> Hash (agent output)
```

### 3. Brief Initialization ✅ (EXISTS)
**File**: `app/services/gemini_live.py:477-518`

```python
async def _initialize_project_brief(self) -> None:
    # Try to load existing brief
    brief = await redis_client.get_project_brief(self.project_id)

    if not brief:
        # Create new brief if doesn't exist
        brief = ProjectBrief(...)
        await redis_client.save_project_brief(brief)
    else:
        self._log("info", f"📋 Loaded existing project brief for {self.project_id}")

    # Send brief to frontend
    await self.frontend_ws.send_json({
        "type": "brief_init",
        "data": {"brief": brief.model_dump(mode="json")},
    })
```

**Good**: Brief IS loaded from Redis on session start
**Bad**: Gemini is NOT told about existing state

### 4. Brief Updates After Agent Execution ✅ (EXISTS)
**File**: `app/services/gemini_live.py:1173-1239`

```python
async def _update_brief_from_agent_result(...):
    brief = await redis_client.get_project_brief(self.project_id)

    if agent_id == "strategy":
        # Update brief with strategy results
        if task.get("product_name") and not brief.product_name:
            updates["product_name"] = task.get("product_name")

    elif agent_id == "art_director":
        # Update selected slogan
        if task.get("slogan") and brief.selected_slogan != task.get("slogan"):
            updates["selected_slogan"] = task.get("slogan")

    # Send brief_update to frontend
    await self.frontend_ws.send_json({
        "type": "brief_update",
        "data": {
            "brief": brief_updated.model_dump(mode="json"),
            "changed_fields": changed_fields,
        },
    })
```

**Good**: Brief is updated when agents complete
**Bad**: Updates are minimal (only some fields)

## Missing Implementation ❌

### 1. State-Aware System Prompt ❌
**File**: `app/services/gemini_live.py:379-475`

**Current prompt** (lines 386-475):
```
You are the Executive Producer...

PHASE 1: GATHER INFORMATION
PHASE 2: CREATE STRATEGY (Use create_campaign_strategy)
- Call this IMMEDIATELY when user explicitly asks for slogans/personas/strategy

PHASE 3: CREATE VISUALS (Use generate_hero_images)
- ONLY call when ALL of these are true:
  1. Strategy Agent has completed and you have slogans
  2. User has EXPLICITLY CHOSEN one slogan
  3. User REQUESTS images/visuals

PHASE 4: CREATE VIDEO (Use generate_social_video)
- ONLY call when ALL of these are true:
  1. Art Director has completed and you have hero images
  2. User has EXPLICITLY CHOSEN one image
  3. User REQUESTS a video
```

**Problem**:
- ❌ NO mention of checking existing state
- ❌ NO instruction to skip if already done
- ❌ NO guidance on resuming workflow
- ❌ Assumes linear progression (always start from Phase 1)

**Example failure scenario**:
```
User: "Can you create slogans?"
Gemini: Calls create_campaign_strategy()  ← WRONG if slogans already exist
```

### 2. State Checking in Function Execution ❌
**File**: `app/services/gemini_live.py:1540-1843`

**Current implementation**:
```python
elif function_name == "create_campaign_strategy":
    # Get current brief to fill in missing parameters
    brief = await redis_client.get_project_brief(self.project_id)

    # Build task from args, with fallback to project brief
    task = {
        "product_name": args.get("product_name") or brief.product_name,
        "product_category": args.get("product_category") or brief.product_category,
        ...
    }

    # Execute agent immediately
    asyncio.create_task(
        self._execute_agent_with_result_publishing(
            orchestrator=orchestrator,
            agent_id="strategy",
            task=task,
            ...
        )
    )
```

**Problem**:
- ❌ NO check if `brief.slogans` already exists
- ❌ NO check if Strategy agent already completed
- ❌ NO option to return existing results
- ❌ Always executes agent, even if work done

**Same issue for all agents**:
- `generate_hero_images`: Doesn't check `brief.hero_images`
- `generate_social_video`: Doesn't check `completed_assets["video_producer"]`
- `generate_audio_assets`: Doesn't check `completed_assets["audio_team"]`
- `generate_landing_page`: Doesn't check `completed_assets["web_dev"]`

### 3. State Reporting to Gemini ❌

**Current**: Agents return minimal summaries
**Missing**:
- ❌ Current brief state in tool responses
- ❌ What's already completed
- ❌ What's the next logical step
- ❌ Option to use existing work vs. regenerate

### 4. Resume Logic ❌

**Current**: No logic to determine where to resume
**Missing**:
- ❌ Function to check workflow progress
- ❌ Recommendation of next step based on state
- ❌ Option to skip completed phases
- ❌ Smart defaults when user says "continue"

## Required Changes

### Change 1: Update System Prompt (HIGH PRIORITY)
**File**: `app/services/gemini_live.py:379-475`

**Add state awareness section**:
```
IMPORTANT: CHECK EXISTING STATE BEFORE EXECUTING

Before calling any agent function, YOU MUST:
1. Check the Project Brief for existing results
2. Inform the user of what already exists
3. Ask if they want to USE EXISTING or REGENERATE

Examples:

User: "Can you create slogans?"
You: "I see we already have 5 slogans from a previous session:
      1. Run Your Future
      2. Step Into Tomorrow
      3. ...

      Would you like to:
      A) Use these existing slogans and move forward
      B) Generate new slogans

      Just let me know!"

User: "Can you create images?"
You: "First, I need to know which slogan to use. I see we already have:
      - Selected slogan: 'Run Your Future'
      - 4 hero images already generated

      Would you like to:
      A) Review the existing images
      B) Generate new images with the same slogan
      C) Choose a different slogan and generate new images?"

User: "Let's continue where we left off"
You: [Check project brief state]
     "Great! Looking at our progress:
      ✅ Product brief complete
      ✅ 5 slogans generated (you selected: 'Run Your Future')
      ✅ 4 hero images created
      ❌ Video not yet created
      ❌ Landing page not yet created

      Would you like me to create a video from one of the images?"
```

### Change 2: Add State Checking Function (HIGH PRIORITY)
**File**: `app/services/gemini_live.py`

**Add new method**:
```python
async def _check_workflow_state(self) -> Dict[str, Any]:
    """
    Check current workflow state and determine next steps.

    Returns:
        {
            "has_slogans": bool,
            "slogans_count": int,
            "selected_slogan": Optional[str],
            "has_images": bool,
            "images_count": int,
            "selected_image": Optional[str],
            "completed_agents": List[str],  # ["strategy", "art_director", ...]
            "next_recommended_step": str,  # "select_slogan", "generate_images", ...
            "resume_message": str,  # User-friendly description
        }
    """
    brief = await redis_client.get_project_brief(self.project_id)
    if not brief:
        return {"next_recommended_step": "create_brief"}

    # Check strategy state
    has_slogans = len(brief.slogans) > 0
    selected_slogan = brief.selected_slogan

    # Check art state
    has_images = len(brief.hero_images) > 0
    selected_image = brief.selected_image

    # Check completed assets
    completed_agents = list(brief.completed_assets.keys())

    # Determine next step
    if not has_slogans:
        next_step = "create_strategy"
    elif not selected_slogan:
        next_step = "select_slogan"
    elif not has_images:
        next_step = "generate_images"
    elif not selected_image:
        next_step = "select_image"
    elif "video_producer" not in completed_agents:
        next_step = "generate_video"
    elif "web_dev" not in completed_agents:
        next_step = "generate_landing_page"
    else:
        next_step = "campaign_complete"

    # Build resume message
    resume_message = f"""
    Current Progress:
    {'✅' if has_slogans else '❌'} Strategy: {len(brief.slogans)} slogans
    {'✅' if selected_slogan else '❌'} Selected: {selected_slogan or 'None'}
    {'✅' if has_images else '❌'} Images: {len(brief.hero_images)} hero images
    {'✅' if selected_image else '❌'} Selected image: {selected_image.asset_id if selected_image else 'None'}
    {'✅' if 'video_producer' in completed_agents else '❌'} Video created
    {'✅' if 'audio_team' in completed_agents else '❌'} Audio created
    {'✅' if 'web_dev' in completed_agents else '❌'} Landing page created

    Next step: {next_step}
    """

    return {
        "has_slogans": has_slogans,
        "slogans_count": len(brief.slogans),
        "slogans": brief.slogans,
        "selected_slogan": selected_slogan,
        "has_images": has_images,
        "images_count": len(brief.hero_images),
        "selected_image": selected_image.asset_id if selected_image else None,
        "completed_agents": completed_agents,
        "next_recommended_step": next_step,
        "resume_message": resume_message.strip(),
    }
```

### Change 3: Add State Check to Agent Functions (HIGH PRIORITY)
**File**: `app/services/gemini_live.py:1622-1659`

**Modify create_campaign_strategy**:
```python
elif function_name == "create_campaign_strategy":
    self._log("info", "🎯 Matched create_campaign_strategy function")

    # CHECK EXISTING STATE FIRST
    brief = await redis_client.get_project_brief(self.project_id)

    # If slogans already exist, return them instead of regenerating
    if brief and len(brief.slogans) > 0:
        self._log("info", f"📋 Found existing slogans ({len(brief.slogans)}), returning cached results")

        # Return existing strategy results
        return {
            "status": "cached",
            "message": f"Found {len(brief.slogans)} existing slogans from previous session",
            "slogans": brief.slogans,
            "personas": brief.personas,
            "note": "These are from a previous session. Ask user if they want to use these or generate new ones."
        }

    # If no existing slogans, execute agent as normal
    self._log("info", "📋 No existing slogans found, executing Strategy Agent")
    task = {...}
    asyncio.create_task(...)
```

**Same pattern for**:
- `generate_hero_images` - Check `brief.hero_images`
- `generate_social_video` - Check `completed_assets["video_producer"]`
- `generate_audio_assets` - Check `completed_assets["audio_team"]`
- `generate_landing_page` - Check `completed_assets["web_dev"]`

### Change 4: Add "Resume Workflow" Function (MEDIUM PRIORITY)
**File**: `app/services/gemini_live.py:164-377`

**Add new tool to _get_agent_tools()**:
```python
{
    "name": "check_workflow_status",
    "description": "Check current campaign progress and get recommendation for next step. Call this when user asks to 'continue', 'resume', or 'what's next'.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}
```

**Add handler**:
```python
elif function_name == "check_workflow_status":
    state = await self._check_workflow_state()
    return state
```

### Change 5: Update Brief After Strategy (MEDIUM PRIORITY)
**File**: `app/services/gemini_live.py:1173-1239`

**Expand _update_brief_from_agent_result**:
```python
if agent_id == "strategy":
    # Save slogans and personas to brief
    if "slogans" in result:
        updates["slogans"] = result.get("slogans", [])
        changed_fields.append("slogans")

    if "personas" in result:
        updates["personas"] = result.get("personas", [])
        changed_fields.append("personas")

    # Mark strategy as completed
    if "completed_assets" not in brief.completed_assets:
        brief.completed_assets = {}
    brief.completed_assets["strategy"] = {
        "slogans_count": len(result.get("slogans", [])),
        "personas_count": len(result.get("personas", [])),
    }
    updates["completed_assets"] = brief.completed_assets
    changed_fields.append("completed_assets")
```

**Same for art_director**:
```python
elif agent_id == "art_director":
    # Save images to brief
    if "images" in result:
        updates["hero_images"] = result.get("images", [])
        changed_fields.append("hero_images")

    # Mark art director as completed
    ...
```

## Implementation Priority

### Phase 1 (CRITICAL - Week 1) ✅ COMPLETED
1. ✅ Add state checking function `_check_workflow_state()` - **DONE** (lines 477-570)
2. ✅ Update system prompt with state awareness instructions - **DONE** (lines 397-437)
3. ✅ Add state checks to `create_campaign_strategy` - **DONE** (lines 1764-1813)
4. ✅ Add state checks to `generate_hero_images` - **DONE** (lines 1819-1871)
5. ✅ Expand `_update_brief_from_agent_result()` to save all outputs - **DONE** (lines 1344-1460)
6. ✅ Add `check_workflow_status` tool - **DONE** (lines 377-385, 1806-1813)
7. ⏳ Test basic resume workflow - **PENDING** (needs integration testing)

### Phase 2 (HIGH - Week 2)
6. ✅ Add state checks to remaining agents (video, audio, web)
7. ✅ Expand `_update_brief_from_agent_result` to save all outputs
8. ✅ Add `check_workflow_status` tool
9. ✅ Test full workflow with interruptions and resumes

### Phase 3 (NICE TO HAVE - Week 3)
10. Add "regenerate" option for each phase
11. Add version history for slogans/images
12. Add "compare versions" feature
13. Add workflow analytics

## Testing Scenarios

### Scenario 1: Resume After Strategy
```
Session 1:
  User: "Create slogans for smart sneakers"
  → Strategy agent creates 5 slogans
  → Session ends

Session 2 (same project_id):
  User: "Let's continue"
  Gemini: "I see we have 5 slogans from last time. Which one do you like?"
  User: "I like #3"
  → Updates selected_slogan
  → Asks if user wants images
```

### Scenario 2: Resume After Images
```
Session 1:
  → Strategy complete (slogan selected)
  → Art Director creates 4 images
  → Session ends

Session 2:
  User: "Continue"
  Gemini: "We have 4 images. Which one would you like to use for video?"
  User: "Use image #2"
  → Creates video from image #2
```

### Scenario 3: Regenerate Strategy
```
User: "I don't like these slogans, make new ones"
Gemini: [Forces re-execution of Strategy agent even though slogans exist]
```

## Success Metrics

✅ Users can resume campaigns across sessions
✅ No duplicate work (agents don't re-run if results exist)
✅ Gemini proactively offers to use existing work
✅ Users can selectively regenerate specific phases
✅ Workflow recommendations are accurate
✅ Brief state always reflects current progress

## References

- `app/models/brief.py:15-62` - ProjectBrief model
- `app/services/redis_client.py` - State persistence
- `app/services/gemini_live.py:379-475` - System prompt
- `app/services/gemini_live.py:1540-1843` - Agent function execution
- `app/services/gemini_live.py:1173-1239` - Brief update after agent completion
