/**
 * System Prompt Editor - Collapsible advanced configuration panel.
 *
 * Features:
 * - View and edit the Executive Producer system prompt
 * - Character count with warning for long prompts
 * - Reset to default functionality
 * - Persists to Redis via API
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { ChevronDown, ChevronRight, RotateCcw, Save, AlertTriangle } from 'lucide-react';
import { API_BASE_URL } from '@/config';

interface PromptData {
  prompt: string;
  is_custom: boolean;
  character_count: number;
}

export function SystemPromptEditor() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [isCustom, setIsCustom] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');

  const MAX_RECOMMENDED_CHARS = 10000;
  const MAX_WARN_CHARS = 15000;

  // Fetch current prompt (template with {project_id} placeholder intact)
  const fetchPrompt = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/admin/system-prompt`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch system prompt');
      }

      const data: PromptData = await response.json();
      setPrompt(data.prompt);
      setOriginalPrompt(data.prompt);
      setIsCustom(data.is_custom);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load prompt');
      console.error('Failed to fetch system prompt:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load prompt when expanded
  useEffect(() => {
    if (isExpanded && !prompt) {
      fetchPrompt();
    }
  }, [isExpanded, prompt, fetchPrompt]);

  // Save prompt
  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus('idle');
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/system-prompt`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt }),
      });

      if (!response.ok) {
        throw new Error('Failed to save system prompt');
      }

      setOriginalPrompt(prompt);
      setIsCustom(true);
      setSaveStatus('saved');

      // Clear save status after 2 seconds
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  // Reset to default
  const handleReset = async () => {
    setIsSaving(true);
    setError(null);

    try {
      // Delete custom prompt
      await fetch(`${API_BASE_URL}/api/admin/system-prompt`, {
        method: 'DELETE',
      });

      // Fetch default prompt template (with {project_id} placeholder intact)
      const response = await fetch(
        `${API_BASE_URL}/api/admin/system-prompt/default`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch default prompt');
      }

      const data: PromptData = await response.json();
      setPrompt(data.prompt);
      setOriginalPrompt(data.prompt);
      setIsCustom(false);
      setSaveStatus('saved');

      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset');
    } finally {
      setIsSaving(false);
    }
  };

  const hasChanges = prompt !== originalPrompt;
  const charCount = prompt.length;
  const isOverRecommended = charCount > MAX_RECOMMENDED_CHARS;
  const isOverWarn = charCount > MAX_WARN_CHARS;

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden">
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-zinc-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-zinc-400" />
          )}
          <span className="text-sm font-medium text-zinc-300">System Prompt</span>
          <span className="text-xs text-zinc-500">(Advanced)</span>
        </div>

        {isCustom && (
          <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded">
            Custom
          </span>
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="p-3 border-t border-zinc-800 space-y-3">
          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-zinc-600 border-t-zinc-300 rounded-full" />
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
              <AlertTriangle className="w-4 h-4" />
              {error}
            </div>
          )}

          {/* Editor */}
          {!isLoading && (
            <>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full h-64 p-3 bg-zinc-950 border border-zinc-800 rounded-lg font-mono text-xs text-zinc-300 resize-y focus:outline-none focus:border-zinc-600 placeholder-zinc-600"
                placeholder="Enter system prompt..."
                spellCheck={false}
              />

              {/* Footer */}
              <div className="flex items-center justify-between">
                {/* Character Count */}
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs ${
                      isOverWarn
                        ? 'text-red-400'
                        : isOverRecommended
                        ? 'text-yellow-400'
                        : 'text-zinc-500'
                    }`}
                  >
                    {charCount.toLocaleString()} characters
                  </span>
                  {isOverRecommended && (
                    <span className="text-xs text-yellow-400/70">
                      (recommended: &lt;{MAX_RECOMMENDED_CHARS.toLocaleString()})
                    </span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  {/* Save Status */}
                  {saveStatus === 'saved' && (
                    <span className="text-xs text-green-400">Saved!</span>
                  )}

                  {/* Reset Button - enabled when custom prompt is saved OR when there are unsaved changes */}
                  <button
                    onClick={handleReset}
                    disabled={isSaving || (!isCustom && !hasChanges)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Reset to default prompt"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    Reset
                  </button>

                  {/* Save Button */}
                  <button
                    onClick={handleSave}
                    disabled={isSaving || !hasChanges}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isSaving ? (
                      <div className="animate-spin w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" />
                    ) : (
                      <Save className="w-3.5 h-3.5" />
                    )}
                    Save
                  </button>
                </div>
              </div>

              {/* Help Text */}
              <p className="text-xs text-zinc-600">
                Customize the Executive Producer&apos;s behavior. Use <code className="px-1 py-0.5 bg-zinc-800 rounded">{'{project_id}'}</code> as a placeholder for the current project.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
