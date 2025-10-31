# Audio Debug Recording

## Overview

The backend includes an audio recording feature that saves all audio chunks sent to Gemini Live. This is useful for debugging audio quality issues, analyzing user speech patterns, or verifying audio data flow.

**Default**: OFF (disabled by default)

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Enable audio recording
SAVE_AUDIO_DEBUG=True

# Optional: Customize save directory (default: /tmp/audio_debug)
AUDIO_DEBUG_DIR=/path/to/audio/debug/folder
```

### Settings in Code

**File**: `app/config.py:40-41`

```python
save_audio_debug: bool = False  # Set to True to enable
audio_debug_dir: str = "/tmp/audio_debug"  # Customize directory
```

## How It Works

### 1. Initialization

When a Gemini Live session starts, if `save_audio_debug=True`:
- Creates debug directory if it doesn't exist
- Opens a new audio file for this session
- Filename: `audio_input_{session_id}_{timestamp}.pcm`

**File**: `app/services/gemini_live.py:134-142`

### 2. Recording

Every audio chunk received from the frontend is:
1. **First** saved to the debug file (if enabled)
2. **Then** sent to Gemini Live

This ensures we capture the exact audio data sent to the API.

**File**: `app/services/gemini_live.py:749-751`

```python
# Save audio to file for debugging (if enabled)
if self.audio_file_handle:
    self.audio_file_handle.write(audio_data)
    self.audio_file_handle.flush()  # Ensure data is written immediately
```

### 3. Cleanup

When the session ends, the audio file is closed.

**File**: `app/services/gemini_live.py:1952-1959`

## Audio File Format

### Specifications

- **Format**: Raw PCM (Pulse Code Modulation)
- **Sample Rate**: 16000 Hz (16 kHz)
- **Bit Depth**: 16-bit signed integer
- **Byte Order**: Little-endian (s16le)
- **Channels**: 1 (Mono)
- **File Extension**: `.pcm`

### Why PCM?

PCM is the raw, uncompressed audio format that:
- Gemini Live expects as input
- Has no encoding overhead
- Preserves exact audio quality
- Can be easily analyzed or converted

## Working with Recorded Audio

### Converting to WAV

WAV files are easier to play and share:

```bash
ffmpeg -f s16le -ar 16000 -ac 1 -i audio_input_abc12345_20250131_143000.pcm output.wav
```

**Parameters**:
- `-f s16le`: Input format (16-bit signed, little-endian)
- `-ar 16000`: Audio sample rate (16 kHz)
- `-ac 1`: Audio channels (mono)
- `-i`: Input file
- Output: `output.wav`

### Playing Audio Directly

Play PCM audio without conversion:

```bash
# Using ffplay
ffplay -f s16le -ar 16000 -ac 1 audio_input_abc12345_20250131_143000.pcm

# Using aplay (Linux)
aplay -f S16_LE -r 16000 -c 1 audio_input_abc12345_20250131_143000.pcm
```

### Analyzing Audio

Check audio properties:

```bash
# Get duration and size info
ffprobe -f s16le -ar 16000 -ac 1 audio_input_abc12345_20250131_143000.pcm

# Visualize waveform
ffmpeg -f s16le -ar 16000 -ac 1 -i audio_input_abc12345_20250131_143000.pcm \
       -filter_complex "showwavespic=s=1280x720" waveform.png
```

### Batch Convert All Recordings

Convert all PCM files in debug directory:

```bash
cd /tmp/audio_debug
for file in *.pcm; do
    ffmpeg -f s16le -ar 16000 -ac 1 -i "$file" "${file%.pcm}.wav"
done
```

## Example Log Output

### When Enabled

```
[Session: abc12345...] [Turn: 0] 💾 Saving audio to: /tmp/audio_debug/audio_input_abc12345_20250131_143052.pcm
[Session: abc12345...] [Turn: 0] 🎤 Starting new audio input (Turn: 0, Chunk #1)
[Session: abc12345...] [Turn: 0] 📤 Sent first audio chunk to Gemini (320 bytes, Turn: 0)
[Session: abc12345...] [Turn: 0] 🎤 Audio chunk #50 (size: 320 bytes)
...
[Session: abc12345...] [Turn: 0] 🎤 User stopped speaking (sent 127 audio chunks), waiting for Gemini response...
[Session: abc12345...] [Turn: 0] 💾 Closed audio debug file for session: abc12345
```

### When Disabled (Default)

No audio save messages appear:

```
[Session: abc12345...] [Turn: 0] 🎤 Starting new audio input (Turn: 0, Chunk #1)
[Session: abc12345...] [Turn: 0] 📤 Sent first audio chunk to Gemini (320 bytes, Turn: 0)
```

## Use Cases

### 1. Debugging Audio Quality Issues

If users report:
- Garbled speech recognition
- Missing audio segments
- Distorted output

Enable recording to:
- Verify audio is being received correctly
- Check for silence/noise in recordings
- Compare input vs. Gemini's interpretation

### 2. Analyzing Speech Patterns

For UX research:
- Average turn length
- Pause patterns
- Speaking rate
- Background noise levels

### 3. Reproducing Bugs

When bugs occur:
1. Enable recording
2. Reproduce the issue
3. Share the PCM file for analysis
4. Verify audio data integrity

### 4. Performance Testing

- Measure audio chunk sizes
- Verify streaming continuity
- Test network transmission quality

## Security & Privacy

### Important Warnings

⚠️ **Contains User Voice Data**: Recorded files contain actual user speech
⚠️ **Not Encrypted**: Files are stored as plain PCM on disk
⚠️ **Disk Space**: Can accumulate quickly (16 kHz mono ≈ 32 KB/second)

### Best Practices

1. **Only Enable for Debugging**: Turn off in production
2. **Secure Storage**: Save to encrypted directory if needed
3. **Regular Cleanup**: Delete old recordings to save space
4. **User Consent**: Inform users if recording in production
5. **Limit Retention**: Set up automatic cleanup after N days

### Recommended Cleanup

```bash
# Delete recordings older than 7 days
find /tmp/audio_debug -name "*.pcm" -mtime +7 -delete

# Or set up a cron job
0 0 * * * find /tmp/audio_debug -name "*.pcm" -mtime +7 -delete
```

## File Size Estimates

### Audio Data Rate

- **Sample Rate**: 16000 samples/second
- **Bit Depth**: 16 bits (2 bytes) per sample
- **Data Rate**: 16000 × 2 = 32,000 bytes/second = ~32 KB/s

### Example File Sizes

| Duration | File Size |
|----------|-----------|
| 10 seconds | ~320 KB |
| 30 seconds | ~960 KB |
| 1 minute | ~1.9 MB |
| 5 minutes | ~9.6 MB |
| 10 minutes | ~19.2 MB |

### Disk Space Planning

If each session averages 2 minutes of user speech:
- **1 session** ≈ 3.8 MB
- **10 sessions** ≈ 38 MB
- **100 sessions** ≈ 380 MB
- **1000 sessions** ≈ 3.8 GB

**Recommendation**: Set up automatic cleanup or use a dedicated debug volume.

## Troubleshooting

### Audio File Not Created

**Check**:
1. Is `SAVE_AUDIO_DEBUG=True` in `.env`?
2. Does the backend have write permissions for `AUDIO_DEBUG_DIR`?
3. Is the directory path valid?

**Test**:
```bash
# Create directory manually
mkdir -p /tmp/audio_debug

# Check permissions
ls -ld /tmp/audio_debug

# Should show: drwxr-xr-x or similar
```

### Audio File Is Empty

**Possible Causes**:
1. User didn't speak (no audio chunks sent)
2. Frontend not sending audio data
3. WebSocket connection failed before audio sent

**Verify**:
- Check logs for "Starting new audio input" messages
- Check frontend is capturing microphone input
- Verify WebSocket connection established

### Can't Play Recorded Audio

**Check Format Parameters**:
```bash
# Correct parameters
ffplay -f s16le -ar 16000 -ac 1 file.pcm

# Common mistakes
ffplay file.pcm  # ❌ Missing format
ffplay -ar 44100 file.pcm  # ❌ Wrong sample rate
```

### Audio Sounds Distorted

**Possible Issues**:
1. Wrong sample rate (should be 16000)
2. Wrong format (should be s16le)
3. Actual audio quality issue (debugging success!)

## References

- **Implementation**: `app/services/gemini_live.py:134-142, 749-751, 1952-1959`
- **Configuration**: `app/config.py:40-41`
- **Environment**: `.env.example:25-26`
- **FFmpeg Documentation**: https://ffmpeg.org/documentation.html
- **PCM Format**: https://en.wikipedia.org/wiki/Pulse-code_modulation

## Summary

The audio debug recording feature:
- ✅ **Default OFF**: No impact on production by default
- ✅ **Easy to Enable**: Single environment variable
- ✅ **Raw Format**: Preserves exact audio quality
- ✅ **Pre-Send Recording**: Captures data before Gemini Live processing
- ✅ **Automatic Cleanup**: File closed when session ends
- ⚠️ **Security Aware**: Contains user voice data
- ⚠️ **Disk Space**: Plan for cleanup strategy

Use this feature responsibly for debugging and development purposes.
