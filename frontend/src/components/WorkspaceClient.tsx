/**
 * Workspace Client - Main application interface.
 *
 * Layout:
 * - Top: Agent Status Bar
 * - Left: Asset Display (main content area)
 * - Right: Project Brief Panel
 * - Bottom: Producer Announcements
 * - Center Fixed: Microphone Interface
 */

'use client';

import { useEffect, useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMicrophone } from '@/hooks/useMicrophone';
import { ProjectBriefPanel } from './ProjectBriefPanel';
import { MicrophoneInterface } from './MicrophoneInterface';
import { AgentStatusBar } from './AgentStatusBar';
import { AssetDisplay } from './AssetDisplay';
import { ProducerAnnouncements } from './ProducerAnnouncements';
import { TranscriptDisplay } from './TranscriptDisplay'; // Import the new component
import { useProjectStore } from '@/stores/useProjectStore';

export default function WorkspaceClient() {
  const [sessionId, setSessionId] = useState<string>('');
  const [projectId, setProjectId] = useState<string>('');
  const [isInitialized, setIsInitialized] = useState(false);

  const { reset } = useProjectStore();

  // Initialize session and project IDs
  useEffect(() => {
    // Generate or retrieve session ID
    const storedSessionId = localStorage.getItem('session_id');
    if (storedSessionId) {
      setSessionId(storedSessionId);
    } else {
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
      localStorage.setItem('session_id', newSessionId);
      setSessionId(newSessionId);
    }

    // For demo, use Aura project
    // In production, this would be dynamic or selected by user
    const demoProjectId = 'aura_smart_sneaker';
    setProjectId(demoProjectId);

    setIsInitialized(true);

    // Reset store on mount
    reset();
  }, [reset]);

  // IMPORTANT: Call hooks unconditionally (Rules of Hooks)
  // Even if IDs aren't ready yet - the hooks will handle it
  const { sendAudio, sendTurnComplete, isConnected } = useWebSocket(sessionId, projectId);

  // Microphone
  const { isRecording, toggleRecording } = useMicrophone({
    onAudioData: sendAudio,
    onTurnComplete: undefined, // Not used - Gemini handles turn detection
    chunkDuration: 100,
    sampleRate: 16000, // Gemini Live API requires 16kHz input (outputs 24kHz)
    vadEnabled: false, // Disable frontend VAD - let Gemini's VAD handle it
  });

  // Render loading state AFTER hooks (Rules of Hooks - hooks must be called unconditionally)
  if (!isInitialized || !sessionId || !projectId) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-zinc-500">Initializing...</div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-black text-white flex flex-col overflow-hidden">
      {/* Agent Status Bar */}
      <AgentStatusBar />

      {/* Main Content Area */}
      <div className="relative flex flex-1 overflow-hidden min-h-0">
        {/* Left Sidebar - Project Brief */}
        <ProjectBriefPanel />

        {/* Main content container - Asset Display */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <AssetDisplay />
        </div>

        {/* Right Sidebar - Transcript */}
        <TranscriptDisplay />
      </div>

      {/* Producer Announcements - Bottom Panel */}
      <ProducerAnnouncements />

      {/* Microphone Interface - Fixed Center Bottom */}
      <MicrophoneInterface isRecording={isRecording} onToggle={toggleRecording} />

      {/* Session Info - Bottom Right */}
      <div className="fixed bottom-4 right-4 text-xs text-zinc-600">
        <div>Session: {sessionId}</div>
      </div>
    </div>
  );
}
