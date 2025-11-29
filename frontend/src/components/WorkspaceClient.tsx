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
import { AgentStatusBar } from './AgentStatusBar';
import { AssetDisplay } from './AssetDisplay';
import { TranscriptDisplay } from './TranscriptDisplay';
import { ConfigurationScreen } from './ConfigurationScreen';
import { ChatInputBar } from './ChatInputBar';
import { CollapsibleAnnouncements } from './CollapsibleAnnouncements';
import { AddAgentModal } from './AddAgentModal';
import { MultimodalInput } from './MultimodalInput';
import { useProjectStore } from '@/stores/useProjectStore';

export default function WorkspaceClient() {
  const [sessionId, setSessionId] = useState<string>('');
  const [projectId, setProjectId] = useState<string>('');
  const [isInitialized, setIsInitialized] = useState(false);

  // Configuration state
  const [configComplete, setConfigComplete] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedVoice, setSelectedVoice] = useState<string>('');

  // Agent modal state
  const [showAddAgentModal, setShowAddAgentModal] = useState(false);

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

  // Handler for configuration completion
  const handleConfigComplete = (model: string, voice: string) => {
    setSelectedModel(model);
    setSelectedVoice(voice);
    setConfigComplete(true);
  };

  // Multimodal state
  const [multimodalMode, setMultimodalMode] = useState<'camera' | 'screen' | null>(null);
  const [isTranscriptOpen, setIsTranscriptOpen] = useState(true);

  // IMPORTANT: Call hooks unconditionally (Rules of Hooks)
  // Must be called before any conditional returns to ensure cleanup runs properly
  const { sendAudio, sendMessage, sendTurnComplete, isConnected, sendVideoFrame } = useWebSocket(
    sessionId,
    projectId,
    selectedModel,
    selectedVoice
  );

  // Microphone - also must be called unconditionally
  const { isRecording, toggleRecording } = useMicrophone({
    onAudioData: sendAudio,
    onTurnComplete: undefined, // Not used - Gemini handles turn detection
    chunkDuration: 100,
    sampleRate: 16000, // Gemini Live API requires 16kHz input (outputs 24kHz)
    vadEnabled: false, // Disable frontend VAD - let Gemini's VAD handle it
  });

  // Show configuration screen first (AFTER hooks are called)
  if (!configComplete) {
    return <ConfigurationScreen onStart={handleConfigComplete} />;
  }

  // Render loading state AFTER hooks (Rules of Hooks - hooks must be called unconditionally)
  if (!isInitialized || !sessionId || !projectId) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-zinc-500">Initializing...</div>
      </div>
    );
  }

  // Handler for reconfiguration - go back to config screen
  const handleReconfigure = () => {
    // Reset configuration state to show config screen again
    setConfigComplete(false);

    // Clear model and voice to trigger WebSocket disconnect
    // This is important because useWebSocket won't connect without valid model/voice
    setSelectedModel('');
    setSelectedVoice('');

    // Reset project store
    reset();

    // WebSocket will disconnect automatically via useEffect cleanup when dependencies change
  };

  // Handler for sending text messages
  const handleSendText = (text: string) => {
    sendMessage({
      type: 'text',
      text: text,
    });
  };

  // Handler for sending images
  const handleSendImage = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const base64 = e.target?.result as string;
      sendMessage({
        type: 'image',
        data: base64,
      });
    };
    reader.readAsDataURL(file);
  };

  // Handler for frame capture
  const handleFrameCapture = (dataUrl: string, type: 'video_input' | 'screen_input') => {
    if (sendVideoFrame) {
      sendVideoFrame(dataUrl, type);
    }
  };

  return (
    <div className="h-screen bg-black text-white flex flex-col overflow-hidden">
      {/* Agent Status Bar */}
      <AgentStatusBar
        onReconfigure={handleReconfigure}
        selectedModel={selectedModel}
        selectedVoice={selectedVoice}
        onAddAgent={() => setShowAddAgentModal(true)}
        isConnected={isConnected}
      />

      {/* Add Agent Modal */}
      <AddAgentModal
        isOpen={showAddAgentModal}
        onClose={() => setShowAddAgentModal(false)}
      />

      {/* Main Content Area */}
      <div className="relative flex flex-1 overflow-hidden min-h-0">
        {/* Left Sidebar - Project Brief */}
        <ProjectBriefPanel />

        {/* Main content container - Asset Display */}
        <div className="flex-1 flex flex-col overflow-hidden relative">
          <AssetDisplay sendMessage={sendMessage} />

          {/* Smart Mirror (Multimodal Input) */}
          <MultimodalInput
            isActive={!!multimodalMode}
            mode={multimodalMode}
            onClose={() => setMultimodalMode(null)}
            onFrameCapture={handleFrameCapture}
          />
        </div>

        {/* Right Sidebar - Transcript (Foldable) */}
        <div
          className={`transition-all duration-300 ease-in-out border-l border-zinc-800/50 flex flex-col bg-zinc-950/80 ${isTranscriptOpen ? 'w-72' : 'w-10'}`}
        >
          <div className="flex items-center justify-between p-2 border-b border-zinc-800/50">
            {isTranscriptOpen && (
              <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                Conversation Transcript
              </span>
            )}
            <button
              onClick={() => setIsTranscriptOpen(!isTranscriptOpen)}
              className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-white transition-colors"
              title={isTranscriptOpen ? "Collapse transcript" : "Expand transcript"}
            >
              {isTranscriptOpen ? '»' : '«'}
            </button>
          </div>
          {isTranscriptOpen && (
            <div className="flex-1 overflow-hidden">
              <TranscriptDisplay />
            </div>
          )}
        </div>
      </div>

      {/* Chat Input Bar - Above Announcements */}
      <ChatInputBar
        onSendText={handleSendText}
        onSendImage={handleSendImage}
        onToggleMic={toggleRecording}
        onToggleCamera={() => setMultimodalMode(multimodalMode === 'camera' ? null : 'camera')}
        onToggleScreenShare={() => setMultimodalMode(multimodalMode === 'screen' ? null : 'screen')}
        isRecording={isRecording}
        isCameraActive={multimodalMode === 'camera'}
        isScreenShareActive={multimodalMode === 'screen'}
      />

      {/* Collapsible Announcements - Bottom */}
      <CollapsibleAnnouncements />

      {/* Session Info - Bottom Right (only visible when announcements collapsed) */}
      <div className="fixed bottom-4 right-16 text-xs text-zinc-600 pointer-events-none">
        <div>Session: {sessionId}</div>
      </div>
    </div>
  );
}
