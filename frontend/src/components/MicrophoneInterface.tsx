/**
 * Persistent Microphone Interface.
 *
 * Features:
 * - Always-visible microphone button
 * - Real-time audio level visualization
 * - Visual indicator when Producer is speaking
 * - Connection status display
 */

'use client';

import { useProjectStore } from '@/stores/useProjectStore';
import { cn } from '@/lib/utils';
import { Mic, MicOff } from 'lucide-react';

interface MicrophoneInterfaceProps {
  isRecording: boolean;
  onToggle: () => void;
}

export function MicrophoneInterface({ isRecording, onToggle }: MicrophoneInterfaceProps) {
  const { isConnected, isMicrophoneActive, isProducerSpeaking, audioLevel } = useProjectStore();

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50">
      <div className="flex flex-col items-center gap-4">
        {/* Connection status */}
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )}
          />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>

        {/* Producer speaking indicator */}
        {isProducerSpeaking && (
          <div className="text-sm text-blue-400 animate-pulse">Producer speaking...</div>
        )}

        {/* Microphone button with audio level visualization */}
        <div className="relative">
          {/* Audio level rings */}
          {isMicrophoneActive && audioLevel > 0.1 && (
            <>
              <div
                className="absolute inset-0 rounded-full bg-blue-500/30 animate-ping"
                style={{
                  transform: `scale(${1 + audioLevel * 0.5})`,
                }}
              />
              <div
                className="absolute inset-0 rounded-full bg-blue-500/20"
                style={{
                  transform: `scale(${1 + audioLevel * 0.3})`,
                }}
              />
            </>
          )}

          {/* Microphone button */}
          <button
            onClick={onToggle}
            disabled={!isConnected}
            className={cn(
              'relative w-20 h-20 rounded-full flex items-center justify-center transition-all',
              'border-2 shadow-lg',
              isRecording
                ? 'bg-blue-500 border-blue-400 hover:bg-blue-600'
                : 'bg-zinc-800 border-zinc-700 hover:bg-zinc-700',
              !isConnected && 'opacity-50 cursor-not-allowed',
              isProducerSpeaking && 'ring-4 ring-green-500/50'
            )}
          >
            {isRecording ? (
              <Mic className="w-8 h-8 text-white" />
            ) : (
              <MicOff className="w-8 h-8 text-zinc-400" />
            )}
          </button>
        </div>

        {/* Status text */}
        <div className="text-xs text-zinc-500">
          {!isConnected
            ? 'Connect to begin'
            : isRecording
            ? 'Listening...'
            : 'Click to activate microphone'}
        </div>

        {/* Audio level bar */}
        {isMicrophoneActive && (
          <div className="w-32 h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 transition-all duration-100"
              style={{ width: `${audioLevel * 100}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
