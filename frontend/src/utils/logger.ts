/**
 * Frontend Logger Utility
 *
 * Logs to both console and an in-memory buffer that can be downloaded.
 * Usage: logger.info('message'), logger.error('message'), etc.
 *
 * Download logs: logger.downloadLogs()
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: any;
}

class Logger {
  private logs: LogEntry[] = [];
  private maxLogs = 5000; // Keep last 5000 log entries

  private formatTimestamp(): string {
    return new Date().toISOString();
  }

  private addLog(level: LogLevel, message: string, data?: any) {
    const entry: LogEntry = {
      timestamp: this.formatTimestamp(),
      level,
      message,
      data,
    };

    // Add to buffer
    this.logs.push(entry);

    // Trim if too many logs
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }

    // Also log to console with appropriate method
    const consoleArgs = data ? [message, data] : [message];
    switch (level) {
      case 'debug':
        console.debug(...consoleArgs);
        break;
      case 'info':
        console.log(...consoleArgs);
        break;
      case 'warn':
        console.warn(...consoleArgs);
        break;
      case 'error':
        console.error(...consoleArgs);
        break;
    }
  }

  debug(message: string, data?: any) {
    this.addLog('debug', message, data);
  }

  info(message: string, data?: any) {
    this.addLog('info', message, data);
  }

  warn(message: string, data?: any) {
    this.addLog('warn', message, data);
  }

  error(message: string, data?: any) {
    this.addLog('error', message, data);
  }

  /**
   * Get all logs as a formatted string
   */
  getLogsAsString(): string {
    return this.logs
      .map((entry) => {
        const dataStr = entry.data ? ` | ${JSON.stringify(entry.data)}` : '';
        return `[${entry.timestamp}] [${entry.level.toUpperCase()}] ${entry.message}${dataStr}`;
      })
      .join('\n');
  }

  /**
   * Get all logs as JSON
   */
  getLogsAsJSON(): string {
    return JSON.stringify(this.logs, null, 2);
  }

  /**
   * Download logs as a text file
   */
  downloadLogs(format: 'text' | 'json' = 'text') {
    const content = format === 'json' ? this.getLogsAsJSON() : this.getLogsAsString();
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `frontend-logs-${Date.now()}.${format === 'json' ? 'json' : 'txt'}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log(`📥 Downloaded ${this.logs.length} log entries as ${format}`);
  }

  /**
   * Clear all logs
   */
  clear() {
    this.logs = [];
    console.clear();
    console.log('🗑️ Logs cleared');
  }

  /**
   * Get log count
   */
  getLogCount(): number {
    return this.logs.length;
  }

  /**
   * Get recent logs (last N entries)
   */
  getRecentLogs(count: number): LogEntry[] {
    return this.logs.slice(-count);
  }
}

// Export singleton instance
export const logger = new Logger();

// Make it available globally for debugging
if (typeof window !== 'undefined') {
  (window as any).logger = logger;
}
