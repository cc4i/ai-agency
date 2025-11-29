'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Camera, Monitor, X, Maximize2, Minimize2, Aperture, RefreshCw, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useProjectStore } from '@/stores/useProjectStore';

interface MultimodalInputProps {
    onFrameCapture: (dataUrl: string, type: 'video_input' | 'screen_input') => void;
    isActive: boolean;
    mode: 'camera' | 'screen' | null;
    onClose: () => void;
}

export function MultimodalInput({ onFrameCapture, isActive, mode, onClose }: MultimodalInputProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const onCloseRef = useRef(onClose);
    const [isMinimized, setIsMinimized] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [flash, setFlash] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    // Keep onClose ref updated
    useEffect(() => {
        onCloseRef.current = onClose;
    }, [onClose]);

    // Get concept previews and captured reference from project store
    const { previewConcepts, conceptIteration, capturedReference, clearSmartMirrorState } = useProjectStore();

    // Clear Smart Mirror state when window closes
    const handleClose = useCallback(() => {
        clearSmartMirrorState();
        onCloseRef.current();
    }, [clearSmartMirrorState]);

    // Debug logging
    useEffect(() => {
        if (previewConcepts.length) {
            console.log(`[MultimodalInput] Concept previews: ${previewConcepts.length} (iteration ${conceptIteration})`);
        }
        if (capturedReference) {
            console.log(`[MultimodalInput] Captured reference: ${capturedReference.id}`);
        }
    }, [previewConcepts, conceptIteration, capturedReference]);

    // Stop stream helper
    const stopStream = useCallback(() => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }
    }, []);

    // Initialize media stream - only depends on isActive and mode
    useEffect(() => {
        if (!isActive || !mode) {
            stopStream();
            setIsLoading(false);
            return;
        }

        // Skip if stream already exists and is active
        if (streamRef.current && streamRef.current.active) {
            console.log('[MultimodalInput] Stream already active, skipping initialization');
            return;
        }

        let isMounted = true;

        const startStream = async () => {
            try {
                setError(null);
                setIsLoading(true);
                let stream: MediaStream;

                if (mode === 'camera') {
                    // Request video with audio:false to avoid conflicts with existing mic stream
                    stream = await navigator.mediaDevices.getUserMedia({
                        video: {
                            width: { ideal: 640 },
                            height: { ideal: 480 },
                            facingMode: 'user'
                        },
                        audio: false // Explicitly disable audio to avoid conflict with mic
                    });
                } else {
                    // Screen share
                    stream = await navigator.mediaDevices.getDisplayMedia({
                        video: true,
                        audio: false
                    } as DisplayMediaStreamOptions);
                }

                // Check if component unmounted during async operation
                if (!isMounted) {
                    stream.getTracks().forEach(track => track.stop());
                    setIsLoading(false);
                    return;
                }

                // Verify we got a valid video track
                const videoTrack = stream.getVideoTracks()[0];
                if (!videoTrack) {
                    throw new Error('No video track available');
                }

                streamRef.current = stream;

                // Set loading false BEFORE setting srcObject so UI updates immediately
                setIsLoading(false);

                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                    console.log('[MultimodalInput] Camera stream attached to video element');
                } else {
                    console.warn('[MultimodalInput] videoRef is null, stream acquired but not attached');
                }

                // Handle stream ending (e.g. user stops screen share via browser UI)
                videoTrack.onended = () => {
                    if (isMounted) {
                        onCloseRef.current();
                    }
                };

                console.log('[MultimodalInput] Camera stream started successfully');

            } catch (err) {
                if (!isMounted) return;

                setIsLoading(false);
                console.error('Error accessing media device:', err);
                const message = err instanceof Error ? err.message : 'Unknown error';
                if (message.includes('Permission denied') || message.includes('NotAllowedError')) {
                    setError('Camera permission denied. Please allow camera access.');
                } else if (message.includes('in use') || message.includes('NotReadableError')) {
                    setError('Camera is in use by another application.');
                } else {
                    setError(`Failed to access ${mode === 'camera' ? 'camera' : 'screen'}: ${message}`);
                }
            }
        };

        startStream();

        return () => {
            isMounted = false;
            stopStream();
            setIsLoading(false);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isActive, mode]); // Only re-run when isActive or mode changes

    // Capture frame function - defined before useEffects that use it
    const captureFrame = useCallback((showFlash: boolean = true) => {
        if (!videoRef.current || !streamRef.current) {
            console.log('[MultimodalInput] captureFrame skipped: no video or stream ref');
            return;
        }

        const videoWidth = videoRef.current.videoWidth;
        const videoHeight = videoRef.current.videoHeight;

        // Skip if video dimensions not available yet
        if (videoWidth === 0 || videoHeight === 0) {
            console.log('[MultimodalInput] captureFrame skipped: video dimensions not ready');
            return;
        }

        const canvas = document.createElement('canvas');
        canvas.width = videoWidth;
        canvas.height = videoHeight;

        const ctx = canvas.getContext('2d');
        if (ctx) {
            ctx.drawImage(videoRef.current, 0, 0);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.7); // 70% quality JPEG

            // Validate dataUrl is not empty
            if (dataUrl.length < 100) {
                console.warn('[MultimodalInput] captureFrame: dataUrl too small, skipping');
                return;
            }

            // Send to parent
            if (mode) {
                console.log(`[MultimodalInput] Sending frame: ${videoWidth}x${videoHeight}, ${Math.round(dataUrl.length / 1024)}KB`);
                onFrameCapture(dataUrl, mode === 'camera' ? 'video_input' : 'screen_input');
            }

            if (showFlash) {
                setFlash(true);
                setTimeout(() => setFlash(false), 200);
            }
        }
    }, [mode, onFrameCapture]);

    // Auto-capture frames periodically (every 2 seconds) to keep context fresh
    // Use state to track if stream is ready
    const [streamReady, setStreamReady] = useState(false);

    // Update streamReady when stream changes
    useEffect(() => {
        if (streamRef.current && streamRef.current.active) {
            // Delay slightly to ensure video element has dimensions
            const timer = setTimeout(() => {
                setStreamReady(true);
                console.log('[MultimodalInput] Stream ready, starting auto-capture');
            }, 500);
            return () => clearTimeout(timer);
        } else {
            setStreamReady(false);
        }
    }, [isLoading]); // isLoading becomes false when stream is set

    useEffect(() => {
        if (!isActive || !streamReady || isMinimized) {
            console.log('[MultimodalInput] Auto-capture not started:', { isActive, streamReady, isMinimized });
            return;
        }

        console.log('[MultimodalInput] Starting auto-capture interval');

        // Capture immediately once
        captureFrame(false);

        const interval = setInterval(() => {
            captureFrame(false); // Silent capture
        }, 2000);

        return () => {
            console.log('[MultimodalInput] Stopping auto-capture interval');
            clearInterval(interval);
        };
    }, [isActive, streamReady, isMinimized, captureFrame]);

    if (!isActive) return null;

    return (
        <div
            className={cn(
                "absolute top-4 right-4 z-50 transition-all duration-300 ease-in-out",
                isMinimized ? "w-64" : "w-[480px]"
            )}
        >
            {/* Smart Mirror Window */}
            <div className="bg-black/90 backdrop-blur-md border border-purple-500/40 rounded-2xl overflow-hidden shadow-2xl shadow-purple-500/10 flex flex-col">

                {/* Header */}
                <div className="flex items-center justify-between px-4 py-3 bg-zinc-900/90 border-b border-zinc-800">
                    <div className="flex items-center gap-3">
                        {mode === 'camera' ? <Camera className="w-5 h-5 text-purple-400" /> : <Monitor className="w-5 h-5 text-blue-400" />}
                        <span className="text-sm font-semibold text-zinc-100">
                            {mode === 'camera' ? 'Smart Mirror' : 'Screen Share'}
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setIsMinimized(!isMinimized)}
                            className="p-1.5 hover:bg-zinc-800 rounded-lg text-zinc-400 hover:text-white transition-colors"
                        >
                            {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
                        </button>
                        <button
                            onClick={handleClose}
                            className="p-1.5 hover:bg-red-900/50 rounded-lg text-zinc-400 hover:text-red-400 transition-colors"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Video Content */}
                <div className={cn(
                    "relative bg-black group",
                    isMinimized ? "h-36" : "aspect-video"
                )}>
                    {/* Always render video element so ref is available */}
                    <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        className={cn(
                            "w-full h-full object-cover",
                            mode === 'camera' && "scale-x-[-1]", // Mirror effect for camera
                            (isLoading || error) && "invisible" // Hide but keep mounted
                        )}
                    />

                    {/* Error overlay */}
                    {error && (
                        <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm text-center p-6">
                            {error}
                        </div>
                    )}

                    {/* Loading overlay */}
                    {isLoading && !error && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                            <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
                            <span className="text-sm text-zinc-400">Starting camera...</span>
                        </div>
                    )}

                    {/* Flash Overlay */}
                    {!isLoading && !error && (
                        <div
                            className={cn(
                                "absolute inset-0 bg-white pointer-events-none transition-opacity duration-200",
                                flash ? "opacity-50" : "opacity-0"
                            )}
                        />
                    )}

                    {/* Controls Overlay (visible on hover) */}
                    {!isLoading && !error && (
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/30">
                            <button
                                onClick={() => captureFrame(true)}
                                className="bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-full p-4 border border-white/30 transition-all transform hover:scale-110 active:scale-95"
                                title="Snap Frame"
                            >
                                <Aperture className="w-8 h-8 text-white" />
                            </button>
                        </div>
                    )}
                </div>

                {/* Captured Reference (key frame sent to Art Director) */}
                {!isMinimized && capturedReference && (
                    <div className="p-3 bg-zinc-900/95 border-t border-zinc-800">
                        <div className="flex items-center gap-3">
                            <div className="w-16 h-16 rounded-lg overflow-hidden border border-green-500/50 flex-shrink-0">
                                <img
                                    src={capturedReference.url}
                                    alt="Captured reference"
                                    className="w-full h-full object-cover"
                                />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium text-green-400">✓ Reference Captured</p>
                                <p className="text-xs text-zinc-400 truncate">{capturedReference.description}</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Concept Gallery (Only visible when not minimized and has preview concepts) */}
                {!isMinimized && previewConcepts.length > 0 && (
                    <div className="p-4 bg-zinc-900/95 border-t border-zinc-800">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-medium text-purple-300 flex items-center gap-2">
                                <RefreshCw className="w-4 h-4" /> Concept Preview
                                {conceptIteration > 1 && (
                                    <span className="text-xs text-purple-400/70">(iteration {conceptIteration})</span>
                                )}
                            </span>
                            <span className="text-xs text-zinc-500">{previewConcepts.length} options</span>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                            {previewConcepts.map((concept, i: number) => (
                                <div
                                    key={concept.id}
                                    className="relative aspect-square rounded-xl overflow-hidden border-2 border-zinc-700 hover:border-purple-500 cursor-pointer transition-all hover:scale-[1.02] hover:shadow-lg hover:shadow-purple-500/20"
                                    title={`${concept.description} - Say "use the ${i === 0 ? 'first' : i === 1 ? 'second' : 'third'} one" to select`}
                                >
                                    <img
                                        src={concept.url}
                                        alt={`Concept ${i + 1}`}
                                        className="w-full h-full object-cover"
                                    />
                                    <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 to-transparent text-xs text-white px-2 py-1.5 truncate">
                                        #{i + 1}
                                    </div>
                                </div>
                            ))}
                        </div>
                        <p className="text-xs text-zinc-500 mt-2 text-center">
                            Say which one you like, or ask for changes
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
