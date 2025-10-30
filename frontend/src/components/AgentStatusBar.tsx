/**
 * Agent Status Bar - Shows real-time status of all agents.
 *
 * Features:
 * - Visual indicators for each agent (idle, thinking, complete, error)
 * - Current task display
 * - Animated thinking state
 */

'use client';

import { useProjectStore } from '@/stores/useProjectStore';
import { cn } from '@/lib/utils';
import { Loader2, CheckCircle2, XCircle, Circle } from 'lucide-react';

const AGENTS = [
  { id: 'strategy', name: 'Strategy', icon: '🎯' },
  { id: 'art_director', name: 'Art Director', icon: '🎨' },
  { id: 'video_producer', name: 'Video Producer', icon: '🎬' },
  { id: 'audio_team', name: 'Audio Team', icon: '🎵' },
  { id: 'web_dev', name: 'Web Dev', icon: '💻' },
];

export function AgentStatusBar() {
  const { agentStatuses } = useProjectStore();

  return (
    <div className="border-b border-zinc-800 bg-zinc-950">
      <div className="container mx-auto px-6 py-4">
        <div className="flex items-center gap-6">
          <div className="text-sm font-medium text-zinc-400">Agencies:</div>

          <div className="flex gap-4">
            {AGENTS.map((agent) => {
              const status = agentStatuses[agent.id];
              return (
                <AgentStatus
                  key={agent.id}
                  name={agent.name}
                  icon={agent.icon}
                  status={status?.status || 'idle'}
                  currentTask={status?.current_task}
                />
              );
            })}
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
}

function AgentStatus({ name, icon, status, currentTask }: AgentStatusProps) {
  const getStatusIcon = () => {
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
    switch (status) {
      case 'thinking':
        return 'border-blue-500/50 bg-blue-500/10';
      case 'complete':
        return 'border-green-500/50 bg-green-500/10';
      case 'error':
        return 'border-red-500/50 bg-red-500/10';
      default:
        return 'border-zinc-700 bg-zinc-900';
    }
  };

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-lg border transition-all',
        getStatusColor()
      )}
      title={currentTask || name}
    >
      <span className="text-lg">{icon}</span>
      <div className="flex flex-col">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-300">{name}</span>
          {getStatusIcon()}
        </div>
        {currentTask && status === 'thinking' && (
          <span className="text-xs text-zinc-500 max-w-32 truncate">{currentTask}</span>
        )}
      </div>
    </div>
  );
}
