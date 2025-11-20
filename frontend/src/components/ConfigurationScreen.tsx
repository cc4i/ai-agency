/**
 * Configuration Screen - Model and Voice Selection
 *
 * Allows users to choose Gemini Live model and voice before starting session.
 * Organized with 3 model options and 30 voices grouped by personality.
 */

'use client';

import { useState, useEffect } from 'react';
import { Sparkles, CheckCircle2, Info } from 'lucide-react';
import { API_BASE_URL } from '@/config';

interface ModelOption {
  name: string;
  description: string;
  features: string[];
  recommended?: boolean;
}

interface VoiceOption {
  personality: string;
  description: string;
}

interface VoiceGroup {
  label: string;
  voices: Record<string, VoiceOption>;
}

interface ConfigOptions {
  models: Record<string, ModelOption>;
  voiceGroups: Record<string, VoiceGroup>;
  defaults: {
    model: string;
    voice: string;
  };
}

interface ConfigurationScreenProps {
  onStart: (model: string, voice: string) => void;
}

export function ConfigurationScreen({ onStart }: ConfigurationScreenProps) {
  const [options, setOptions] = useState<ConfigOptions | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedVoice, setSelectedVoice] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    // Fetch available models and voices from backend
    fetch(`${API_BASE_URL}/api/config/models-voices`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch configuration');
        return res.json();
      })
      .then((data: ConfigOptions) => {
        setOptions(data);

        // Check for saved preferences
        const savedModel = localStorage.getItem('preferred_model');
        const savedVoice = localStorage.getItem('preferred_voice');

        // Use saved preferences if valid, otherwise use defaults
        setSelectedModel(
          savedModel && data.models[savedModel] ? savedModel : data.defaults.model
        );
        setSelectedVoice(
          savedVoice && Object.values(data.voiceGroups).some(group =>
            Object.keys(group.voices).includes(savedVoice)
          ) ? savedVoice : data.defaults.voice
        );

        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch config:', err);
        setError('Failed to load configuration options. Please check if the backend is running.');
        setLoading(false);
      });
  }, []);

  const handleStart = () => {
    // Save preferences
    localStorage.setItem('preferred_model', selectedModel);
    localStorage.setItem('preferred_voice', selectedVoice);

    onStart(selectedModel, selectedVoice);
  };

  const toggleGroupExpansion = (groupKey: string) => {
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(groupKey)) {
        newSet.delete(groupKey);
      } else {
        newSet.add(groupKey);
      }
      return newSet;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-purple-950/20 to-black flex items-center justify-center">
        <div className="text-center space-y-4">
          <Sparkles className="w-12 h-12 text-purple-400 animate-pulse mx-auto" />
          <div className="text-zinc-400">Loading configuration...</div>
        </div>
      </div>
    );
  }

  if (error || !options) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-purple-950/20 to-black flex items-center justify-center">
        <div className="max-w-md text-center space-y-4 p-8 rounded-lg border border-red-500/50 bg-red-500/10">
          <Info className="w-12 h-12 text-red-400 mx-auto" />
          <div className="text-red-300 font-semibold">Configuration Error</div>
          <div className="text-zinc-400 text-sm">{error || 'Failed to load configuration'}</div>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-purple-950/20 to-black text-white flex items-center justify-center p-4 sm:p-8 overflow-y-auto">
      <div className="max-w-4xl w-full space-y-8 py-8">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="flex items-center justify-center gap-3">
            <Sparkles className="w-10 h-10 text-purple-400" />
            <h1 className="text-4xl sm:text-5xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent">
              AI Agency Hub
            </h1>
          </div>
          <p className="text-zinc-400 text-lg">Configure your Executive Producer</p>
          <p className="text-zinc-500 text-sm">Choose your preferred model and voice to get started</p>
        </div>

        {/* Model Selection */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <span className="text-blue-400">1.</span> Select Model
          </h2>
          <div className="grid gap-3">
            {Object.entries(options.models).map(([key, model]) => (
              <button
                key={key}
                onClick={() => setSelectedModel(key)}
                className={`
                  p-4 rounded-lg border-2 text-left transition-all relative
                  ${selectedModel === key
                    ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20'
                    : 'border-zinc-700 bg-zinc-900/50 hover:border-zinc-600 hover:bg-zinc-900'
                  }
                `}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="font-semibold text-base sm:text-lg flex items-center gap-2 font-mono">
                      {key}
                      {model.recommended && (
                        <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full border border-green-500/30 font-sans">
                          Recommended
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-zinc-400 mt-2">{model.description}</div>
                  </div>
                  {selectedModel === key && (
                    <CheckCircle2 className="w-6 h-6 text-blue-400 flex-shrink-0" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Voice Selection - Grouped by Personality */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <span className="text-green-400">2.</span> Select Voice
          </h2>
          <div className="space-y-6">
            {Object.entries(options.voiceGroups).map(([groupKey, group]) => {
              const voiceEntries = Object.entries(group.voices);
              const isExpanded = expandedGroups.has(groupKey);
              const visibleVoices = isExpanded ? voiceEntries : voiceEntries.slice(0, 3);
              const hasMore = voiceEntries.length > 3;

              return (
                <div key={groupKey}>
                  <h3 className="text-sm font-medium text-zinc-400 mb-3 uppercase tracking-wide">
                    {group.label}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                    {visibleVoices.map(([voiceName, voice]) => (
                      <button
                        key={voiceName}
                        onClick={() => setSelectedVoice(voiceName)}
                        className={`
                          p-3 rounded-lg border text-left transition-all relative
                          ${selectedVoice === voiceName
                            ? 'border-green-500 bg-green-500/10 shadow-md shadow-green-500/20'
                            : 'border-zinc-700 bg-zinc-900/50 hover:border-zinc-600 hover:bg-zinc-900'
                          }
                        `}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="font-semibold text-sm truncate">{voiceName}</div>
                            <div className="text-xs text-zinc-500 mt-0.5">{voice.personality}</div>
                            <div className="text-xs text-zinc-400 mt-1">{voice.description}</div>
                          </div>
                          {selectedVoice === voiceName && (
                            <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                  {hasMore && (
                    <button
                      onClick={() => toggleGroupExpansion(groupKey)}
                      className="mt-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1"
                    >
                      {isExpanded ? (
                        <>Show less</>
                      ) : (
                        <>Show {voiceEntries.length - 3} more</>
                      )}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Start Button */}
        <div className="pt-4 space-y-4">
          <button
            onClick={handleStart}
            disabled={!selectedModel || !selectedVoice}
            className="w-full py-6 text-lg font-semibold bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 transition-all shadow-lg shadow-purple-500/30 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Sparkles className="w-5 h-5" />
            Start Session
          </button>

          {/* Selected Summary */}
          {selectedModel && selectedVoice && (
            <div className="text-center space-y-1 animate-in fade-in duration-300">
              <div className="text-sm text-zinc-500">
                Starting with{' '}
                <span className="text-blue-400 font-medium font-mono">
                  {selectedModel}
                </span>
                {' '}using{' '}
                <span className="text-green-400 font-medium">{selectedVoice}</span> voice
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
