import { useEffect, useRef } from 'react';
import { useProjectStore } from '@/lib/stores/projectStore';
import { useConversationStore } from '@/lib/stores/conversationStore';
import { AudioPlayback } from '@/lib/audio';

export function useGeminiLiveConnection(sessionId: string) {
    const projectStore = useProjectStore();
    const conversationStore = useConversationStore();
    const audioPlayback = useRef(new AudioPlayback());
    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        // Single WebSocket for everything
        const ws = new WebSocket(`ws://localhost:8000/ws/live/${sessionId}`);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log('Connected to Gemini Live');
        };

        ws.onmessage = async (event) => {
            const message = JSON.parse(event.data);

            switch (message.type) {
                // Audio output from Gemini Live
                case 'audio_output':
                    // Play audio
                    await audioPlayback.current.playAudioChunk(message.data);
                    break;

                // Text transcript from Gemini Live (simultaneous with audio)
                case 'text_output':
                    if (message.role === 'assistant') {
                        // Update streaming text display
                        conversationStore.updateCurrentMessage(message.text);
                    } else if (message.role === 'user') {
                        // User's speech was transcribed
                        conversationStore.addMessage({
                            role: 'user',
                            text: message.text,
                            timestamp: message.timestamp
                        });
                    }
                    break;

                // Turn complete - commit streaming message
                case 'turn_complete':
                    conversationStore.commitCurrentMessage();
                    break;

                // Project brief updates
                case 'brief_updated':
                    projectStore.updateBrief(message.brief);
                    break;

                // Agent status
                case 'agent_thinking':
                    projectStore.setCurrentAgent(message.agent_id);
                    projectStore.setThinking(true);
                    break;

                case 'agent_completed':
                    projectStore.setThinking(false);
                    break;

                // Asset ready events
                case 'strategy_complete':
                case 'images_ready':
                case 'video_ready':
                case 'audio_ready':
                case 'code_ready':
                    projectStore.addAsset(message.agent_id, message.output);
                    break;
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
        };

        return () => {
            ws.close();
            audioPlayback.current.stop();
        };
    }, [sessionId]);

    // Return function to send audio
    return {
        sendAudio: (audioData: ArrayBuffer) => {
            const ws = wsRef.current;
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'audio_input',
                    data: btoa(String.fromCharCode(...new Uint8Array(audioData)))
                }));
            }
        }
    };
}
