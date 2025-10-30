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
    <div className="w-96 bg-black border-l border-zinc-800 flex flex-col h-[calc(100vh-100px)]">
      <div className="p-4 border-b border-zinc-800">
        <h2 className="font-bold text-lg">Conversation Transcript</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
        {transcript.map((message, index) => (
          <div
            key={index}
            className={`flex flex-col ${
              message.role === 'assistant' ? 'items-start' : 'items-end'
            }`}>
            <div
              className={`max-w-xs lg:max-w-sm p-3 rounded-lg ${
                message.role === 'assistant'
                  ? 'bg-blue-900/50 text-white'
                  : 'bg-gray-700 text-white'
              }`}>
              <p className="text-sm">{message.text}</p>
              <div className="text-xs text-gray-400 mt-1 text-right">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
            <div className="text-xs font-semibold text-gray-500 uppercase mt-1">
              {message.role}
            </div>
          </div>
        ))}
        {transcript.length === 0 && (
          <div className="text-center text-zinc-500 pt-10">
            Transcript will appear here...
          </div>
        )}
      </div>
    </div>
  );
}
