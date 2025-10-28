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
  data: any;
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

        switch (message.type) {
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

          case 'producer_speaking_start':
            setProducerSpeaking(true);
            break;

          case 'producer_speaking_end':
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
            console.log('Unknown message type:', message.type);
        }
      } catch (error) {
        console.error('Error handling WebSocket message:', error);
      }
    },
    [setBrief, updateBrief, addAsset, updateAgentStatus, addAnnouncement, setProducerSpeaking]
  );

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
      wsRef.current.send(audioData);
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
