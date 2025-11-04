import { useProjectStore } from '@/stores/useProjectStore';
import { useEffect, useRef, useState } from 'react';

export function TranscriptDisplay() {
  const transcript = useProjectStore((state) => state.transcript);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    // Scroll to the bottom whenever the transcript changes
    if (scrollRef.current && !isCollapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript, isCollapsed]);

  return (
    <div
      className={`bg-black border-l border-zinc-800 flex flex-col h-full transition-all duration-300 ${
        isCollapsed ? 'w-12' : 'w-96'
      }`}
    >
      <div className="p-3 border-b border-zinc-800 flex-shrink-0 flex items-center justify-between">
        {!isCollapsed && (
          <h2 className="font-semibold text-sm">Conversation Transcript</h2>
        )}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="text-zinc-500 hover:text-zinc-300 transition-colors p-1 hover:bg-zinc-800 rounded"
          title={isCollapsed ? 'Expand transcript' : 'Collapse transcript'}
        >
          <svg
            className={`w-4 h-4 transition-transform ${isCollapsed ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
      {!isCollapsed && (
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
      )}
    </div>
  );
}
