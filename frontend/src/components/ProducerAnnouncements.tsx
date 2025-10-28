/**
 * Producer Announcements - Chat-like display of producer messages.
 *
 * Features:
 * - Scrollable message history
 * - Type indicators (info, success, warning, error)
 * - Auto-scroll to latest message
 */

'use client';

import { useEffect, useRef } from 'react';
import { useProjectStore } from '@/stores/useProjectStore';
import { cn } from '@/lib/utils';
import { Info, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

export function ProducerAnnouncements() {
  const { announcements, isProducerSpeaking } = useProjectStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [announcements]);

  return (
    <div className="border-t border-zinc-800 bg-zinc-950 h-64">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            🎙️ Executive Producer
          </h3>
          {isProducerSpeaking && (
            <div className="flex items-center gap-2 text-xs text-blue-400 animate-pulse">
              <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
              Speaking...
            </div>
          )}
        </div>
      </div>

      <div ref={scrollRef} className="h-48 overflow-y-auto p-4 space-y-3">
        {announcements.length === 0 ? (
          <div className="text-sm text-zinc-500 text-center py-8">
            Waiting for producer to speak...
          </div>
        ) : (
          announcements.map((announcement, i) => (
            <Announcement key={i} announcement={announcement} />
          ))
        )}
      </div>
    </div>
  );
}

interface AnnouncementProps {
  announcement: {
    message: string;
    type: 'info' | 'success' | 'warning' | 'error';
    timestamp: string;
  };
}

function Announcement({ announcement }: AnnouncementProps) {
  const getIcon = () => {
    switch (announcement.type) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-400" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Info className="w-4 h-4 text-blue-400" />;
    }
  };

  const getBackgroundColor = () => {
    switch (announcement.type) {
      case 'success':
        return 'bg-green-500/10 border-green-500/30';
      case 'warning':
        return 'bg-yellow-500/10 border-yellow-500/30';
      case 'error':
        return 'bg-red-500/10 border-red-500/30';
      default:
        return 'bg-zinc-800 border-zinc-700';
    }
  };

  return (
    <div className={cn('rounded-lg border p-3', getBackgroundColor())}>
      <div className="flex items-start gap-2">
        {getIcon()}
        <div className="flex-1">
          <div className="text-sm text-zinc-200">{announcement.message}</div>
          <div className="text-xs text-zinc-500 mt-1">
            {new Date(announcement.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  );
}
