/**
 * Zustand store for project state management.
 *
 * Manages:
 * - Project Brief (real-time updates from backend)
 * - Assets (strategy, art, video, audio, web)
 * - Agent status (idle, thinking, complete)
 * - Audio streaming state
 * - Producer announcements
 */

import { create } from 'zustand';
import { ConversationMessage } from '@/types/brief';

export interface ProjectBrief {
  project_id: string;
  session_id: string;
  product_name: string;
  product_category: string;
  theme: string;
  key_features: string[];
  brand_tone: string;
  target_market: string;
  initial_sketch_url?: string;
  reference_images?: Array<{
    asset_id: string;
    url: string;
    description: string;
    generation_params?: any;
  }>;

  // Strategy outputs (NEW - persisted to Redis)
  slogans?: string[];
  personas?: Array<{
    name: string;
    age_range: string;
    description: string;
    pain_points: string[];
    motivations: string[];
    product_usage_context: string;
  }>;
  selected_slogan?: string;

  // Art outputs
  hero_images?: Array<{
    asset_id: string;
    url: string;
    description: string;
    generation_params: any;
    parent_asset_id?: string;
    refinement_iteration?: number;
    user_feedback_applied?: string;
    generation_number?: number;
    variation_number?: number;
  }>;
  selected_image?: {
    asset_id: string;
    url: string;
    generation_params: any;
    description: string;
  };

  // Generation tracking (NEW - production level)
  current_generation?: number;
  generation_history?: Array<any>;
  image_refinement_history?: Record<string, any>;

  created_at: string;
  updated_at: string;
}

export interface Asset {
  type: string;
  data: any;
  created_at: string;
}

export interface AgentStatus {
  agent_id: string;
  status: 'idle' | 'thinking' | 'complete' | 'error';
  current_task?: string;
}

export interface ProducerAnnouncement {
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  timestamp: string;
}

// Concept preview for Smart Mirror iteration flow
export interface ConceptPreview {
  id: string;
  url: string;
  description: string;
  iteration: number;
}

// Captured reference image for concept generation
export interface CapturedReference {
  id: string;
  url: string;
  description: string;
  timestamp: number;
}

interface ProjectState {
  // Project data
  brief: ProjectBrief | null;
  assets: Record<string, Asset[]>;
  agentStatuses: Record<string, AgentStatus>;
  announcements: ProducerAnnouncement[];
  transcript: ConversationMessage[];
  changedFields: string[];

  // Live transcription (real-time display before turn completes)
  liveTranscript: { role: 'user' | 'assistant'; text: string } | null;

  // Concept preview state (for Smart Mirror iteration)
  previewConcepts: ConceptPreview[];
  conceptIteration: number;
  capturedReference: CapturedReference | null;

  // Audio state
  isConnected: boolean;
  isMicrophoneActive: boolean;
  isProducerSpeaking: boolean;
  audioLevel: number;

  // Frequency data for waveform visualization (16 bars each, 0-1 normalized)
  userFrequencyData: number[];
  aiFrequencyData: number[];

  // Actions
  setBrief: (brief: ProjectBrief) => void;
  updateBrief: (updates: Partial<ProjectBrief>, changedFields?: string[]) => void;
  addAsset: (agentId: string, asset: Asset) => void;
  updateAgentStatus: (agentId: string, status: AgentStatus) => void;
  addAnnouncement: (announcement: ProducerAnnouncement) => void;
  addTranscriptMessage: (message: ConversationMessage) => void;
  setLiveTranscript: (live: { role: 'user' | 'assistant'; text: string } | null) => void;
  appendLiveTranscript: (role: 'user' | 'assistant', text: string) => void;
  clearChangedFields: () => void;

  // Concept preview actions
  setPreviewConcepts: (concepts: ConceptPreview[], iteration: number) => void;
  clearPreviewConcepts: () => void;
  setCapturedReference: (ref: CapturedReference | null) => void;
  clearSmartMirrorState: () => void; // Clear all when window closes

  setConnected: (connected: boolean) => void;
  setMicrophoneActive: (active: boolean) => void;
  setProducerSpeaking: (speaking: boolean) => void;
  setAudioLevel: (level: number) => void;
  setUserFrequencyData: (data: number[]) => void;
  setAiFrequencyData: (data: number[]) => void;

  reset: () => void;
}

// Default frequency data (16 bars, all zero)
const DEFAULT_FREQUENCY_DATA = Array(16).fill(0);

const initialState = {
  brief: null,
  assets: {},
  agentStatuses: {},
  announcements: [],
  transcript: [],
  changedFields: [],
  liveTranscript: null as { role: 'user' | 'assistant'; text: string } | null,
  previewConcepts: [] as ConceptPreview[],
  conceptIteration: 0,
  capturedReference: null as CapturedReference | null,
  isConnected: false,
  isMicrophoneActive: false,
  isProducerSpeaking: false,
  audioLevel: 0,
  userFrequencyData: DEFAULT_FREQUENCY_DATA,
  aiFrequencyData: DEFAULT_FREQUENCY_DATA,
};

export const useProjectStore = create<ProjectState>((set) => ({
  ...initialState,

  setBrief: (brief) => set({ brief }),

  updateBrief: (updates, changedFields = []) => {
    console.log('[Store] updateBrief called with changedFields:', changedFields);
    if (updates.reference_images) {
      console.log('[Store] updateBrief has reference_images:', updates.reference_images.length);
    }
    return set((state) => {
      const newBrief = state.brief ? { ...state.brief, ...updates } : null;
      console.log('[Store] After update, brief.reference_images:', newBrief?.reference_images?.length || 0);
      return {
        brief: newBrief,
        changedFields,
      };
    });
  },

  addAsset: (agentId, asset) =>
    set((state) => ({
      assets: {
        ...state.assets,
        [agentId]: [...(state.assets[agentId] || []), asset],
      },
    })),

  updateAgentStatus: (agentId, status) =>
    set((state) => ({
      agentStatuses: {
        ...state.agentStatuses,
        [agentId]: status,
      },
    })),

  addAnnouncement: (announcement) =>
    set((state) => ({
      announcements: [...state.announcements, announcement],
    })),

  addTranscriptMessage: (message) =>
    set((state) => ({
      transcript: [...state.transcript, message],
      liveTranscript: null, // Clear live transcript when committing
    })),

  setLiveTranscript: (live) => set({ liveTranscript: live }),

  appendLiveTranscript: (role, text) =>
    set((state) => {
      if (state.liveTranscript && state.liveTranscript.role === role) {
        // Same role - append text
        return { liveTranscript: { role, text: state.liveTranscript.text + text } };
      } else {
        // Different role - start fresh
        return { liveTranscript: { role, text } };
      }
    }),

  clearChangedFields: () => set({ changedFields: [] }),

  // Concept preview actions
  setPreviewConcepts: (concepts, iteration) => set({
    previewConcepts: concepts,
    conceptIteration: iteration
  }),
  clearPreviewConcepts: () => set({
    previewConcepts: [],
    conceptIteration: 0
  }),
  setCapturedReference: (ref) => set({ capturedReference: ref }),
  clearSmartMirrorState: () => set({
    previewConcepts: [],
    conceptIteration: 0,
    capturedReference: null
  }),

  setConnected: (connected) => set({ isConnected: connected }),
  setMicrophoneActive: (active) => set({ isMicrophoneActive: active }),
  setProducerSpeaking: (speaking) => set({ isProducerSpeaking: speaking }),
  setAudioLevel: (level) => set({ audioLevel: level }),
  setUserFrequencyData: (data) => set({ userFrequencyData: data }),
  setAiFrequencyData: (data) => set({ aiFrequencyData: data }),

  reset: () => set(initialState),
}));
