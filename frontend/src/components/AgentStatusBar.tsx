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
import { Loader2, CheckCircle2, XCircle, Circle, Sparkles, Settings } from 'lucide-react';

const AGENTS = [
  { id: 'strategy', name: 'Strategy', icon: '🎯' },
  { id: 'art_director', name: 'Art Director', icon: '🎨' },
  { id: 'video_producer', name: 'Video Producer', icon: '🎬' },
  { id: 'audio_team', name: 'Audio Team', icon: '🎵' },
  { id: 'web_dev', name: 'Web Dev', icon: '💻' },
];

interface AgentStatusBarProps {
  onReconfigure?: () => void;
  selectedModel?: string;
  selectedVoice?: string;
}

export function AgentStatusBar({ onReconfigure, selectedModel, selectedVoice }: AgentStatusBarProps) {
  const { agentStatuses } = useProjectStore();

  return (
    <div className="border-b border-zinc-800 bg-gradient-to-r from-purple-950/30 via-blue-950/30 to-purple-950/30">
      <div className="px-3 py-3 space-y-3">
        {/* Header Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-purple-400" />
            <div>
              <h2 className="text-2xl font-semibold text-zinc-100">
                AI Agency Hub
              </h2>
              <p className="text-xs text-zinc-400">
                Your creative team is ready to bring your campaign to life
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
        <div className="flex gap-3">
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
        'flex items-center gap-2 px-2 py-1 rounded-lg border transition-all',
        getStatusColor()
      )}
      title={currentTask || name}
    >
      <span className="text-base">{icon}</span>
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
