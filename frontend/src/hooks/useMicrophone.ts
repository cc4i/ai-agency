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
  chunkDuration?: number; // milliseconds
  sampleRate?: number;
}

export function useMicrophone({
  onAudioData,
  chunkDuration = 100,
  sampleRate = 16000,
}: UseMicrophoneOptions) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number>();

  const { setMicrophoneActive, setAudioLevel } = useProjectStore();

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate,
        },
      });

      // Create audio context for visualization
      audioContextRef.current = new AudioContext({ sampleRate });
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);

      // Start audio level monitoring
      monitorAudioLevel();

      // Create media recorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          event.data.arrayBuffer().then(onAudioData);
        }
      };

      mediaRecorder.start(chunkDuration);
      mediaRecorderRef.current = mediaRecorder;

      setIsRecording(true);
      setMicrophoneActive(true);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to access microphone';
      setError(errorMessage);
      console.error('Microphone error:', err);
    }
  }, [onAudioData, chunkDuration, sampleRate, setMicrophoneActive]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      mediaRecorderRef.current = null;
    }

    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    setIsRecording(false);
    setMicrophoneActive(false);
    setAudioLevel(0);
  }, [setMicrophoneActive, setAudioLevel]);

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
