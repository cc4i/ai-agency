# UI Notes - Agent Status Bar

## Agent Status Items Are Display-Only

The agent status items in the top bar (Strategy, Art Director, Video Producer, Audio Team, Web Dev) are **display-only indicators**, not interactive buttons.

### What They Show

Each agent displays:
- **Icon**: Visual identifier (🎯 🎨 🎬 🎵 💻)
- **Name**: Agent role
- **Status**: Current state with visual indicator
  - **Idle** (gray): Agent not working
  - **Thinking** (blue, spinning): Agent processing task
  - **Complete** (green, checkmark): Agent finished task
  - **Error** (red, X): Agent encountered error
- **Current Task** (optional): What the agent is doing (only shown when thinking)

### Why They're Not Clickable

The agent status bar provides real-time visibility into the multi-agent system's state. Users don't directly control individual agents - they interact with the Executive Producer (via voice) who orchestrates the agents.

**Interaction Flow**:
1. User speaks to Executive Producer (via microphone)
2. Producer delegates tasks to agents
3. Agents update their status automatically
4. User sees progress in the status bar

### If You Want Clickable Agents

If you need to make agents clickable (e.g., to view details or manually trigger tasks), you would need to:

1. Add click handlers to `AgentStatus` component
2. Add a modal/panel to show agent details
3. Implement agent control API endpoints
4. Add state management for selected agent

**Example Implementation**:

```typescript
// In AgentStatusBar.tsx
function AgentStatus({ name, icon, status, currentTask }: AgentStatusProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsExpanded(true)}
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg border transition-all',
          'hover:border-blue-500 cursor-pointer', // Make it look clickable
          getStatusColor()
        )}
      >
        {/* existing content */}
      </button>

      {isExpanded && (
        <AgentDetailsModal
          agentId={id}
          onClose={() => setIsExpanded(false)}
        />
      )}
    </>
  );
}
```

But for the current design (Phase 4), agents are orchestrated automatically by the Producer, so direct interaction is not needed.

## Interactive Elements

**Currently interactive**:
- **Microphone button** (bottom center): Click to start/stop recording
- **Project Brief fields** (right panel): May become editable in future phases

**Not interactive (display-only)**:
- Agent status items (top bar)
- Asset displays (main content area)
- Producer announcements (bottom panel)
