# Google GenAI SDK Migration - Status Update

**Date**: 2025-10-29
**Status**: ⚠️ Package installed, context manager lifecycle issue

## ✅ Completed

### 1. Package Installation
- **`google-genai`**: v1.46.0 ✓ (NEW SDK for Vertex AI Live API)
- **`google-cloud-aiplatform`**: v1.122.0 ✓
- **`google-generativeai`**: v0.8.5 ✓ (kept for legacy agents)

### 2. Code Migration
- ✅ Updated imports to `from google import genai`
- ✅ Created `genai.Client(vertexai=True, ...)`
- ✅ Updated connection to use `LiveConnectConfig`
- ✅ Updated audio sending to use `Blob` type
- ✅ Updated response handling for SDK objects

## ⚠️ Current Issue

### Async Context Manager Lifecycle

**Error**:
```
Connection error: object _AsyncGeneratorContextManager can't be used in 'await' expression
```

**Problem** (backend/app/services/gemini_live.py:275-281):
```python
# Current code - DOESN'T WORK
session_context = self.genai_client.aio.live.connect(
    model="gemini-2.0-flash-exp",
    config=config,
)
session = await session_context.__aenter__()  # ❌ Causes error
```

**Why**: The SDK's `aio.live.connect()` returns an async context manager designed for use with `async with`:

```python
# How SDK expects to be used (from docs)
async with client.aio.live.connect(model=model, config=config) as session:
    # Use session here
    await session.send(...)
    async for response in session.receive():
        ...
```

**The challenge**: Our WebSocket architecture needs a long-lived session object that spans the entire connection lifecycle, but the SDK expects short-lived `async with` blocks.

## Possible Solutions

### Option 1: Refactor to Use `async with` (Recommended)

Restructure the connection method to properly use the context manager:

```python
async def connect(self, frontend_websocket: WebSocket) -> None:
    await frontend_websocket.accept()
    self.frontend_ws = frontend_websocket

    try:
        # Use async with to properly manage the session lifecycle
        async with self.genai_client.aio.live.connect(
            model="gemini-2.0-flash-exp",
            config=config
        ) as session:
            self.gemini_session = session
            self.is_connected = True

            # Run bidirectional streaming INSIDE the context
            await asyncio.gather(
                self._handle_frontend_to_gemini(),
                self._handle_gemini_to_frontend(),
                return_exceptions=True,
            )
    except Exception as e:
        self._log("error", f"✗ Connection error: {e}")
        self.is_connected = False
        if self.frontend_ws:
            await self.frontend_ws.close(code=1011, reason=f"Connection error: {e}")
```

**Pros**:
- Proper lifecycle management
- Automatic cleanup on exit
- Follows SDK best practices

**Cons**:
- Requires restructuring the connection flow
- Session only available inside the `async with` block

### Option 2: Use `AsyncExitStack` (Alternative)

Use Python's `AsyncExitStack` to manage the context manager manually:

```python
from contextlib import AsyncExitStack

async def _connect_to_gemini_live(self):
    self.exit_stack = AsyncExitStack()

    session = await self.exit_stack.enter_async_context(
        self.genai_client.aio.live.connect(
            model="gemini-2.0-flash-exp",
            config=config
        )
    )

    return session

async def disconnect(self):
    if hasattr(self, 'exit_stack'):
        await self.exit_stack.aclose()
```

**Pros**:
- More control over lifecycle
- Can store session as instance variable

**Cons**:
- More complex
- Still requires careful cleanup management

### Option 3: Revert to Manual WebSocket (Last Resort)

Fall back to manual WebSocket management if SDK doesn't fit the architecture well.

## Recommendation

**Use Option 1** - Refactor to properly use `async with`. This is the cleanest approach and follows the SDK's design.

## Files Affected

- ✅ `backend/pyproject.toml` - Dependencies updated
- ⚠️ `backend/app/services/gemini_live.py` - Needs refactoring (lines 237-289)
- ✅ `backend/app/config.py` - WebSocket URL updated (not used with new SDK)
- ✅ `backend/.env.example` - Documentation updated

## Next Steps

1. Refactor `_connect_to_gemini_live()` to use `async with`
2. Move bidirectional streaming inside the context manager
3. Test connection lifecycle
4. Verify audio quality improvements with `gemini-2.0-flash-exp`

## Package Versions (Final)

```toml
"google-genai>=1.46.0"  # NEW SDK for Vertex AI Live API
"google-cloud-aiplatform>=1.122.0"
"google-generativeai>=0.8.5"  # Keep for legacy agents
```

## References

- **Live API Docs**: https://cloud.google.com/vertex-ai/generative-ai/docs/live-api
- **google-genai PyPI**: https://pypi.org/project/google-genai/
- **Python Async Context Managers**: https://docs.python.org/3/reference/datamodel.html#async-context-managers
