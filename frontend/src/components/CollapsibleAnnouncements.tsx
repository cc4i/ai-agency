/**
 * Collapsible Announcements - Shows producer updates
 *
 * Features:
 * - Collapsible header with unread count
 * - Click to expand/collapse
 * - Shows recent announcements when expanded
 */

'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Megaphone } from 'lucide-react';
import { useProjectStore } from '@/stores/useProjectStore';

export function CollapsibleAnnouncements() {
  const { announcements } = useProjectStore();
  const [isExpanded, setIsExpanded] = useState(false);

  // Get recent announcements (last 5)
  const recentAnnouncements = announcements.slice(-5).reverse();
  const unreadCount = announcements.length;

  const getAnnouncementIcon = (type: string) => {
    switch (type) {
      case 'success':
        return '✅';
      case 'info':
        return 'ℹ️';
      case 'warning':
        return '⚠️';
      case 'error':
        return '❌';
      default:
        return '📢';
    }
  };

  const getTimeAgo = (timestamp: string) => {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    const diffHours = Math.floor(diffMins / 60);
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  };

  return (
    <div className="border-t border-zinc-800 bg-zinc-900">
      {/* Collapsible Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Megaphone className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-zinc-300">
            Producer Announcements
          </span>
          {unreadCount > 0 && (
            <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded-full border border-purple-500/30">
              {unreadCount}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-zinc-500" />
        ) : (
          <ChevronDown className="w-4 h-4 text-zinc-500" />
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-zinc-800 max-h-60 overflow-y-auto">
          {recentAnnouncements.length === 0 ? (
            <div className="p-4 text-center text-sm text-zinc-500">
              No announcements yet
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {recentAnnouncements.map((announcement, index) => (
                <div
                  key={index}
                  className="p-3 hover:bg-zinc-800/50 transition-colors"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-lg flex-shrink-0">
                      {getAnnouncementIcon(announcement.type)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-zinc-300">
                        {announcement.message}
                      </p>
                      <p className="text-xs text-zinc-600 mt-1">
                        {getTimeAgo(announcement.timestamp)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
