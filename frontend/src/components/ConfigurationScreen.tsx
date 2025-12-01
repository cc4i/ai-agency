/**
 * Configuration Screen - Model and Voice Selection (Compact)
 *
 * Compact single-screen layout for quick session start.
 * Row 1: Model selection (horizontal buttons)
 * Row 2: Voice selection (dropdown)
 */

'use client';

import { useState, useEffect, useMemo } from 'react';
import { Sparkles, Info, ChevronDown } from 'lucide-react';
import { API_BASE_URL } from '@/config';
import { SystemPromptEditor } from './SystemPromptEditor';

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

  // Flatten all voices for dropdown
  const allVoices = useMemo(() => {
    if (!options) return [];
    const voices: { name: string; personality: string; description: string; group: string }[] = [];
    Object.entries(options.voiceGroups).forEach(([groupKey, group]) => {
      Object.entries(group.voices).forEach(([voiceName, voice]) => {
        voices.push({
          name: voiceName,
          personality: voice.personality,
          description: voice.description,
          group: group.label,
        });
      });
    });
    return voices;
  }, [options]);

  // Get selected voice details
  const selectedVoiceDetails = useMemo(() => {
    return allVoices.find(v => v.name === selectedVoice);
  }, [allVoices, selectedVoice]);

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
    <div className="h-screen bg-gradient-to-br from-black via-purple-950/20 to-black text-white flex items-center justify-center p-6">
      <div className="w-full max-w-2xl space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-3">
            <Sparkles className="w-8 h-8 text-purple-400" />
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent">
              AI Agency Hub
            </h1>
          </div>
          <p className="text-zinc-500 text-sm">Select model and voice to start</p>
        </div>

        {/* Selection Card */}
        <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-6 space-y-6">
          {/* Model Selection - Vertical List */}
          <div className="space-y-3">
            <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
              Model
            </label>
            <div className="space-y-2">
              {Object.entries(options.models).map(([key, model]) => (
                <button
                  key={key}
                  onClick={() => setSelectedModel(key)}
                  className={`
                    w-full px-4 py-3 rounded-lg border text-left transition-all flex items-center gap-3
                    ${selectedModel === key
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-zinc-700 hover:border-zinc-600 hover:bg-zinc-800/50'
                    }
                  `}
                >
                  {/* Radio indicator */}
                  <div className={`
                    w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0
                    ${selectedModel === key ? 'border-blue-500' : 'border-zinc-600'}
                  `}>
                    {selectedModel === key && (
                      <div className="w-2 h-2 rounded-full bg-blue-500" />
                    )}
                  </div>
                  <span className={`font-mono text-sm ${selectedModel === key ? 'text-blue-300' : 'text-zinc-300'}`}>
                    {key}
                  </span>
                  {model.recommended && (
                    <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full border border-green-500/30 flex-shrink-0 ml-auto">
                      Recommended
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-zinc-800" />

          {/* Voice Selection - Dropdown */}
          <div className="space-y-3">
            <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
              Voice
            </label>
            <div className="relative">
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-100 appearance-none cursor-pointer hover:border-zinc-600 focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500/50 transition-colors"
              >
                {Object.entries(options.voiceGroups).map(([groupKey, group]) => (
                  <optgroup key={groupKey} label={group.label}>
                    {Object.entries(group.voices).map(([voiceName, voice]) => (
                      <option key={voiceName} value={voiceName}>
                        {voiceName} — {voice.personality}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500 pointer-events-none" />
            </div>
            {selectedVoiceDetails && (
              <p className="text-xs text-zinc-500 italic">
                &ldquo;{selectedVoiceDetails.description}&rdquo;
              </p>
            )}
          </div>

          {/* Divider */}
          <div className="border-t border-zinc-800" />

          {/* System Prompt Editor - Collapsible Advanced Section */}
          <SystemPromptEditor />
        </div>

        {/* Start Button */}
        <button
          onClick={handleStart}
          disabled={!selectedModel || !selectedVoice}
          className="w-full py-4 text-base font-semibold bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 transition-all shadow-lg shadow-purple-500/30 rounded-xl disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          <Sparkles className="w-5 h-5" />
          Start Session
        </button>
      </div>
    </div>
  );
}
