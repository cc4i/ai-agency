export class AudioCapture {
    private mediaRecorder: MediaRecorder | null = null;
    private audioContext: AudioContext | null = null;
    private ws: WebSocket;

    constructor(ws: WebSocket) {
        this.ws = ws;
    }

    async startRecording() {
        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Create audio context for processing
        this.audioContext = new AudioContext({ sampleRate: 16000 });

        // Create media recorder
        this.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'  // Or PCM based on Gemini requirements
        });

        // Handle audio chunks
        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                this.sendAudioChunk(event.data);
            }
        };

        // Start recording with time slice (send chunks every 100ms)
        this.mediaRecorder.start(100);
    }

    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
    }

    private async sendAudioChunk(audioBlob: Blob) {
        // Convert to base64
        const reader = new FileReader();
        reader.onloadend = () => {
            const base64 = (reader.result as string).split(',')[1];

            // Send via WebSocket
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'audio_input',
                    data: base64,
                    timestamp: Date.now()
                }));
            }
        };
        reader.readAsDataURL(audioBlob);
    }
}

export class VoiceActivityDetector {
    private analyser: AnalyserNode;
    private threshold = 0.02;  // Adjust based on testing

    constructor(stream: MediaStream) {
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        this.analyser = audioContext.createAnalyser();
        this.analyser.fftSize = 512;
        source.connect(this.analyser);
    }

    isVoiceDetected(): boolean {
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);

        // Calculate average volume
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        const normalized = average / 255;

        return normalized > this.threshold;
    }

    getAudioLevel(): number {
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);
        return dataArray.reduce((a, b) => a + b) / dataArray.length / 255;
    }
}

export class AudioPlayback {
    private audioQueue: AudioBuffer[] = [];
    private isPlaying = false;

    async playAudioChunk(base64Audio: string) {
        // Decode base64 to audio buffer
        const audioData = atob(base64Audio);
        const arrayBuffer = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
            arrayBuffer[i] = audioData.charCodeAt(i);
        }

        // Create audio context
        const audioContext = new AudioContext();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.buffer);

        // Queue for playback
        this.audioQueue.push(audioBuffer);

        // Start playback if not already playing
        if (!this.isPlaying) {
            this.playQueue(audioContext);
        }
    }

    private async playQueue(audioContext: AudioContext) {
        this.isPlaying = true;

        while (this.audioQueue.length > 0) {
            const buffer = this.audioQueue.shift()!;
            const source = audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(audioContext.destination);

            // Play and wait for completion
            source.start();
            await new Promise(resolve => {
                source.onended = resolve;
            });
        }

        this.isPlaying = false;
    }

    stop() {
        this.audioQueue = [];
        this.isPlaying = false;
    }
}
