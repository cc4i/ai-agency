# WebSocket Connection Fix - Multiple Connections Issue

## Problem

Backend logs showed:
```
INFO:     127.0.0.1:53933 - "WebSocket /ws//" 403
INFO:     connection rejected (403 Forbidden)
```

Multiple WebSocket connections were being created with **empty session/project IDs** (`/ws//`), causing 403 errors.

## Root Cause

### Issue 1: Hooks Running Before Initialization

```typescript
// BEFORE (BROKEN)
export default function WorkspaceClient() {
  const [sessionId, setSessionId] = useState<string>('');  // Empty initially!
  const [projectId, setProjectId] = useState<string>('');  // Empty initially!

  // ❌ useWebSocket called IMMEDIATELY with empty strings
  const { sendAudio } = useWebSocket(sessionId, projectId);

  useEffect(() => {
    // Session ID generated here (too late!)
    setSessionId(`session_${Date.now()}_...`);
    setProjectId('aura_smart_sneaker');
  }, []);

  // Guard happens after hooks already ran
  if (!sessionId) return <div>Loading...</div>;
}
```

**Result**:
- `useWebSocket('', '')` → tries to connect to `/ws//` → 403 error
- Then IDs are set → reconnects to proper path
- Creates 2 connections per mount

### Issue 2: React 18 StrictMode

Next.js has `reactStrictMode: true` in `next.config.js`, which in development:
- Mounts component
- Unmounts component
- Remounts component

**Result**: Each component mount creates connections, so with empty IDs bug = 4 connections!

## Solution

### Fix 1: Early Return Before Hooks

```typescript
// AFTER (FIXED)
export default function WorkspaceClient() {
  const [sessionId, setSessionId] = useState<string>('');
  const [projectId, setProjectId] = useState<string>('');
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // Generate IDs
    setSessionId(`session_${Date.now()}_...`);
    setProjectId('aura_smart_sneaker');
    setIsInitialized(true);
  }, []);

  // ✓ Return BEFORE hooks run
  if (!isInitialized || !sessionId || !projectId) {
    return <div>Initializing...</div>;
  }

  // Hooks only run when IDs are ready
  const { sendAudio } = useWebSocket(sessionId, projectId);
  const microphone = useMicrophone({ onAudioData: sendAudio });
}
```

**Key**: Early return prevents hooks from running until IDs are ready

### Fix 2: Guards in useWebSocket

```typescript
// In useWebSocket hook
const connect = useCallback(() => {
  // ✓ Double-check IDs are valid
  if (!sessionId || !projectId) {
    console.warn('Cannot connect: missing session or project ID');
    return;
  }

  if (wsRef.current?.readyState === WebSocket.OPEN) {
    console.log('Already connected, skipping');
    return;
  }

  // Close existing connection before creating new one
  if (wsRef.current) {
    wsRef.current.close();
    wsRef.current = null;
  }

  const ws = new WebSocket(`${WS_URL}/ws/${sessionId}/${projectId}`);
  // ...
}, [sessionId, projectId]);

useEffect(() => {
  // ✓ Only connect if IDs exist
  if (sessionId && projectId) {
    connect();
  }

  return () => disconnect();
}, [sessionId, projectId, connect, disconnect]);
```

**Key**: Multiple layers of protection

## Expected Behavior Now

### Development (with StrictMode)

**First Mount**:
```
[WebSocket] 🔌 Connecting to ws://localhost:8000/ws/session_xxx.../aura_smart_sneaker
[WebSocket] ✓ Connected to backend
```

**StrictMode Unmount**:
```
[WebSocket] ✗ Disconnected (code: 1001, reason: )
```

**StrictMode Remount**:
```
[WebSocket] 🔌 Connecting to ws://localhost:8000/ws/session_xxx.../aura_smart_sneaker
[WebSocket] ✓ Connected to backend
```

**Result**:
- Only 1 connection active at a time
- No `/ws//` errors
- Clean reconnection on remount

### Production (StrictMode disabled)

**Single Mount**:
```
[WebSocket] 🔌 Connecting to ws://localhost:8000/ws/session_xxx.../aura_smart_sneaker
[WebSocket] ✓ Connected to backend
```

**Result**: Only 1 connection, period

## Backend Logs (Fixed)

**Before**:
```
INFO:     127.0.0.1:53933 - "WebSocket /ws//" 403
INFO:     connection rejected (403 Forbidden)
INFO:     127.0.0.1:53935 - "WebSocket /ws//" 403
INFO:     connection rejected (403 Forbidden)
```

**After**:
```
2025-10-29 00:47:39,677 - app.main - INFO - WebSocket connection request for session: session_1761667471315_e47jvmt, project: aura_smart_sneaker
2025-10-29 00:47:39,677 - app.services.gemini_live - INFO - [Session: session_1...] [Turn: 0] 🔌 Establishing Gemini Live connection
INFO:     127.0.0.1:53927 - "WebSocket /ws/session_1761667471315_e47jvmt/aura_smart_sneaker" [accepted]
2025-10-29 00:47:39,913 - app.services.gemini_live - INFO - [Session: session_1...] [Turn: 0] ✓ Gemini Live connection established
```

✓ Only valid connections with proper IDs

## Files Changed

1. **frontend/src/components/WorkspaceClient.tsx**
   - Moved early return BEFORE hooks
   - Added check for empty IDs

2. **frontend/src/hooks/useWebSocket.ts**
   - Added guard to prevent connection with empty IDs
   - Added existing connection cleanup
   - Added better logging
   - Only connect if IDs are valid

## Testing

### 1. Check for Empty ID Connections

**Before starting**:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

**Watch for**:
```
# Should NOT see:
"WebSocket /ws//" 403

# Should see:
"WebSocket /ws/session_xxx.../aura_smart_sneaker" [accepted]
```

### 2. Check Frontend Logs

Open browser console (F12):

```
# Should see:
[Session: session_xxx...][Project: aura_smart_sneaker] [WebSocket] 🔌 Connecting to ws://localhost:8000/ws/...
[Session: session_xxx...][Project: aura_smart_sneaker] [WebSocket] ✓ Connected to backend

# Should NOT see:
⚠ Cannot connect: missing session or project ID
```

### 3. Verify Single Active Connection

**In browser DevTools**:
1. Go to Network tab
2. Filter by "WS" (WebSocket)
3. Should see only 1 active connection
4. Click microphone, speak
5. Connection should stay open (Status: "Pending")

## Why StrictMode is Good

React 18's StrictMode double-mounting helps catch bugs:
- **Bad**: Component assumes it only mounts once
- **Good**: Component properly cleans up on unmount

Our fix ensures:
- ✓ Proper cleanup when component unmounts
- ✓ Fresh connection when component remounts
- ✓ No duplicate connections
- ✓ Works in both dev and production

## Related Issues

This fix also solves:
- Multiple Gemini Live connections (wasting API quota)
- Race conditions when IDs change
- Memory leaks from unclosed connections
- Confusion in backend logs (multiple sessions)

## Production Note

In production builds (`npm run build && npm start`):
- StrictMode is automatically disabled
- Component only mounts once
- Only 1 connection created
- No remounting behavior

The fixes ensure it works correctly in **both** development and production!
