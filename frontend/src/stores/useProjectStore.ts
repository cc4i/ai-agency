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

interface ProjectState {
  // Project data
  brief: ProjectBrief | null;
  assets: Record<string, Asset[]>;
  agentStatuses: Record<string, AgentStatus>;
  announcements: ProducerAnnouncement[];
  transcript: ConversationMessage[];
  changedFields: string[];

  // Audio state
  isConnected: boolean;
  isMicrophoneActive: boolean;
  isProducerSpeaking: boolean;
  audioLevel: number;

  // Actions
  setBrief: (brief: ProjectBrief) => void;
  updateBrief: (updates: Partial<ProjectBrief>, changedFields?: string[]) => void;
  addAsset: (agentId: string, asset: Asset) => void;
  updateAgentStatus: (agentId: string, status: AgentStatus) => void;
  addAnnouncement: (announcement: ProducerAnnouncement) => void;
  addTranscriptMessage: (message: ConversationMessage) => void;
  clearChangedFields: () => void;

  setConnected: (connected: boolean) => void;
  setMicrophoneActive: (active: boolean) => void;
  setProducerSpeaking: (speaking: boolean) => void;
  setAudioLevel: (level: number) => void;

  reset: () => void;
}

const initialState = {
  brief: null,
  assets: {},
  agentStatuses: {},
  announcements: [],
  transcript: [],
  changedFields: [],
  isConnected: false,
  isMicrophoneActive: false,
  isProducerSpeaking: false,
  audioLevel: 0,
};

export const useProjectStore = create<ProjectState>((set) => ({
  ...initialState,

  setBrief: (brief) => set({ brief }),

  updateBrief: (updates, changedFields = []) =>
    set((state) => ({
      brief: state.brief ? { ...state.brief, ...updates } : null,
      changedFields,
    })),

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
    })),

  clearChangedFields: () => set({ changedFields: [] }),

  setConnected: (connected) => set({ isConnected: connected }),
  setMicrophoneActive: (active) => set({ isMicrophoneActive: active }),
  setProducerSpeaking: (speaking) => set({ isProducerSpeaking: speaking }),
  setAudioLevel: (level) => set({ audioLevel: level }),

  reset: () => set(initialState),
}));
