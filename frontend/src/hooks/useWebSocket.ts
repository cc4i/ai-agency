/**
 * WebSocket hook for bidirectional audio streaming and real-time updates.
 *
 * Handles:
 * - Audio streaming (Frontend ↔ Backend ↔ Gemini Live)
 * - Project Brief real-time sync
 * - Asset updates
 * - Agent status updates
 * - Producer announcements
 */

import { useEffect, useRef, useCallback } from 'react';
import { useProjectStore } from '@/stores/useProjectStore';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

interface WebSocketMessage {
  type: string;
  data?: any;
  mime_type?: string;
  text?: string;
  timestamp?: string;
  role?: string;
  agent_id?: string;
  status?: string;
  current_task?: string;
  asset_type?: string;
  asset_data?: any;
  announcement_type?: string;
  message?: string;
  changed_fields?: string[];
  brief?: any;
}

export function useWebSocket(sessionId: string, projectId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const audioContextRef = useRef<AudioContext | null>(null);

  const {
    setBrief,
    updateBrief,
    addAsset,
    updateAgentStatus,
    addAnnouncement,
    setConnected,
    setProducerSpeaking,
  } = useProjectStore();

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        // Check if binary audio data
        if (event.data instanceof Blob) {
          handleAudioData(event.data);
          return;
        }

        // Parse JSON message
        const message: WebSocketMessage = JSON.parse(event.data);
        console.log('[WebSocket] Received:', message.type);

        switch (message.type) {
          case 'audio_output':
            // Handle audio output from Gemini Live
            if (message.data) {
              handleAudioOutput(message.data, message.mime_type || 'audio/pcm');
            }
            setProducerSpeaking(false); // Audio chunk received, might be done speaking
            break;

          case 'text_output':
            // Handle text transcript
            if (message.text) {
              console.log('[Producer]:', message.text);
              addAnnouncement({
                message: message.text,
                type: 'info',
                timestamp: message.timestamp || new Date().toISOString(),
              });
            }
            break;

          case 'turn_complete':
            console.log('[WebSocket] Turn complete');
            setProducerSpeaking(false);
            break;

          case 'brief_update':
            if (message.data.brief) {
              updateBrief(message.data.brief, message.data.changed_fields || []);
            }
            break;

          case 'brief_init':
            if (message.data.brief) {
              setBrief(message.data.brief);
            }
            break;

          case 'asset_added':
            addAsset(message.data.agent_id, {
              type: message.data.asset_type,
              data: message.data.asset_data,
              created_at: new Date().toISOString(),
            });
            break;

          case 'agent_status':
            updateAgentStatus(message.data.agent_id, {
              agent_id: message.data.agent_id,
              status: message.data.status,
              current_task: message.data.current_task,
            });
            break;

          case 'producer_announcement':
            addAnnouncement({
              message: message.data.message,
              type: message.data.announcement_type || 'info',
              timestamp: new Date().toISOString(),
            });
            break;

          case 'interrupted':
            console.log('[WebSocket] Turn interrupted');
            setProducerSpeaking(false);
            break;

          case 'error':
            console.error('WebSocket error:', message.data);
            addAnnouncement({
              message: message.data.message || 'An error occurred',
              type: 'error',
              timestamp: new Date().toISOString(),
            });
            break;

          default:
            console.log('Unknown message type:', message.type, message);
        }
      } catch (error) {
        console.error('Error handling WebSocket message:', error);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setBrief, updateBrief, addAsset, updateAgentStatus, addAnnouncement, setProducerSpeaking]
  );

  const handleAudioOutput = useCallback(async (audioBase64: string, mimeType: string) => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }

    try {
      console.log('[Audio] Received audio chunk, size:', audioBase64.length);

      // Decode base64 to ArrayBuffer
      const binary = atob(audioBase64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }

      // For PCM audio, we need to create an AudioBuffer manually
      if (mimeType === 'audio/pcm' || mimeType.includes('pcm')) {
        // PCM16 data
        const pcm16 = new Int16Array(bytes.buffer);

        // Convert to Float32 for Web Audio API
        const float32 = new Float32Array(pcm16.length);
        for (let i = 0; i < pcm16.length; i++) {
          float32[i] = pcm16[i] / 32768.0; // Convert to -1.0 to 1.0
        }

        // Create audio buffer
        const audioBuffer = audioContextRef.current.createBuffer(
          1, // mono
          float32.length,
          16000 // sample rate
        );

        audioBuffer.getChannelData(0).set(float32);

        // Play audio
        const source = audioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextRef.current.destination);
        source.start();

        console.log('[Audio] Playing PCM audio chunk');
      } else {
        // For other formats, try to decode
        const audioBuffer = await audioContextRef.current.decodeAudioData(bytes.buffer);
        const source = audioContextRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextRef.current.destination);
        source.start();

        console.log('[Audio] Playing decoded audio');
      }
    } catch (error) {
      console.error('Error playing audio output:', error);
    }
  }, []);

  const handleAudioData = useCallback(async (audioBlob: Blob) => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext();
    }

    try {
      const arrayBuffer = await audioBlob.arrayBuffer();
      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);

      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      source.start();
    } catch (error) {
      console.error('Error playing audio:', error);
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(`${WS_URL}/ws/${sessionId}/${projectId}`);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = handleMessage;

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);

      // Attempt reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Attempting to reconnect...');
        connect();
      }, 3000);
    };

    wsRef.current = ws;
  }, [sessionId, projectId, handleMessage, setConnected]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnected(false);
  }, [setConnected]);

  const sendAudio = useCallback((audioData: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Convert ArrayBuffer to base64
      const bytes = new Uint8Array(audioData);
      let binary = '';
      for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      const base64 = btoa(binary);

      // Send as JSON message
      const message = {
        type: 'audio_input',
        data: base64,
      };

      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    sendAudio,
    sendMessage,
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
  };
}
