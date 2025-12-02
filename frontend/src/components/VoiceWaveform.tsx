/**
 * Voice Waveform Visualizer - Real-time audio frequency visualization.
 *
 * Features:
 * - Unified waveform that shows active speaker
 * - AI speaking takes priority (since mic picks up speaker audio)
 * - Color-coded: cyan for user, purple for AI, gray for idle
 * - Glow effects on active bars
 * - Idle breathing animation when recording but silent
 */

'use client';

import { cn } from '@/lib/utils';
import { useState, useEffect } from 'react';

interface VoiceWaveformProps {
  userFrequencies: number[];   // 0-1 normalized, 16 bars
  aiFrequencies: number[];     // 0-1 normalized, 16 bars
  isRecording: boolean;
  isAiSpeaking: boolean;
  compact?: boolean;           // Compact mode for smaller displays
}

export function VoiceWaveform({
  userFrequencies,
  aiFrequencies,
  isRecording,
  isAiSpeaking,
  compact = false,
}: VoiceWaveformProps) {
  // Idle animation tick (for breathing effect when silent)
  const [tick, setTick] = useState(0);

  // Update tick for idle animation
  useEffect(() => {
    if (!isRecording && !isAiSpeaking) return;

    const interval = setInterval(() => {
      setTick(t => t + 1);
    }, 100);

    return () => clearInterval(interval);
  }, [isRecording, isAiSpeaking]);

  // Don't render if not recording and not speaking
  if (!isRecording && !isAiSpeaking) {
    return null;
  }

  const barCount = compact ? 10 : 20;
  const barHeight = compact ? 16 : 22;
  const barWidth = compact ? 2 : 2.5;
  const gap = compact ? 1 : 1;

  // Downsample frequencies if needed
  const downsample = (frequencies: number[], targetCount: number) => {
    if (frequencies.length <= targetCount) return frequencies;
    const step = Math.floor(frequencies.length / targetCount);
    return Array.from({ length: targetCount }, (_, i) => {
      let sum = 0;
      for (let j = 0; j < step; j++) {
        sum += frequencies[i * step + j] || 0;
      }
      return sum / step;
    });
  };

  const userBars = downsample(userFrequencies, barCount);
  const aiBars = downsample(aiFrequencies, barCount);

  // Check if there's actual audio activity (not just noise floor)
  // Use higher threshold for user to filter environmental noise and speaker bleed
  const hasUserActivity = userBars.some(v => v > 0.18);
  const hasAiActivity = aiBars.some(v => v > 0.08);

  // Determine active speaker:
  // - AI speaking takes priority (isAiSpeaking flag is authoritative)
  // - When AI is speaking, ignore user mic input (it's just picking up speaker audio)
  // - Only show user activity when AI is NOT speaking
  const activeSource: 'ai' | 'user' | 'idle' =
    isAiSpeaking ? 'ai' :
    (isRecording && hasUserActivity) ? 'user' :
    'idle';

  // Use appropriate frequency data based on active source
  const activeBars = activeSource === 'ai' ? aiBars : userBars;
  const hasActivity = activeSource === 'ai' ? hasAiActivity : hasUserActivity;

  // Labels and colors based on active source
  const label = activeSource === 'ai' ? 'AI' : activeSource === 'user' ? 'You' : 'Listening';

  const getBarColor = () => {
    if (activeSource === 'ai') {
      return 'bg-gradient-to-t from-purple-500 to-purple-300';
    } else if (activeSource === 'user') {
      return 'bg-gradient-to-t from-cyan-500 to-cyan-300';
    }
    return 'bg-zinc-600';
  };

  const getGlowColor = () => {
    if (activeSource === 'ai') {
      return 'rgba(168, 85, 247, 0.6)'; // purple
    } else if (activeSource === 'user') {
      return 'rgba(34, 211, 238, 0.6)'; // cyan
    }
    return 'none';
  };

  const getLabelColor = () => {
    if (activeSource === 'ai') return 'text-purple-400';
    if (activeSource === 'user') return 'text-cyan-400';
    return 'text-zinc-500';
  };

  return (
    <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-zinc-800/50">
      <div className="flex items-center gap-1.5">
        {/* Waveform bars */}
        <div
          className="flex items-center justify-center gap-px h-6"
          style={{ gap: `${gap}px` }}
        >
          {activeBars.map((level, i) => {
            // Idle breathing animation when not actively speaking
            const idleHeight = activeSource === 'idle'
              ? 3 + Math.sin((tick / 3) + i * 0.5) * 2
              : 0;

            const finalHeight = hasActivity
              ? Math.max(3, level * barHeight)
              : Math.max(2, idleHeight);

            return (
              <div
                key={`bar-${i}`}
                className={cn(
                  'rounded-full transition-all',
                  hasActivity ? 'duration-[50ms]' : 'duration-300',
                  getBarColor()
                )}
                style={{
                  width: `${barWidth}px`,
                  height: `${finalHeight}px`,
                  boxShadow: hasActivity && level > 0.25
                    ? `0 0 ${level * 6}px ${getGlowColor()}`
                    : 'none',
                }}
              />
            );
          })}
        </div>

        {/* Label */}
        <span className={cn(
          'text-[9px] font-semibold uppercase tracking-wider min-w-[45px] transition-colors duration-200',
          getLabelColor()
        )}>
          {label}
        </span>
      </div>
    </div>
  );
}
