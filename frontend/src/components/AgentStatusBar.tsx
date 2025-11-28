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
}

export function AgentStatusBar({ onReconfigure, selectedModel, selectedVoice, onAddAgent }: AgentStatusBarProps) {
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
    : DEFAULT_AGENTS.map(a => ({ ...a, provider: 'local' as const, status: 'ready' as const }));

  // Count remote agents
  const remoteCount = agents.filter(a => a.provider === 'remote').length;

  return (
    <div className="border-b border-zinc-800 bg-gradient-to-r from-purple-950/30 via-blue-950/30 to-purple-950/30">
      <div className="px-3 py-3 space-y-3">
        {/* Header Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Sparkles className="w-10 h-10 text-purple-400" />
            <div>
              <h2 className="text-2xl font-semibold text-zinc-100">
                AI Agency Hub
              </h2>
              <p className="text-xs text-zinc-400">
                Your creative team is ready to bring your campaign to life
                {remoteCount > 0 && (
                  <span className="ml-2 text-purple-400">
                    ({remoteCount} remote agent{remoteCount > 1 ? 's' : ''})
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex flex-col items-end">
              <div className="text-xs text-zinc-400 font-mono">
                {selectedModel || 'gemini-live-2.5-flash'}
              </div>
              {selectedVoice && (
                <div className="text-xs text-zinc-500">
                  Voice: {selectedVoice}
                </div>
              )}
            </div>
            {onReconfigure && (
              <button
                onClick={onReconfigure}
                className="p-1.5 rounded-lg hover:bg-zinc-800 transition-colors group"
                title="Change model and voice settings"
              >
                <Settings className="w-4 h-4 text-zinc-500 group-hover:text-zinc-300 transition-colors" />
              </button>
            )}
          </div>
        </div>

        {/* Agent Status Row */}
        <div className="flex gap-3 flex-wrap items-center">
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
          {/* Add Remote Agent Button */}
          {onAddAgent && (
            <button
              onClick={onAddAgent}
              className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-dashed border-purple-500/50 hover:border-purple-400 hover:bg-purple-500/10 transition-colors group"
              title="Add remote A2A agent"
            >
              <Plus className="w-4 h-4 text-purple-400 group-hover:text-purple-300 transition-colors" />
              <Cloud className="w-4 h-4 text-purple-400 group-hover:text-purple-300 transition-colors" />
              <span className="text-xs text-purple-400 group-hover:text-purple-300">Add Agent</span>
            </button>
          )}
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

  const getStatusIcon = () => {
    // Circuit breaker takes precedence for remote agents
    if (isRemote && isCircuitOpen) {
      return <WifiOff className="w-4 h-4 text-red-400" />;
    }
    if (isRemote && isCircuitHalfOpen) {
      return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
    }

    switch (status) {
      case 'thinking':
        return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'complete':
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Circle className="w-4 h-4 text-zinc-600" />;
    }
  };

  const getStatusColor = () => {
    // Circuit breaker states
    if (isRemote && isCircuitOpen) {
      return 'border-red-500/50 bg-red-500/10';
    }
    if (isRemote && isCircuitHalfOpen) {
      return 'border-yellow-500/50 bg-yellow-500/10';
    }

    switch (status) {
      case 'thinking':
        return 'border-blue-500/50 bg-blue-500/10';
      case 'complete':
        return 'border-green-500/50 bg-green-500/10';
      case 'error':
        return 'border-red-500/50 bg-red-500/10';
      default:
        return isRemote ? 'border-purple-700 bg-purple-900/20' : 'border-zinc-700 bg-zinc-900';
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
        'flex items-center gap-2 px-2 py-1 rounded-lg border transition-all relative',
        getStatusColor()
      )}
      title={getTooltip()}
    >
      {/* Remote badge */}
      {isRemote && (
        <div className="absolute -top-1 -right-1">
          <Cloud className="w-3 h-3 text-purple-400" />
        </div>
      )}

      <span className="text-base">{icon}</span>
      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-300">{name}</span>
          {getStatusIcon()}
        </div>
        {/* Show current task or circuit breaker status */}
        {isCircuitOpen && (
          <span className="text-xs text-red-400 max-w-32 truncate">Failover active</span>
        )}
        {isCircuitHalfOpen && (
          <span className="text-xs text-yellow-400 max-w-32 truncate">Recovering...</span>
        )}
        {currentTask && status === 'thinking' && !isCircuitOpen && !isCircuitHalfOpen && (
          <span className="text-xs text-zinc-500 max-w-32 truncate">{currentTask}</span>
        )}
      </div>
    </div>
  );
}
