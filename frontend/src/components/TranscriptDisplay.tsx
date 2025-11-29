import { useProjectStore } from '@/stores/useProjectStore';
import { useEffect, useRef } from 'react';

export function TranscriptDisplay() {
  const transcript = useProjectStore((state) => state.transcript);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Scroll to the bottom whenever the transcript changes
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  return (
    <div className="bg-zinc-950/50 flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 space-y-3" ref={scrollRef}>
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
        {transcript.length === 0 && (
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
