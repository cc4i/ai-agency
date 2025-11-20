/**
 * Application Configuration
 * 
 * Centralizes API and WebSocket URLs.
 * Uses environment variables if available, otherwise falls back to defaults.
 */

// API Base URL (HTTP)
export const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// WebSocket Base URL (WS)
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
