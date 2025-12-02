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
import { logger } from '@/utils/logger';

import { WS_BASE_URL } from '@/config';

const WS_URL = WS_BASE_URL;

interface WebSocketMessage {
  type: string;
  data?: any;
  mime_type?: string;
  text?: string;
  timestamp?: string;
  role?: 'user' | 'assistant';
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

export function useWebSocket(
  sessionId: string,
  projectId: string,
  model: string,
  voice: string
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const nextPlayTimeRef = useRef<number>(0); // Track scheduled playback time for gapless audio
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null); // Track active source for interruption
  const transcriptBuffer = useRef<{ role: 'user' | 'assistant'; text: string } | null>(null);

  // Audio processing chain - create once and reuse
  const audioFilterRef = useRef<BiquadFilterNode | null>(null);
  const audioCompressorRef = useRef<DynamicsCompressorNode | null>(null);

  // AI audio analyser for waveform visualization
  const aiAnalyserRef = useRef<AnalyserNode | null>(null);
  const aiAnalyserFrameRef = useRef<number | null>(null);

  // Audio processing toggle - set to false to bypass filter/compressor for testing
  const enableAudioProcessing = useRef<boolean>(false); // Toggle this to test raw audio

  const sessionPrefix = `[Session: ${sessionId.slice(0, 8)}...][Project: ${projectId}][Model: ${model}][Voice: ${voice}]`;

  const {
    setBrief,
    updateBrief,
    addAsset,
    updateAgentStatus,
    addAnnouncement,
    addTranscriptMessage,
    appendLiveTranscript,
    setLiveTranscript,
    setConnected,
    setProducerSpeaking,
    setPreviewConcepts,
    setCapturedReference,
    setAiFrequencyData,
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
        logger.debug(`${sessionPrefix} [WebSocket] ⬇ Received: ${message.type}`);

        switch (message.type) {
          case 'audio_output':
            // Handle audio output from Gemini Live
            if (message.data) {
              setProducerSpeaking(true); // Producer is speaking
              handleAudioOutput(message.data, message.mime_type || 'audio/pcm');
            }
            break;

          case 'text_output':
            // Handle real-time transcript with live display
            if (message.text && message.role) {
              const role = message.role as 'user' | 'assistant';

              // Check if role changed - commit previous buffer first
              if (transcriptBuffer.current && transcriptBuffer.current.role !== role) {
                if (transcriptBuffer.current.text.trim()) {
                  addTranscriptMessage({
                    ...transcriptBuffer.current,
                    timestamp: new Date().toISOString(),
                  });
                }
                transcriptBuffer.current = null;
              }

              // Append to buffer
              if (transcriptBuffer.current && transcriptBuffer.current.role === role) {
                transcriptBuffer.current.text += message.text;
              } else {
                transcriptBuffer.current = { role, text: message.text };
              }

              // Update live transcript for immediate display
              appendLiveTranscript(role, message.text);
            }
            break;

          case 'turn_complete':
            console.log('[WebSocket] Turn complete');
            setProducerSpeaking(false);
            // Commit the buffered transcript for the completed turn
            if (transcriptBuffer.current) {
              addTranscriptMessage({
                ...transcriptBuffer.current,
                timestamp: new Date().toISOString(),
              });
              transcriptBuffer.current = null; // Reset buffer
            }
            // Clear live transcript (addTranscriptMessage also does this, but be explicit)
            setLiveTranscript(null);
            break;

          case 'brief_update':
            if (message.data.brief) {
              // Debug: Log the update
              const changedFields = message.data.changed_fields || [];
              console.log(`[WebSocket] brief_update received, changed_fields: ${changedFields.join(', ')}`);

              // Debug: Log reference_images specifically
              const refImages = message.data.brief.reference_images;
              if (refImages) {
                console.log(`[WebSocket] brief_update has ${refImages.length} reference_images`);
                refImages.forEach((img: any, i: number) => {
                  const urlLen = img.url?.length || 0;
                  console.log(`[WebSocket]   ref_img[${i}]: url_len=${urlLen}`);
                });
              }

              updateBrief(message.data.brief, changedFields);
            }
            break;

          case 'concept_preview':
            // Handle concept preview for Smart Mirror iteration flow
            if (message.data.concepts) {
              const concepts = message.data.concepts.map((c: any) => ({
                id: c.id || c.asset_id,
                url: c.url,
                description: c.description || c.prompt || 'Concept',
                iteration: message.data.iteration || 1,
              }));
              logger.info(`[WebSocket] Received ${concepts.length} concept previews (iteration ${message.data.iteration})`);
              setPreviewConcepts(concepts, message.data.iteration || 1);
            }
            break;

          case 'reference_captured':
            // Handle captured reference image for Smart Mirror display
            if (message.data.reference) {
              const ref = message.data.reference;
              const refUrl = ref.url || ref.data;
              logger.info(`[WebSocket] Reference captured: ${ref.id}`);
              logger.info(`[WebSocket] Reference URL length: ${refUrl?.length || 0}`);
              logger.info(`[WebSocket] Reference URL starts with: ${refUrl?.substring(0, 50) || 'N/A'}`);

              // Validate it's a proper data URI
              if (refUrl && !refUrl.startsWith('data:image')) {
                logger.error(`[WebSocket] ERROR: Reference URL is not a valid data URI!`);
              }

              setCapturedReference({
                id: ref.id || ref.reference_id,
                url: refUrl,
                description: ref.description || 'Captured reference',
                timestamp: ref.timestamp || Date.now(),
              });
            }
            break;

          case 'concept_selected':
            // Don't clear preview - keep concepts visible until Smart Mirror closes
            logger.info('[WebSocket] Concept selected and saved to brief');
            break;

          case 'brief_init':
            if (message.data.brief) {
              const brief = message.data.brief;
              setBrief(brief);

              // CRITICAL: Reconstruct assets from persisted brief fields
              // This ensures assets display after page refresh/reconnect
              logger.debug('[WebSocket] Reconstructing assets from brief...');

              // Reconstruct strategy assets (slogans + personas)
              if (brief.slogans?.length > 0 || brief.personas?.length > 0) {
                addAsset('strategy', {
                  type: 'slogans',
                  data: {
                    slogans: brief.slogans || [],
                    personas: brief.personas || [],
                  },
                  created_at: brief.updated_at || new Date().toISOString(),
                });
                logger.debug(`[WebSocket] ✓ Reconstructed strategy: ${brief.slogans?.length || 0} slogans, ${brief.personas?.length || 0} personas`);
              }

              // Reconstruct art director assets (hero images)
              if (brief.hero_images?.length > 0) {
                addAsset('art_director', {
                  type: 'images',
                  data: {
                    images: brief.hero_images,
                    current_generation: brief.current_generation || 1,
                    generation_history: brief.generation_history || [],
                    refinement_history: brief.image_refinement_history || {},
                  },
                  created_at: brief.updated_at || new Date().toISOString(),
                });
                logger.debug(`[WebSocket] ✓ Reconstructed hero images: ${brief.hero_images.length} images (Gen ${brief.current_generation || 1})`);
              }
            }
            break;

          case 'asset_added':
            // Log asset metadata without full base64 data
            const imageUrlInfo = message.data.asset_data?.images?.[0]?.url;
            const dataSizeKB = imageUrlInfo ? Math.round(imageUrlInfo.length / 1024) : null;

            // Validate data URI format
            let validationStatus = 'unknown';
            if (imageUrlInfo) {
              if (imageUrlInfo.startsWith('data:image')) {
                const parts = imageUrlInfo.split(',');
                if (parts.length === 2) {
                  const [header, b64Data] = parts;
                  validationStatus = `valid - header: ${header}, data: ${b64Data.length} chars`;

                  // Test base64 validity (first 100 chars)
                  try {
                    atob(b64Data.substring(0, 100));
                    validationStatus += ', base64 OK';
                  } catch (e) {
                    validationStatus += `, base64 INVALID: ${e}`;
                  }
                } else {
                  validationStatus = `invalid - ${parts.length} parts (expected 2)`;
                }
              } else {
                validationStatus = `not a data URI`;
              }
            }

            console.log('[WebSocket] asset_added received:', {
              agent_id: message.data.agent_id,
              asset_type: message.data.asset_type,
              asset_data_keys: message.data.asset_data ? Object.keys(message.data.asset_data) : 'null',
              first_image_size_kb: dataSizeKB,
              first_image_validation: validationStatus,
              image_count: message.data.asset_data?.images?.length || 0,
            });
            addAsset(message.data.agent_id, {
              type: message.data.asset_type,
              data: message.data.asset_data,
              created_at: new Date().toISOString(),
            });
            console.log('[WebSocket] asset_added stored in state');
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

            // Stop current audio immediately
            if (currentSourceRef.current) {
              try {
                currentSourceRef.current.stop();
                console.log('[Audio] 🛑 Stopped current source due to interruption');
              } catch (e) {
                // Ignore errors if already stopped
              }
              currentSourceRef.current = null;
            }

            // Clear queue and reset state
            audioQueueRef.current = [];
            isPlayingRef.current = false;
            nextPlayTimeRef.current = 0;

            setProducerSpeaking(false);
            transcriptBuffer.current = null; // Clear buffer on interruption
            break;

          case 'connection_established':
            console.log('[WebSocket] Connection established:', message.data);
            // Backend confirms connection is ready
            break;

          case 'status':
            console.log('[WebSocket] Status update:', message.message);
            // Backend sends status updates during initialization
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
            // Log unknown messages but sanitize base64 data
            const sanitizedMessage = JSON.parse(JSON.stringify(message));
            if (sanitizedMessage.data?.asset_data?.images) {
              sanitizedMessage.data.asset_data.images = sanitizedMessage.data.asset_data.images.map((img: any) => ({
                ...img,
                url: img.url?.startsWith('data:')
                  ? `[base64 data - ${Math.round(img.url.length / 1024)}KB]`
                  : img.url
              }));
            }
            console.log('Unknown message type:', message.type, sanitizedMessage);
        }
      } catch (error) {
        console.error('Error handling WebSocket message:', error);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setBrief, updateBrief, addAsset, updateAgentStatus, addAnnouncement, addTranscriptMessage, appendLiveTranscript, setLiveTranscript, setProducerSpeaking]
  );

  const initAudioChain = useCallback(() => {
    if (!audioContextRef.current) {
      // Higher quality 24kHz sample rate
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      logger.info(`[Audio Context] Created with sample rate: ${audioContextRef.current.sampleRate}`);
    }

    // Create filter and compressor ONCE and reuse them (only if processing enabled)
    if (enableAudioProcessing.current && !audioFilterRef.current && audioContextRef.current) {
      // Low-pass filter to reduce high-frequency noise
      audioFilterRef.current = audioContextRef.current.createBiquadFilter();
      audioFilterRef.current.type = 'lowpass';
      audioFilterRef.current.frequency.value = 8000; // Remove frequencies above 8kHz
      audioFilterRef.current.Q.value = 1;

      // Compressor to normalize volume and reduce clipping
      // UPDATED: Less aggressive settings to reduce artifacts
      audioCompressorRef.current = audioContextRef.current.createDynamicsCompressor();
      audioCompressorRef.current.threshold.value = -18; // CHANGED from -24 (less aggressive)
      audioCompressorRef.current.knee.value = 30;
      audioCompressorRef.current.ratio.value = 4; // CHANGED from 12 (gentler compression)
      audioCompressorRef.current.attack.value = 0.003;
      audioCompressorRef.current.release.value = 0.25;

      // Connect filter → compressor → destination (permanent chain)
      audioFilterRef.current.connect(audioCompressorRef.current);
      audioCompressorRef.current.connect(audioContextRef.current.destination);

      logger.info('[Audio Chain] ✓ Created filter + compressor chain (threshold: -18dB, ratio: 4:1)');
    } else if (!enableAudioProcessing.current) {
      logger.warn('[Audio Chain] ⚠️ Audio processing DISABLED - using raw audio');
    }
  }, []);

  // Monitor AI audio frequency data for waveform visualization
  const startAiFrequencyMonitor = useCallback(() => {
    if (!aiAnalyserRef.current) return;

    const dataArray = new Uint8Array(aiAnalyserRef.current.frequencyBinCount);
    const NUM_BARS = 16;

    const update = () => {
      if (!aiAnalyserRef.current || !isPlayingRef.current) {
        // Stop monitoring when not playing
        setAiFrequencyData(Array(16).fill(0));
        return;
      }

      aiAnalyserRef.current.getByteFrequencyData(dataArray);

      // Downsample to NUM_BARS
      const step = Math.floor(dataArray.length / NUM_BARS);
      const frequencies: number[] = [];
      for (let i = 0; i < NUM_BARS; i++) {
        let sum = 0;
        for (let j = 0; j < step; j++) {
          sum += dataArray[i * step + j] || 0;
        }
        frequencies.push((sum / step) / 255);
      }
      setAiFrequencyData(frequencies);

      aiAnalyserFrameRef.current = requestAnimationFrame(update);
    };

    update();
  }, [setAiFrequencyData]);

  const playNextAudioBuffer = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      setProducerSpeaking(false);
      setAiFrequencyData(Array(16).fill(0)); // Reset AI waveform
      if (aiAnalyserFrameRef.current) {
        cancelAnimationFrame(aiAnalyserFrameRef.current);
        aiAnalyserFrameRef.current = null;
      }
      console.log('[Audio Queue] ✓ Queue empty, producer finished speaking');
      return;
    }

    // Initialize audio chain if needed
    initAudioChain();

    if (!audioContextRef.current) {
      console.error('[Audio] Audio context not initialized');
      return;
    }

    // Only check filter if processing is enabled
    if (enableAudioProcessing.current && !audioFilterRef.current) {
      console.error('[Audio] Audio processing enabled but filter not initialized');
      return;
    }

    // Create AI analyser if not exists
    if (!aiAnalyserRef.current) {
      aiAnalyserRef.current = audioContextRef.current.createAnalyser();
      aiAnalyserRef.current.fftSize = 64;
      aiAnalyserRef.current.connect(audioContextRef.current.destination);
    }

    // Resume AudioContext if suspended (browser autoplay policy)
    if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume().then(() => {
        console.log('[Audio Context] Resumed from suspended state');
      });
    }

    const audioBuffer = audioQueueRef.current.shift()!;
    isPlayingRef.current = true;

    const source = audioContextRef.current.createBufferSource();
    source.buffer = audioBuffer;
    currentSourceRef.current = source; // Track active source

    // Connect source - either to processing chain or direct to destination
    // Always route through AI analyser for visualization
    if (enableAudioProcessing.current && audioFilterRef.current) {
      // source → filter → compressor → analyser → destination
      source.connect(audioFilterRef.current);
      // Reconnect compressor to analyser (if not already)
      if (audioCompressorRef.current && aiAnalyserRef.current) {
        audioCompressorRef.current.disconnect();
        audioCompressorRef.current.connect(aiAnalyserRef.current);
      }
      console.log('[Audio Queue] 🔊 Using audio processing (filter + compressor + analyser)');
    } else {
      // source → analyser → destination
      source.connect(aiAnalyserRef.current);
      console.log('[Audio Queue] 🔊 Bypassing audio processing (raw audio + analyser)');
    }

    // Start frequency monitoring if not already running
    if (!aiAnalyserFrameRef.current) {
      startAiFrequencyMonitor();
    }

    // Use scheduled playback for gapless audio
    const currentTime = audioContextRef.current.currentTime;
    const playTime = Math.max(currentTime, nextPlayTimeRef.current);

    source.start(playTime);

    // Schedule next chunk to start exactly when this one ends
    nextPlayTimeRef.current = playTime + audioBuffer.duration;

    console.log('[Audio Queue] ▶ Playing buffer (duration:', audioBuffer.duration.toFixed(2), 's) at time:', playTime.toFixed(3), ', queue size:', audioQueueRef.current.length);

    // Check for more buffers when this one finishes
    source.onended = () => {
      // Clear reference if this was the active source
      if (currentSourceRef.current === source) {
        currentSourceRef.current = null;
      }

      // Play next buffer if available
      if (audioQueueRef.current.length > 0) {
        playNextAudioBuffer();
      } else {
        // Reset timing for next turn
        nextPlayTimeRef.current = 0;
        isPlayingRef.current = false;
        setProducerSpeaking(false);
        setAiFrequencyData(Array(16).fill(0)); // Reset AI waveform
        if (aiAnalyserFrameRef.current) {
          cancelAnimationFrame(aiAnalyserFrameRef.current);
          aiAnalyserFrameRef.current = null;
        }
        console.log('[Audio Queue] ✓ All buffers played, producer finished speaking');
      }
    };
  }, [setProducerSpeaking, setAiFrequencyData, initAudioChain, startAiFrequencyMonitor]);

  const handleAudioOutput = useCallback(async (audioBase64: string, mimeType: string) => {
    // Initialize audio chain if needed
    initAudioChain();

    if (!audioContextRef.current) {
      console.error('[Audio] Audio context not initialized');
      return;
    }

    try {
      console.log('[Audio] ⬇ Received chunk:', audioBase64.length, 'chars, mime:', mimeType);

      // Decode base64 to ArrayBuffer
      const binary = atob(audioBase64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }

      console.log('[Audio] Decoded to', bytes.length, 'bytes');

      let audioBuffer: AudioBuffer;

      // For PCM audio, we need to create an AudioBuffer manually
      if (mimeType === 'audio/pcm' || mimeType.includes('pcm')) {
        // PCM16 data (16-bit = 2 bytes per sample)
        // Use DataView for explicit little-endian byte order handling
        const dataView = new DataView(bytes.buffer);
        const numSamples = bytes.length / 2; // 2 bytes per sample

        console.log('[Audio] Processing PCM16:', bytes.length, 'bytes =', numSamples, 'samples');

        // Convert to Float32 for Web Audio API with proper normalization
        const float32 = new Float32Array(numSamples);
        let maxSample = 0;
        let minSample = 0;
        let clippedCount = 0;
        let silentCount = 0;
        let sumSquares = 0;

        for (let i = 0; i < numSamples; i++) {
          // Read little-endian int16 (Gemini sends little-endian)
          const sample = dataView.getInt16(i * 2, true); // true = little-endian

          // Track statistics
          const absSample = Math.abs(sample);
          if (sample > maxSample) maxSample = sample;
          if (sample < minSample) minSample = sample;
          if (absSample > 30000) clippedCount++;
          if (absSample < 10) silentCount++;
          sumSquares += sample * sample;

          // Proper normalization: -32768 to 32767 → -1.0 to 1.0
          float32[i] = sample / 32768.0;
        }

        // Calculate RMS (Root Mean Square) for volume level
        const rms = Math.sqrt(sumSquares / numSamples);
        const rmsDb = 20 * Math.log10(rms / 32768);

        // Calculate zero-crossing rate (indicator of noise vs speech)
        let zeroCrossings = 0;
        for (let i = 1; i < numSamples; i++) {
          const dataView = new DataView(bytes.buffer);
          const prev = dataView.getInt16((i - 1) * 2, true);
          const curr = dataView.getInt16(i * 2, true);
          if ((prev >= 0 && curr < 0) || (prev < 0 && curr >= 0)) {
            zeroCrossings++;
          }
        }
        const zcr = zeroCrossings / numSamples;

        // Sample first 10 values for pattern analysis
        const firstSamples = [];
        for (let i = 0; i < Math.min(10, numSamples); i++) {
          const dataView = new DataView(bytes.buffer);
          firstSamples.push(dataView.getInt16(i * 2, true));
        }

        logger.info(`[Audio] PCM16 samples converted: ${numSamples}`);
        logger.info('[Audio] 📊 Quality Analysis:');
        logger.info(`  - Max amplitude: ${maxSample} (+) / Min: ${minSample} (-)`);
        logger.info(`  - Range: ${maxSample - minSample} / 65536 possible`);
        logger.info(`  - RMS level: ${rms.toFixed(1)} (${rmsDb.toFixed(1)} dB)`);
        logger.info(`  - Clipped samples: ${clippedCount} (${(clippedCount / numSamples * 100).toFixed(2)}%)`);
        logger.info(`  - Silent samples: ${silentCount} (${(silentCount / numSamples * 100).toFixed(2)}%)`);
        logger.info(`  - Zero-crossing rate: ${zcr.toFixed(4)} (noise indicator: >0.5 = likely noise)`);
        logger.info(`  - First 10 samples: ${firstSamples.join(', ')}`);

        // Detect issues
        if (clippedCount > numSamples * 0.01) {
          logger.warn('⚠️ [Audio] HIGH CLIPPING DETECTED - Audio may be distorted!');
        }
        if (rms < 100) {
          logger.warn('⚠️ [Audio] VERY LOW VOLUME - Audio may be barely audible');
        }
        if (maxSample === minSample) {
          logger.error('❌ [Audio] NO VARIATION - Audio is completely flat (DC offset or silence)');
        }
        if (zcr > 0.5) {
          logger.warn('⚠️ [Audio] HIGH ZERO-CROSSING RATE - May indicate noise or high-frequency artifacts');
        }

        // Provide quality verdict
        const qualityScore = (rms > 500 && rms < 10000 && clippedCount < numSamples * 0.01 && zcr < 0.3) ? '✅ GOOD' : '⚠️ NEEDS INVESTIGATION';
        logger.info(`[Audio] Quality verdict: ${qualityScore}`);

        // Create audio buffer - CRITICAL: must match AudioContext sample rate (24kHz)
        audioBuffer = audioContextRef.current.createBuffer(
          1, // mono
          float32.length,
          24000 // Gemini outputs at 24kHz
        );

        audioBuffer.getChannelData(0).set(float32);
        console.log('[Audio] ✓ PCM buffer created, duration:', audioBuffer.duration.toFixed(2), 's, rate: 24kHz');
      } else {
        // For other formats, try to decode
        audioBuffer = await audioContextRef.current.decodeAudioData(bytes.buffer);
        console.log('[Audio] ✓ Decoded buffer, duration:', audioBuffer.duration.toFixed(2), 's');
      }

      // Add to queue
      audioQueueRef.current.push(audioBuffer);
      console.log('[Audio Queue] Added to queue, total buffers:', audioQueueRef.current.length);

      // Start playing if not already playing
      if (!isPlayingRef.current) {
        console.log('[Audio Queue] Starting playback');
        playNextAudioBuffer();
      }
    } catch (error) {
      console.error('[Audio] ✗ Error processing audio:', error);
    }
  }, [playNextAudioBuffer, initAudioChain]);

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
    // Don't connect if IDs are empty
    if (!sessionId || !projectId || !model || !voice) {
      console.warn(`${sessionPrefix} [WebSocket] ⚠ Cannot connect: missing session, project ID, model, or voice`);
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log(`${sessionPrefix} [WebSocket] Already connected, skipping`);
      return;
    }

    // Close any existing connection
    if (wsRef.current) {
      console.log(`${sessionPrefix} [WebSocket] Closing existing connection before reconnect`);
      wsRef.current.close();
      wsRef.current = null;
    }

    // Include model and voice as query parameters
    const wsUrl = `${WS_URL}/ws/adk/${sessionId}/${projectId}?model=${encodeURIComponent(model)}&voice=${encodeURIComponent(voice)}`;
    console.log(`${sessionPrefix} [WebSocket] 🔌 Connecting to ${wsUrl} (ADK)`);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`${sessionPrefix} [WebSocket] ✓ Connected to backend`);
      setConnected(true);
    };

    ws.onmessage = handleMessage;

    ws.onerror = (error) => {
      console.error(`${sessionPrefix} [WebSocket] ✗ Error:`, error);
      setConnected(false);
    };

    ws.onclose = (event) => {
      console.log(`${sessionPrefix} [WebSocket] ✗ Disconnected (code: ${event.code}, reason: ${event.reason})`);
      setConnected(false);

      // Attempt reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log(`${sessionPrefix} [WebSocket] 🔄 Attempting to reconnect...`);
        connect();
      }, 3000);
    };

    wsRef.current = ws;
  }, [sessionId, projectId, model, voice, handleMessage, setConnected, sessionPrefix]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Disconnect and clean up audio chain
    if (audioFilterRef.current) {
      audioFilterRef.current.disconnect();
      audioFilterRef.current = null;
    }
    if (audioCompressorRef.current) {
      audioCompressorRef.current.disconnect();
      audioCompressorRef.current = null;
    }
    if (aiAnalyserRef.current) {
      aiAnalyserRef.current.disconnect();
      aiAnalyserRef.current = null;
    }
    if (aiAnalyserFrameRef.current) {
      cancelAnimationFrame(aiAnalyserFrameRef.current);
      aiAnalyserFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Clear audio queue and reset timing
    audioQueueRef.current = [];
    isPlayingRef.current = false;
    nextPlayTimeRef.current = 0;

    setConnected(false);
    setProducerSpeaking(false);
    setAiFrequencyData(Array(16).fill(0)); // Reset AI waveform
    console.log('[Audio] Cleaned up audio chain');
  }, [setConnected, setProducerSpeaking, setAiFrequencyData]);

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

      logger.debug(`[Audio] Sending ${bytes.byteLength} bytes (base64: ${base64.length} chars)`);
      wsRef.current.send(JSON.stringify(message));
    } else {
      logger.warn(`[Audio] Cannot send - WebSocket state: ${wsRef.current?.readyState}`);
    }
  }, []);

  const sendVideoFrame = useCallback((base64Data: string, type: 'video_input' | 'screen_input' = 'video_input') => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Remove data URL prefix if present for cleaner logging/processing
      const cleanBase64 = base64Data.replace(/^data:image\/\w+;base64,/, '');

      const message = {
        type: type,
        data: cleanBase64,
      };

      // Don't log full frame data to avoid console spam
      // logger.debug(`[Video] Sending ${type} frame (${cleanBase64.length} chars)`);
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const sendTurnComplete = useCallback(() => {
    // DEPRECATED: Do not send turn_complete for audio streaming
    // Gemini Live's built-in VAD automatically detects turn completion from silence
    // Sending explicit messages causes 1007 "invalid argument" errors
    console.log(`${sessionPrefix} [Turn Complete] Gemini VAD will auto-detect (no message sent)`);
  }, [sessionPrefix]);

  useEffect(() => {
    // Only connect if we have valid IDs, model, and voice
    if (sessionId && projectId && model && voice) {
      console.log(`${sessionPrefix} [WebSocket] useEffect triggered, connecting...`);
      connect();
    }

    return () => {
      console.log(`${sessionPrefix} [WebSocket] useEffect cleanup, disconnecting...`);
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, projectId, model, voice]); // Only depend on IDs and config, not connect/disconnect functions

  return {
    sendAudio,
    sendVideoFrame,
    sendMessage,
    sendTurnComplete,
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
  };
}
