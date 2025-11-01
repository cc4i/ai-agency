# End-to-End Testing Plan - Aura Smart Sneaker Demo Flow

## Overview

This document outlines the comprehensive end-to-end testing strategy for the complete AI Agency demo flow, from welcome screen through campaign completion (handoff → launch party).

**Objective**: Verify the complete 9-minute "Aura Smart Sneaker" campaign flow works flawlessly from start to finish.

---

## Testing Strategy

### Test Levels

```
┌─────────────────────────────────────────┐
│ Level 1: Component Tests                │
│ - Individual agent outputs              │
│ - UI components                         │
│ - WebSocket connections                 │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Level 2: Integration Tests              │
│ - Agent orchestration                   │
│ - Producer logic                        │
│ - Event bus                             │
│ - Brief synchronization                 │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Level 3: E2E Tests (This Document)      │
│ - Complete demo flow                    │
│ - User journey simulation               │
│ - All agents + UI integrated            │
└─────────────────────────────────────────┘
```

---

## E2E Test Scenarios

### Scenario 1: Happy Path - Complete Demo Flow (Primary)

**Test ID**: `E2E-001`
**Duration**: ~9 minutes
**Mode**: Automated with pre-configured selections

#### Test Setup

```bash
# 1. Seed demo data
uv run python scripts/seed_demo_data.py --campaign=aura

# 2. Start backend (Redis already running)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Start frontend (separate terminal)
cd frontend && npm run dev

# 4. Verify health
curl http://localhost:8000/health
```

**Note**: Redis is assumed to be already running as an existing service.

#### Test Steps

| Step | Action | Expected Result | Validation |
|------|--------|-----------------|------------|
| **PHASE 1: HANDOFF** | | | |
| 1.1 | Navigate to http://localhost:3000 | Welcome screen displays | ✓ "Welcome, Creative Director" visible<br>✓ Microphone icon present<br>✓ CTA: "Let's get started" |
| 1.2 | Simulate voice: "Let's get started" | Producer introduction | ✓ Voice + text response<br>✓ Sketch image displays<br>✓ Project Brief panel appears |
| 1.3 | Producer presents campaign plan | 5-phase plan visible | ✓ All 5 phases listed<br>✓ Agent names shown<br>✓ Plan added to Project Brief |
| 1.4 | Simulate voice: "Yes, task the Strategy Agent" | Plan approved | ✓ Producer confirms<br>✓ Strategy Agent status: "working" |
| **PHASE 2: AGENCY HUB** | | | |
| 2.1 | Strategy Agent executes | Thinking animation | ✓ Pulsing dots visible<br>✓ Status bar shows "Strategy Agent working"<br>✓ Project Brief shows 🟡 status |
| 2.2 | Wait for Strategy completion | 3 personas + 5 slogans | ✓ Exactly 3 personas displayed<br>✓ Exactly 5 slogans listed<br>✓ Project Brief updated ✅<br>✓ Producer announces completion |
| 2.3 | Simulate voice: "I like 'Run on light'" | Slogan selected | ✓ Brief updated with selected slogan<br>✓ Producer confirms selection<br>✓ Art Director notified |
| 2.4 | Art Director executes | Thinking animation | ✓ Art Director status: "working"<br>✓ Selected slogan visible in brief |
| 2.5 | Wait for Art Director completion | 4 hero images | ✓ Exactly 4 images in grid<br>✓ All images have URLs<br>✓ Images display correctly |
| 2.6 | Simulate voice: "Image 2" | Image selected | ✓ Brief updated with selected image<br>✓ Producer announces proactive collaboration<br>✓ Video/Audio/Web agents notified |
| 2.7 | Audio Agent makes suggestion | Proactive suggestion | ✓ Suggestion UI appears<br>✓ "uplifting, futuristic, electronic beat" mentioned<br>✓ Sample playback option |
| 2.8 | Parallel agents execute | 3 agents working | ✓ Video Producer: 🟡<br>✓ Audio Team: 🟡<br>✓ Web Dev: 🟡<br>✓ All running simultaneously |
| 2.9 | Video Producer completes (first draft) | Video ready for critique | ✓ Video URL returned<br>✓ 15-second duration<br>✓ Producer begins critique |
| 2.10 | Producer critique triggers | Revision request | ✓ Critique message: "missing glowing sole"<br>✓ Revision instructions sent<br>✓ Video status: "Revision 1" |
| 2.11 | Video Producer revises | Revised video | ✓ New video URL<br>✓ Producer approves<br>✓ Video status: ✅ |
| 2.12 | Audio Team completes | 3 audio assets | ✓ Jingle URL<br>✓ Podcast ad URL<br>✓ Transcription text<br>✓ Audio status: ✅ |
| 2.13 | Web Dev completes | Landing page code | ✓ HTML returned<br>✓ CSS returned<br>✓ JavaScript returned<br>✓ Live preview renders<br>✓ Web Dev status: ✅ |
| **PHASE 3: LAUNCH PARTY** | | | |
| 3.1 | All agents complete | Completion announcement | ✓ Producer announces completion<br>✓ "Campaign complete" message |
| 3.2 | Launch Party screen displays | Asset summary grid | ✓ All 5 agent outputs visible<br>✓ Strategy: 3 personas + 5 slogans<br>✓ Art: 4 images<br>✓ Video: 15s clip<br>✓ Audio: 3 assets<br>✓ Web: Code + preview |
| 3.3 | Project Brief final state | Complete brief | ✓ All fields populated<br>✓ Selected slogan visible<br>✓ Selected image visible<br>✓ All assets linked |

#### Assertions

```python
# Test assertions pseudocode

async def test_e2e_complete_demo_flow():
    """E2E-001: Complete Aura Smart Sneaker demo flow."""

    # Setup
    session_id = await create_session()
    project_id = await create_project()
    demo = AuraDemoFlow(session_id, project_id)

    # Execute with pre-configured selections
    user_selections = {
        "slogan": "Run on light",
        "image": 1  # Image #2 (index 1)
    }

    results = await demo.run_demo(user_selections)

    # Phase 1 Assertions
    assert results["welcome_completed"] == True
    assert results["plan_presented"] == True
    assert results["plan_approved"] == True

    # Phase 2 Assertions - Strategy
    assert "strategy" in results
    assert len(results["strategy"]["personas"]) == 3
    assert len(results["strategy"]["slogans"]) == 5
    assert "Run on light" in results["strategy"]["slogans"]

    # Phase 2 Assertions - Art Director
    assert "art" in results
    assert len(results["art"]["images"]) == 4
    for image in results["art"]["images"]:
        assert image["url"] is not None
        assert image["url"].startswith("http")

    # Phase 2 Assertions - Video (with critique)
    assert "video_producer" in results
    assert results["video_producer"]["revision_number"] == 1  # Revised once
    assert results["video_producer"]["duration_seconds"] == 15
    assert "glowing sole" in results["video_producer"]["critique_notes"].lower()

    # Phase 2 Assertions - Audio
    assert "audio_team" in results
    assert "jingle" in results["audio_team"]
    assert "podcast_ad" in results["audio_team"]
    assert "transcription" in results["audio_team"]
    assert results["audio_team"]["jingle"]["duration_seconds"] > 0

    # Phase 2 Assertions - Web Dev
    assert "web_dev" in results
    assert results["web_dev"]["html"] is not None
    assert results["web_dev"]["css"] is not None
    assert results["web_dev"]["javascript"] is not None
    assert "Run on light" in results["web_dev"]["html"]

    # Phase 3 Assertions - Completion
    assert results["campaign_completed"] == True

    # Project Brief Assertions
    brief = await redis_client.get_project_brief(project_id)
    assert brief.selected_slogan == "Run on light"
    assert brief.selected_image is not None
    assert brief.status == "completed"
    assert len(brief.completed_assets) == 5

    print("✅ E2E-001: Complete demo flow PASSED")
```

---

### Scenario 2: User-Driven Interactive Demo

**Test ID**: `E2E-002`
**Duration**: ~12 minutes (includes user think time)
**Mode**: Manual testing with real voice input

#### Test Steps

Same as E2E-001, but with actual voice input through microphone instead of simulated selections.

#### Additional Validations
- ✓ Microphone capture working
- ✓ Voice-to-text transcription accurate
- ✓ Gemini Live responding with natural voice
- ✓ Audio playback smooth and clear
- ✓ No audio lag or echo
- ✓ Turn-taking works correctly

---

### Scenario 3: Error Handling - Agent Failure

**Test ID**: `E2E-003`
**Objective**: Verify graceful degradation when an agent fails

#### Test Steps

1. Start demo flow normally
2. Force Strategy Agent to fail (simulate API error)
3. Verify error handling

#### Expected Behavior

```
Producer: "I apologize, but our Strategy Agent encountered an issue.
           Let me try again..."

[Automatic retry - max 2 attempts]

If retry fails:
Producer: "I'm having trouble connecting to our Strategy Agent.
           Would you like to try a different approach or restart?"
```

#### Assertions

```python
async def test_e2e_agent_failure_recovery():
    """E2E-003: Agent failure recovery."""

    # Setup: Inject failure in Strategy Agent
    with mock.patch('app.agents.strategy.StrategyAgent.execute',
                    side_effect=Exception("API Error")):

        demo = AuraDemoFlow(session_id, project_id)

        with pytest.raises(AgentExecutionError) as exc_info:
            await demo.run_demo()

        # Verify retry attempted
        assert exc_info.value.retry_count == 2

        # Verify error message sent to user
        messages = await get_conversation_messages(session_id)
        error_msg = messages[-1]
        assert "encountered an issue" in error_msg.lower()

    print("✅ E2E-003: Error handling PASSED")
```

---

### Scenario 4: Critique Loop - Multiple Revisions

**Test ID**: `E2E-004`
**Objective**: Test critique system with maximum revisions

#### Test Setup

Force Video Producer to fail critique twice, then pass on third attempt.

#### Expected Behavior

- Revision 1: Fails critique → Revision requested
- Revision 2: Fails critique → Revision requested
- Max revisions reached → Escalate to user

```
Producer: "I've requested two revisions, but the video still doesn't
           meet our brief requirements. Would you like to:
           1. Accept the current version
           2. Provide manual feedback to the agent
           3. Skip the video for now"
```

#### Assertions

```python
async def test_e2e_max_revisions():
    """E2E-004: Maximum revision limit."""

    # Mock critique to always fail
    def failing_critique(result, brief):
        return CritiqueResult(
            status="REVISE",
            issues=["Missing element"],
            revision_instructions="Add missing element"
        )

    with mock.patch('app.producer.critique.CritiqueSystem.evaluate',
                    side_effect=failing_critique):

        demo = AuraDemoFlow(session_id, project_id)
        results = await demo.run_demo()

        # Verify max revisions enforced
        assert results["video_producer"]["revision_number"] == 2
        assert results["video_producer"]["escalated_to_user"] == True

    print("✅ E2E-004: Max revisions PASSED")
```

---

### Scenario 5: Proactive Collaboration Verification

**Test ID**: `E2E-005`
**Objective**: Verify agents collaborate proactively without explicit user commands

#### Test Steps

1. Run demo until image selection
2. Verify autonomous agent notifications
3. Confirm parallel execution

#### Assertions

```python
async def test_e2e_proactive_collaboration():
    """E2E-005: Proactive agent collaboration."""

    demo = AuraDemoFlow(session_id, project_id)

    # Subscribe to event bus
    events = []
    async def capture_events(event):
        events.append(event)

    event_bus.subscribe("agent_notified", capture_events)

    # Run demo
    await demo.run_demo()

    # Verify event-driven notifications
    assert any(e["agent_id"] == "video_producer" and
               e["trigger"] == "image_selected"
               for e in events)

    assert any(e["agent_id"] == "web_dev" and
               e["trigger"] == "image_selected"
               for e in events)

    # Verify Audio Agent proactive suggestion
    assert any(e["type"] == "proactive_suggestion" and
               e["agent_id"] == "audio_team"
               for e in events)

    # Verify parallel execution timing
    # Video, Audio, Web should start within 5s of each other
    video_start = next(e["timestamp"] for e in events
                       if e["agent_id"] == "video_producer")
    audio_start = next(e["timestamp"] for e in events
                       if e["agent_id"] == "audio_team")
    web_start = next(e["timestamp"] for e in events
                     if e["agent_id"] == "web_dev")

    assert abs(video_start - audio_start) < 5.0
    assert abs(audio_start - web_start) < 5.0

    print("✅ E2E-005: Proactive collaboration PASSED")
```

---

### Scenario 6: Real-time Brief Synchronization

**Test ID**: `E2E-006`
**Objective**: Verify Project Brief updates in real-time across all components

#### Test Steps

1. Monitor WebSocket events
2. Verify brief updates propagate to frontend
3. Confirm agents receive updated context

#### Assertions

```python
async def test_e2e_brief_synchronization():
    """E2E-006: Real-time Project Brief sync."""

    # Connect to WebSocket
    ws_client = WebSocketClient()
    await ws_client.connect(f"ws://localhost:8000/ws/project/{project_id}")

    brief_updates = []

    async def capture_brief_updates():
        async for message in ws_client:
            if message["type"] == "brief_updated":
                brief_updates.append(message)

    asyncio.create_task(capture_brief_updates())

    # Run demo
    demo = AuraDemoFlow(session_id, project_id)
    await demo.run_demo()

    # Verify brief updates
    assert len(brief_updates) >= 4  # Plan, slogan, image, completion

    # Verify each update contains changed fields
    slogan_update = next(u for u in brief_updates
                         if "selected_slogan" in u["changed_fields"])
    assert slogan_update["brief"]["selected_slogan"] == "Run on light"

    # Verify final state
    final_brief = await redis_client.get_project_brief(project_id)
    assert final_brief.status == "completed"
    assert len(final_brief.completed_assets) == 5

    print("✅ E2E-006: Brief synchronization PASSED")
```

---

## Performance Benchmarks

### Expected Timing (with real API calls)

| Phase | Component | Expected Duration | Max Acceptable |
|-------|-----------|-------------------|----------------|
| 1 | Welcome & Introduction | 30s | 60s |
| 1 | Plan Presentation | 20s | 40s |
| 2 | Strategy Agent | 30s | 60s |
| 2 | Art Director (4 images) | 60s | 120s |
| 2 | Video Producer (first) | 45s | 90s |
| 2 | Video Producer (revision) | 45s | 90s |
| 2 | Audio Team (parallel) | 40s | 80s |
| 2 | Web Dev (parallel) | 30s | 60s |
| 3 | Launch Party Screen | 5s | 10s |
| **Total** | **Complete Flow** | **~7-9 min** | **12 min** |

### Performance Test

```python
async def test_e2e_performance_benchmarks():
    """E2E-007: Performance benchmarks."""

    start_time = time.time()

    demo = AuraDemoFlow(session_id, project_id)
    results = await demo.run_demo()

    total_duration = time.time() - start_time

    # Overall timing
    assert total_duration < 720  # 12 minutes max

    # Individual agent timing
    assert results["strategy"]["duration"] < 60
    assert results["art"]["duration"] < 120
    assert results["video_producer"]["duration"] < 180  # Includes revision
    assert results["audio_team"]["duration"] < 80
    assert results["web_dev"]["duration"] < 60

    print(f"✅ E2E-007: Performance PASSED (Total: {total_duration:.1f}s)")
```

---

## Test Implementation

### Test File Structure

```
backend/tests/e2e/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── test_complete_demo.py    # E2E-001: Happy path
├── test_interactive_demo.py # E2E-002: User-driven
├── test_error_handling.py   # E2E-003: Agent failures
├── test_critique_loop.py    # E2E-004: Revisions
├── test_collaboration.py    # E2E-005: Proactive
├── test_brief_sync.py       # E2E-006: Real-time sync
├── test_performance.py      # E2E-007: Benchmarks
└── fixtures/
    ├── mock_agents.py
    ├── test_data.py
    └── websocket_client.py
```

### Pytest Configuration

```python
# backend/tests/e2e/conftest.py

import pytest
import asyncio
from app.main import app
from app.services.redis_client import redis_client
from fastapi.testclient import TestClient

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def clean_redis():
    """Clean Redis test data before each test.

    Note: Redis service is already running, we just clean test data.
    """
    await redis_client.connect()
    # Only flush test database, not production data
    await redis_client.client.flushdb()
    yield
    await redis_client.disconnect()

@pytest.fixture(scope="function")
async def test_session():
    """Create test session."""
    from app.main import create_session, create_project

    session_data = await create_session()
    project_data = await create_project()

    return {
        "session_id": session_data["session_id"],
        "project_id": project_data["project_id"]
    }

@pytest.fixture(scope="function")
def seed_demo_data():
    """Seed Aura Smart Sneaker demo data."""
    import subprocess
    subprocess.run([
        "python", "scripts/seed_demo_data.py",
        "--campaign=aura"
    ])
```

### Running E2E Tests

```bash
# Run all E2E tests
uv run pytest backend/tests/e2e/ -v

# Run specific test
uv run pytest backend/tests/e2e/test_complete_demo.py::test_e2e_complete_demo_flow -v

# Run with coverage
uv run pytest backend/tests/e2e/ --cov=app --cov-report=html

# Run with performance profiling
uv run pytest backend/tests/e2e/ --durations=10

# Run in parallel (faster)
uv run pytest backend/tests/e2e/ -n auto
```

---

## Mock vs Real API Tests

### Mock Mode (Fast, Local)

```python
# Use for rapid development and CI/CD
@pytest.fixture
def mock_google_ai():
    """Mock Google AI API responses."""
    with mock.patch('app.agents.strategy.gemini_pro_client') as m:
        m.generate_content.return_value = MOCK_STRATEGY_OUTPUT
        yield m
```

**Advantages:**
- Fast execution (< 60s for full suite)
- No API costs
- Deterministic results
- No network dependency

**Disadvantages:**
- Doesn't test real API integration
- May miss API-specific issues

### Real API Mode (Slow, Integration)

```python
# Use for pre-production validation
@pytest.mark.integration
async def test_e2e_real_apis():
    """Test with real Google AI APIs."""
    # Uses actual Gemini, Imagen, Veo, Lyria
    # Requires API keys
    # Takes 9-12 minutes
    pass
```

**Advantages:**
- Tests real API behavior
- Validates prompts and parameters
- Catches quota/rate limit issues

**Disadvantages:**
- Slow (9-12 min per test)
- Costs money (API usage)
- Non-deterministic outputs

### Recommended Strategy

```bash
# Daily development: Mock mode
uv run pytest backend/tests/e2e/ --mock

# Pre-commit: Quick smoke test
uv run pytest backend/tests/e2e/test_complete_demo.py --mock

# Nightly CI: Real APIs
uv run pytest backend/tests/e2e/ --real-apis --maxfail=1

# Pre-release: Full validation
uv run pytest backend/tests/e2e/ --real-apis --count=3  # Run 3x
```

---

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/e2e-tests.yml

name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM

jobs:
  e2e-mock:
    runs-on: ubuntu-latest

    # Note: For CI, we still need Redis service container
    # For local development, use existing Redis service
    services:
      redis:
        image: redis:latest
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python 3.13
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install dependencies
        run: |
          cd backend
          uv sync --dev

      - name: Run E2E tests (Mock)
        run: |
          cd backend
          uv run pytest tests/e2e/ --mock -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  e2e-real-apis:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'  # Only nightly

    steps:
      # ... similar setup ...

      - name: Run E2E tests (Real APIs)
        env:
          GOOGLE_APPLICATION_CREDENTIALS: ${{ secrets.GCP_CREDENTIALS }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          cd backend
          uv run pytest tests/e2e/ --real-apis -v --maxfail=1
```

---

## Manual QA Checklist

For final pre-release validation, run through this manual checklist:

### Visual/UX Checks

- [ ] Microphone icon glows smoothly
- [ ] Thinking animation pulses correctly
- [ ] Project Brief updates with smooth transitions
- [ ] Image gallery displays in 2x2 grid
- [ ] Video player controls work
- [ ] Audio player controls work
- [ ] Code/preview split screen renders correctly
- [ ] Launch Party screen displays all assets
- [ ] No visual glitches or layout issues

### Audio Checks

- [ ] Microphone capture is clear
- [ ] Producer voice is natural and clear
- [ ] No audio lag or echo
- [ ] Turn-taking works smoothly
- [ ] Background noise doesn't trigger false inputs
- [ ] Audio sample playback works
- [ ] Jingle/podcast ad playback works

### Content Quality Checks

- [ ] Strategy personas are realistic and detailed
- [ ] Slogans are creative and on-brand
- [ ] Images match Tokyo neon theme
- [ ] Glowing sole is visible in images
- [ ] Video shows product clearly
- [ ] Video revision improves quality
- [ ] Audio quality is professional
- [ ] Landing page code is clean and functional

### Error Handling Checks

- [ ] Graceful handling of network issues
- [ ] Clear error messages to user
- [ ] Retry logic works
- [ ] Timeout handling works
- [ ] No silent failures

---

## Success Criteria

The E2E testing is successful when:

1. ✅ All automated tests pass (E2E-001 through E2E-007)
2. ✅ Complete flow executes in < 12 minutes
3. ✅ All 5 agents generate quality outputs
4. ✅ Critique loop triggers correctly
5. ✅ Proactive collaboration verified
6. ✅ No errors or crashes
7. ✅ Manual QA checklist 100% complete
8. ✅ Performance benchmarks met
9. ✅ Real API test passes at least 3/3 times
10. ✅ User experience is smooth and impressive

---

## Next Steps After Testing

Once E2E tests pass:

1. **Record demo video** - Capture successful run for marketing
2. **Document known issues** - Any quirks or limitations
3. **Prepare "Show Me the API"** - Code reveal feature
4. **User acceptance testing** - Get feedback from real users
5. **Optimize performance** - Tune based on benchmark data
6. **Deploy to staging** - Test in production-like environment

---

## Test Execution Timeline

### Week 1: Test Implementation
- Day 1-2: Implement E2E-001 (happy path)
- Day 3: Implement E2E-002 (interactive)
- Day 4: Implement E2E-003, E2E-004 (error handling)
- Day 5: Implement E2E-005, E2E-006 (collaboration, sync)

### Week 2: Validation & Refinement
- Day 1: Implement E2E-007 (performance)
- Day 2: Run full mock suite, fix issues
- Day 3: Run real API tests, fix issues
- Day 4: Manual QA checklist
- Day 5: Final validation, documentation

---

**Document Version**: 1.0
**Last Updated**: 2025-01-01
**Status**: Ready for Implementation
