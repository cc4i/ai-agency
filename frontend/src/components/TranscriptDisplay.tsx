import { useProjectStore } from '@/stores/useProjectStore';
import { useEffect, useRef } from 'react';

export function TranscriptDisplay() {
  const transcript = useProjectStore((state) => state.transcript);
  const liveTranscript = useProjectStore((state) => state.liveTranscript);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to the bottom whenever the transcript or live transcript changes
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript, liveTranscript]);

  return (
    <div className="bg-zinc-950/50 flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-3" ref={scrollRef}>
        {/* Committed transcript messages */}
        {transcript.map((message, index) => (
          <div
            key={index}
            className={`flex flex-col ${
              message.role === 'assistant' ? 'items-start' : 'items-end'
            }`}
          >
            {/* Role label */}
            <div className="text-[10px] font-medium text-zinc-500 uppercase mb-1 px-1">
              {message.role === 'assistant' ? 'AI Producer' : 'You'}
            </div>
            {/* Message bubble */}
            <div
              className={`max-w-[90%] px-3 py-2 rounded-lg text-sm ${
                message.role === 'assistant'
                  ? 'bg-purple-900/30 text-zinc-200 border border-purple-800/30'
                  : 'bg-zinc-800 text-zinc-200 border border-zinc-700/50'
              }`}
            >
              <p className="text-xs leading-relaxed">{message.text}</p>
            </div>
            {/* Timestamp */}
            <div className="text-[10px] text-zinc-600 mt-1 px-1">
              {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        ))}

        {/* Live transcript bubble (real-time typing) */}
        {liveTranscript && liveTranscript.text && (
          <div
            className={`flex flex-col ${
              liveTranscript.role === 'assistant' ? 'items-start' : 'items-end'
            }`}
          >
            {/* Role label with speaking indicator */}
            <div className="text-[10px] font-medium text-zinc-500 uppercase mb-1 px-1 flex items-center gap-1.5">
              {liveTranscript.role === 'assistant' ? 'AI Producer' : 'You'}
              <span className="inline-flex gap-0.5">
                <span className="w-1 h-1 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
                <span className="w-1 h-1 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
                <span className="w-1 h-1 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
              </span>
            </div>
            {/* Live message bubble with typing cursor */}
            <div
              className={`max-w-[90%] px-3 py-2 rounded-lg text-sm ${
                liveTranscript.role === 'assistant'
                  ? 'bg-purple-900/40 text-zinc-200 border border-purple-500/50 shadow-sm shadow-purple-500/20'
                  : 'bg-zinc-700 text-zinc-200 border border-zinc-500/50 shadow-sm shadow-zinc-500/20'
              }`}
            >
              <p className="text-xs leading-relaxed">
                {liveTranscript.text}
                <span className="inline-block w-0.5 h-3 bg-purple-400 ml-0.5 animate-pulse" />
              </p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {transcript.length === 0 && !liveTranscript && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="text-zinc-600 text-xs">
              Transcript will appear here...
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
