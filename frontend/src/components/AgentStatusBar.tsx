/**
 * Agent Status Bar - Shows real-time status of all agents.
 *
 * Features:
 * - Visual indicators for each agent (idle, thinking, complete, error)
 * - Current task display
 * - Animated thinking state
 * - Remote agent badges with circuit breaker status
 * - Add Agent button for registering remote A2A agents
 */

'use client';

import { useEffect, useState } from 'react';
import { useProjectStore } from '@/stores/useProjectStore';
import { useAgentStore, AgentInfo } from '@/stores/useAgentStore';
import { cn } from '@/lib/utils';
import { Loader2, CheckCircle2, XCircle, Circle, Sparkles, Settings, Plus, Cloud, Wifi, WifiOff, AlertTriangle } from 'lucide-react';

// Default local agents (fallback if API not available)
const DEFAULT_AGENTS = [
  { id: 'strategy', name: 'Strategy', icon: '🎯' },
  { id: 'art_director', name: 'Art Director', icon: '🎨' },
  { id: 'video_producer', name: 'Video Producer', icon: '🎬' },
  { id: 'audio_team', name: 'Audio Team', icon: '🎵' },
  { id: 'web_dev', name: 'Web Dev', icon: '💻' },
];

// Map agent IDs to icons
const AGENT_ICONS: Record<string, string> = {
  strategy: '🎯',
  art_director: '🎨',
  video_producer: '🎬',
  audio_team: '🎵',
  web_dev: '💻',
};

interface AgentStatusBarProps {
  onReconfigure?: () => void;
  selectedModel?: string;
  selectedVoice?: string;
  onAddAgent?: () => void;
  isConnected?: boolean;
}

export function AgentStatusBar({ onReconfigure, selectedModel, selectedVoice, onAddAgent, isConnected = false }: AgentStatusBarProps) {
  const { agentStatuses } = useProjectStore();
  const { agents, fetchAgents, circuitBreakerStates } = useAgentStore();
  const [showRemoteIndicators, setShowRemoteIndicators] = useState(false);

  // Fetch agents on mount
  useEffect(() => {
    fetchAgents().catch(console.error);
  }, [fetchAgents]);

  // Determine which agents to display (use API agents if available, else defaults)
  const displayAgents = agents.length > 0
    ? agents.filter(a => a.is_active).map(a => ({
      id: a.agent_id,
      name: a.name,
      icon: AGENT_ICONS[a.agent_id] || '🤖',
      provider: a.provider,
      status: a.status,
      overrides: a.overrides,
      overridden_by: a.overridden_by,
    }))
    : DEFAULT_AGENTS.map(a => ({ ...a, provider: 'local' as const, status: 'ready' as const, overrides: undefined }));

  // Count remote agents
  const remoteCount = agents.filter(a => a.provider === 'remote').length;

  return (
    <div className="border-b border-zinc-800/50 bg-gradient-to-r from-zinc-950 via-zinc-900/95 to-zinc-950 h-16 flex items-center px-6 justify-between">
      {/* Left: Identity */}
      <div className="flex items-center gap-3 min-w-[280px]">
        <div className="p-2.5 bg-purple-500/15 rounded-xl">
          <Sparkles className="w-6 h-6 text-purple-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent leading-tight">
            AI Agency Hub
          </h1>
          <p className="text-xs text-zinc-500 leading-tight">
            Multimodal Creative Team
            {remoteCount > 0 && (
              <span className="ml-1 text-purple-400">
                +{remoteCount} remote
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Center: Agent Status Row */}
      <div className="flex-1 flex justify-center overflow-x-auto px-6 no-scrollbar">
        <div className="flex items-center gap-3">
          {displayAgents.map((agent) => {
            const taskStatus = agentStatuses[agent.id];
            const cbState = circuitBreakerStates[agent.id];
            return (
              <AgentStatus
                key={agent.id}
                name={agent.name}
                icon={agent.icon}
                status={taskStatus?.status || 'idle'}
                currentTask={taskStatus?.current_task}
                provider={agent.provider}
                circuitBreakerState={cbState?.state}
                overrides={agent.overrides}
              />
            );
          })}

          {/* Add Remote Agent Button - compact icon style matching agent chips */}
          {onAddAgent && (
            <button
              onClick={onAddAgent}
              className="flex items-center gap-2 px-3 py-2 rounded-full border border-dashed border-zinc-700/50 hover:border-purple-500/50 hover:bg-purple-500/10 bg-zinc-900/80 transition-all group"
              title="Add remote A2A agent"
            >
              <Plus className="w-4 h-4 text-zinc-500 group-hover:text-purple-400 transition-colors" />
            </button>
          )}
        </div>
      </div>

      {/* Right: Configuration */}
      <div className="flex items-center gap-4 min-w-[220px] justify-end">
        <div className="flex flex-col items-end hidden md:flex">
          <div className="text-xs font-medium text-zinc-300 font-mono">
            {selectedModel || 'No model selected'}
          </div>
          {selectedVoice && (
            <div className="text-[10px] text-zinc-500">
              Voice: {selectedVoice}
            </div>
          )}
        </div>

        <div className="h-8 w-px bg-zinc-800/50 hidden md:block" />

        <div className="flex items-center gap-2">
          {onReconfigure && (
            <button
              onClick={onReconfigure}
              className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-white transition-colors"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
          )}

          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-900/80 border ${isConnected ? 'border-green-800/50' : 'border-red-800/50'}`}>
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <span className={`text-xs font-medium ${isConnected ? 'text-zinc-400' : 'text-red-400'}`}>
              {isConnected ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

interface AgentStatusProps {
  name: string;
  icon: string;
  status: 'idle' | 'thinking' | 'complete' | 'error';
  currentTask?: string;
  provider?: 'local' | 'remote';
  circuitBreakerState?: 'closed' | 'open' | 'half_open';
  overrides?: string;
}

function AgentStatus({ name, icon, status, currentTask, provider, circuitBreakerState, overrides }: AgentStatusProps) {
  const isRemote = provider === 'remote';
  const isCircuitOpen = circuitBreakerState === 'open';
  const isCircuitHalfOpen = circuitBreakerState === 'half_open';
  const isActive = status === 'thinking';
  const isComplete = status === 'complete';

  const getStatusIcon = () => {
    // Circuit breaker takes precedence for remote agents
    if (isRemote && isCircuitOpen) {
      return <WifiOff className="w-3.5 h-3.5 text-red-400" />;
    }
    if (isRemote && isCircuitHalfOpen) {
      return <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />;
    }

    switch (status) {
      case 'thinking':
        return <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin" />;
      case 'complete':
        return <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />;
      case 'error':
        return <XCircle className="w-3.5 h-3.5 text-red-400" />;
      default:
        return null;
    }
  };

  const getTooltip = () => {
    const parts = [name];
    if (isRemote) parts.push('(Remote A2A)');
    if (overrides) parts.push(`Overrides: ${overrides}`);
    if (isCircuitOpen) parts.push('Circuit OPEN - failing over to local');
    if (isCircuitHalfOpen) parts.push('Circuit HALF-OPEN - testing recovery');
    if (currentTask) parts.push(currentTask);
    return parts.join(' | ');
  };

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-full border transition-all relative',
        // Base styles
        'bg-zinc-900/80',
        // Status-based styles with glow effect
        isActive && 'border-purple-500/60 bg-purple-900/30 shadow-[0_0_12px_rgba(168,85,247,0.3)]',
        isComplete && 'border-green-500/40 bg-green-900/20',
        status === 'error' && 'border-red-500/40 bg-red-900/20',
        status === 'idle' && 'border-zinc-700/50',
        // Circuit breaker overrides
        isRemote && isCircuitOpen && 'border-red-500/50 bg-red-900/20',
        isRemote && isCircuitHalfOpen && 'border-yellow-500/50 bg-yellow-900/20',
        // Remote indicator
        isRemote && status === 'idle' && 'border-purple-700/50 bg-purple-900/10'
      )}
      title={getTooltip()}
    >
      {/* Remote badge */}
      {isRemote && (
        <div className="absolute -top-1.5 -right-1.5">
          <Cloud className="w-3 h-3 text-purple-400" />
        </div>
      )}

      <span className="text-base">{icon}</span>
      <span className={cn(
        'text-xs font-medium',
        isActive ? 'text-purple-200' : 'text-zinc-400'
      )}>
        {name}
      </span>
      {getStatusIcon()}
    </div>
  );
}
