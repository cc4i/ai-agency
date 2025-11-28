/**
 * Add Agent Modal - Dialog for registering remote A2A agents.
 *
 * Features:
 * - Input for Agent Card URL
 * - Environment variable reference for API key
 * - Override selection for local agents
 * - Validation and error handling
 */

'use client';

import { useState, useEffect } from 'react';
import { useAgentStore, AgentInfo } from '@/stores/useAgentStore';
import { cn } from '@/lib/utils';
import {
  X,
  Cloud,
  Link,
  Key,
  ArrowRightLeft,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Eye,
  EyeOff
} from 'lucide-react';

interface AddAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AddAgentModal({ isOpen, onClose }: AddAgentModalProps) {
  const { agents, registerRemoteAgent, isLoading, error, fetchAgents } = useAgentStore();

  // Form state
  const [agentCardUrl, setAgentCardUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [overrideLocal, setOverrideLocal] = useState<string | undefined>(undefined);

  // UI state
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState<AgentInfo | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);

  // Get local agents that can be overridden
  const localAgents = agents.filter(a => a.provider === 'local' && !a.overridden_by);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setAgentCardUrl('');
      setApiKey('');
      setOverrideLocal(undefined);
      setSubmitError(null);
      setSuccess(null);
      setShowApiKey(false);
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSuccess(null);

    // Validation
    if (!agentCardUrl.trim()) {
      setSubmitError('Agent Card URL is required');
      return;
    }
    if (!apiKey.trim()) {
      setSubmitError('API Key is required');
      return;
    }

    // Validate URL format
    try {
      new URL(agentCardUrl);
    } catch {
      setSubmitError('Invalid URL format');
      return;
    }

    // Register the agent (pass actual API key)
    const result = await registerRemoteAgent(agentCardUrl, apiKey, overrideLocal);

    if (result.success && result.agent) {
      setSuccess(result.agent);
      // Refresh agents list
      await fetchAgents();
    } else {
      setSubmitError(result.error || 'Failed to register agent');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-lg mx-4 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <Cloud className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">Add Remote Agent</h2>
              <p className="text-xs text-zinc-400">Connect an external A2A agent</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Success State */}
          {success && (
            <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
              <div className="flex items-center gap-2 text-green-400">
                <CheckCircle2 className="w-5 h-5" />
                <span className="font-medium">Agent Registered Successfully</span>
              </div>
              <div className="mt-2 text-sm text-zinc-300">
                <p><strong>{success.name}</strong> is now available</p>
                {success.overrides && (
                  <p className="text-zinc-400 mt-1">
                    Overriding local agent: {success.overrides}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="mt-4 w-full px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors"
              >
                Done
              </button>
            </div>
          )}

          {/* Form Fields */}
          {!success && (
            <>
              {/* Agent Card URL */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                  <Link className="w-4 h-4 text-purple-400" />
                  Agent Card URL
                </label>
                <input
                  type="url"
                  value={agentCardUrl}
                  onChange={(e) => setAgentCardUrl(e.target.value)}
                  placeholder="https://example.com/.well-known/agent.json"
                  className={cn(
                    "w-full px-4 py-2.5 bg-zinc-800 border rounded-lg",
                    "text-zinc-100 placeholder-zinc-500",
                    "focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500",
                    "transition-colors",
                    submitError && !agentCardUrl ? "border-red-500" : "border-zinc-700"
                  )}
                  disabled={isLoading}
                />
                <p className="text-xs text-zinc-500">
                  The URL to the agent&apos;s Agent Card (usually at /.well-known/agent.json)
                </p>
              </div>

              {/* API Key */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                  <Key className="w-4 h-4 text-purple-400" />
                  API Key
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Enter API key for the remote agent"
                    className={cn(
                      "w-full px-4 py-2.5 pr-12 bg-zinc-800 border rounded-lg",
                      "text-zinc-100 placeholder-zinc-500",
                      "focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500",
                      "transition-colors",
                      submitError && !apiKey ? "border-red-500" : "border-zinc-700"
                    )}
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-zinc-500 hover:text-zinc-300 transition-colors"
                    tabIndex={-1}
                  >
                    {showApiKey ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-zinc-500">
                  The API key will be stored securely on the server
                </p>
              </div>

              {/* Override Local Agent */}
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                  <ArrowRightLeft className="w-4 h-4 text-purple-400" />
                  Override Local Agent (Optional)
                </label>
                <select
                  value={overrideLocal || ''}
                  onChange={(e) => setOverrideLocal(e.target.value || undefined)}
                  className={cn(
                    "w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg",
                    "text-zinc-100",
                    "focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500",
                    "transition-colors"
                  )}
                  disabled={isLoading}
                >
                  <option value="">None - Add as new agent</option>
                  {localAgents.map((agent) => (
                    <option key={agent.agent_id} value={agent.agent_id}>
                      {agent.name} ({agent.agent_id})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-zinc-500">
                  Optionally replace a local agent with this remote one. The local agent becomes a fallback.
                </p>
              </div>

              {/* Error Display */}
              {(submitError || error) && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <div className="flex items-center gap-2 text-red-400">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span className="text-sm">{submitError || error}</span>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg transition-colors"
                  disabled={isLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className={cn(
                    "flex-1 px-4 py-2.5 rounded-lg transition-colors",
                    "flex items-center justify-center gap-2",
                    isLoading
                      ? "bg-purple-600/50 text-purple-300 cursor-not-allowed"
                      : "bg-purple-600 hover:bg-purple-500 text-white"
                  )}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <Cloud className="w-4 h-4" />
                      Connect Agent
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </form>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-zinc-800 bg-zinc-800/30">
          <a
            href="https://google.github.io/A2A/"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-400 transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            Learn more about the A2A Protocol
          </a>
        </div>
      </div>
    </div>
  );
}
