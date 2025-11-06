/**
 * Microphone hook for continuous audio capture.
 *
 * Features:
 * - Persistent microphone with visual indicator
 * - Real-time audio level visualization
 * - Automatic audio chunking for streaming
 * - Push-to-talk and always-on modes
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { useProjectStore } from '@/stores/useProjectStore';

interface UseMicrophoneOptions {
  onAudioData: (data: ArrayBuffer) => void;
  onTurnComplete?: () => void; // Called after silence duration
  chunkDuration?: number; // milliseconds
  sampleRate?: number;
  vadThreshold?: number; // Voice Activity Detection threshold (0-1)
  vadEnabled?: boolean; // Enable/disable VAD
  silenceDuration?: number; // ms of silence before turn complete (default 1500ms)
}

export function useMicrophone({
  onAudioData,
  onTurnComplete,
  chunkDuration = 100,
  sampleRate = 16000, // Gemini Live API requires 16kHz input (outputs 24kHz)
  vadThreshold = 0.01, // Lower threshold - let Gemini's VAD handle it
  vadEnabled = false, // Disable frontend VAD - let Gemini handle it
  silenceDuration = 1500, // Not used when VAD disabled
}: UseMicrophoneOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number>();

  const { setMicrophoneActive, setAudioLevel, isProducerSpeaking } = useProjectStore();

  const monitorAudioLevel = useCallback(() => {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

    const update = () => {
      if (!analyserRef.current) return;

      analyserRef.current.getByteFrequencyData(dataArray);

      // Calculate average volume
      const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      const normalized = average / 255; // Normalize to 0-1

      setAudioLevel(normalized);

      animationFrameRef.current = requestAnimationFrame(update);
    };

    update();
  }, [setAudioLevel]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate,
          channelCount: 1, // Mono audio
        },
      });

      // Create audio context for processing and visualization
      audioContextRef.current = new AudioContext({ sampleRate });
      const source = audioContextRef.current.createMediaStreamSource(stream);

      // Create analyser for visualization
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);

      // Start audio level monitoring
      monitorAudioLevel();

      // Create ScriptProcessor to capture raw PCM audio
      // Note: ScriptProcessor is deprecated but widely supported
      // For production, consider using AudioWorklet
      const bufferSize = 4096; // Larger chunks for better quality and smoother streaming (~256ms at 16kHz)
      const processor = audioContextRef.current.createScriptProcessor(bufferSize, 1, 1);

      let audioChunkCount = 0;
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // Turn-taking: Don't send audio if Gemini is speaking
        const currentProducerSpeaking = useProjectStore.getState().isProducerSpeaking;
        if (currentProducerSpeaking) {
          // Gemini is speaking, don't interrupt
          console.log('[Turn-Taking] Gemini speaking, pausing user audio');
          return;
        }

        // Convert Float32Array to Int16Array (PCM16)
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          // Clamp and convert to 16-bit integer
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Send ALL audio (including silence) - let Gemini's VAD handle detection
        audioChunkCount++;
        if (audioChunkCount % 10 === 0) {
          console.log(`[Mic] Captured and sending audio chunk #${audioChunkCount} (${pcm16.buffer.byteLength} bytes)`);
        }
        onAudioData(pcm16.buffer);
      };

      source.connect(processor);
      processor.connect(audioContextRef.current.destination);

      // Store reference for cleanup
      (audioContextRef.current as any).processor = processor;

      setIsRecording(true);
      setMicrophoneActive(true);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to access microphone';
      setError(errorMessage);
      console.error('Microphone error:', err);
    }
  }, [onAudioData, sampleRate, setMicrophoneActive, monitorAudioLevel]);

  const stopRecording = useCallback(() => {
    // Stop MediaRecorder if it exists (legacy)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      mediaRecorderRef.current = null;
    }

    // Stop audio context and processor
    if (audioContextRef.current) {
      // Disconnect processor
      const processor = (audioContextRef.current as any).processor;
      if (processor) {
        processor.disconnect();
      }

      // Stop all tracks
      const state = audioContextRef.current.state;
      if (state !== 'closed') {
        audioContextRef.current.close();
      }
      audioContextRef.current = null;
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    setIsRecording(false);
    setMicrophoneActive(false);
    setAudioLevel(0);
  }, [setMicrophoneActive, setAudioLevel]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, [stopRecording]);

  return {
    isRecording,
    error,
    startRecording,
    stopRecording,
    toggleRecording,
  };
}
