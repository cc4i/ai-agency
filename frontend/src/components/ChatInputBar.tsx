/**
 * Chat Input Bar - Text/Image input with voice toggle
 *
 * Features:
 * - Image upload (left)
 * - Text input (center)
 * - Mic toggle (right)
 * - CMD+ENTER to send
 */

'use client';

import { useState, useRef } from 'react';
import { Paperclip, Mic, MicOff, Camera, Monitor } from 'lucide-react';
import { useProjectStore } from '@/stores/useProjectStore';

interface ChatInputBarProps {
  onSendText: (text: string) => void;
  onSendImage: (file: File) => void;
  onToggleMic: () => void;
  onToggleCamera?: () => void;
  onToggleScreenShare?: () => void;
  isRecording: boolean;
  isCameraActive?: boolean;
  isScreenShareActive?: boolean;
}

export function ChatInputBar({
  onSendText,
  onSendImage,
  onToggleMic,
  onToggleCamera,
  onToggleScreenShare,
  isRecording,
  isCameraActive,
  isScreenShareActive,
}: ChatInputBarProps) {
  const { audioLevel } = useProjectStore();
  const [message, setMessage] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (message.trim()) {
      onSendText(message);
      setMessage('');
      inputRef.current?.focus();
      // Reset textarea height
      if (inputRef.current) {
        inputRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // CMD+ENTER (Mac) or CTRL+ENTER (Windows/Linux) to send
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
    // Plain Enter just adds a new line (default behavior)
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    // Auto-resize textarea up to max height
    e.target.style.height = 'auto';
    const newHeight = Math.min(e.target.scrollHeight, 200); // Max 200px
    e.target.style.height = `${newHeight}px`;
    // Enable scrolling if content exceeds max height
    e.target.style.overflowY = e.target.scrollHeight > 200 ? 'auto' : 'hidden';
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onSendImage(file);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-3">
      <div className="max-w-6xl mx-auto flex items-center gap-3">
        {/* Left Actions Group */}
        <div className="flex items-center gap-1">
          {/* Image Upload */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 rounded-lg hover:bg-zinc-800 transition-colors group"
            title="Upload image"
          >
            <Paperclip className="w-5 h-5 text-zinc-400 group-hover:text-zinc-300" />
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />
          </button>

          {/* Camera Toggle */}
          {onToggleCamera && (
            <button
              onClick={onToggleCamera}
              className={`p-2 rounded-lg transition-colors group ${isCameraActive ? 'bg-purple-500/20 text-purple-400' : 'hover:bg-zinc-800 text-zinc-400'}`}
              title={isCameraActive ? "Turn off camera" : "Turn on camera"}
            >
              <Camera className={`w-5 h-5 ${isCameraActive ? 'text-purple-400' : 'text-zinc-400 group-hover:text-zinc-300'}`} />
            </button>
          )}

          {/* Screen Share Toggle */}
          {onToggleScreenShare && (
            <button
              onClick={onToggleScreenShare}
              className={`p-2 rounded-lg transition-colors group ${isScreenShareActive ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-zinc-800 text-zinc-400'}`}
              title={isScreenShareActive ? "Stop screen share" : "Share screen"}
            >
              <Monitor className={`w-5 h-5 ${isScreenShareActive ? 'text-blue-400' : 'text-zinc-400 group-hover:text-zinc-300'}`} />
            </button>
          )}
        </div>

        {/* Text Input - Center (flex-1) */}
        <div className="flex-1 relative">
          <textarea
            ref={inputRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Type a message... (Enter for new line, Cmd+Enter to send)"
            rows={1}
            className="w-full bg-zinc-800 rounded-lg px-4 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-shadow resize-none overflow-hidden min-h-[42px] max-h-[200px]"
          />
          <div className="absolute right-3 -bottom-5 text-xs text-zinc-600">
            <span>{navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}+Enter to send</span>
          </div>
        </div>

        {/* Mic Button - Right (with audio level feedback) */}
        <button
          onClick={onToggleMic}
          className={`
            relative p-2 rounded-lg transition-all
            ${isRecording && audioLevel > 0.1
              ? 'text-white shadow-lg'
              : isRecording
                ? 'bg-blue-500 text-white'
                : 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-300'
            }
          `}
          style={
            isRecording && audioLevel > 0.1
              ? {
                backgroundColor: `rgb(59, 130, 246, ${0.5 + audioLevel * 0.5})`,
                boxShadow: `0 0 ${10 + audioLevel * 20}px rgba(59, 130, 246, ${audioLevel})`,
              }
              : undefined
          }
          title={isRecording ? 'Disable audio input' : 'Enable audio input'}
        >
          {isRecording ? (
            <Mic className="w-5 h-5" />
          ) : (
            <MicOff className="w-5 h-5" />
          )}
        </button>
      </div>
    </div>
  );
}
