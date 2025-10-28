/**
 * Zustand store for project state management.
 */

import { create } from 'zustand'
import type { ProjectBrief } from '@/types/brief'

interface ProjectStore {
  brief: ProjectBrief | null
  assets: Record<string, any>
  currentAgent: string | null
  isListening: boolean
  isThinking: boolean

  setBrief: (brief: ProjectBrief) => void
  updateBrief: (updates: Partial<ProjectBrief>) => void
  addAsset: (agentId: string, asset: any) => void
  setCurrentAgent: (agentId: string | null) => void
  setListening: (isListening: boolean) => void
  setThinking: (isThinking: boolean) => void
}

export const useProjectStore = create<ProjectStore>((set) => ({
  brief: null,
  assets: {},
  currentAgent: null,
  isListening: false,
  isThinking: false,

  setBrief: (brief) => set({ brief }),
  updateBrief: (updates) =>
    set((state) => ({
      brief: state.brief ? { ...state.brief, ...updates } : null,
    })),
  addAsset: (agentId, asset) =>
    set((state) => ({
      assets: { ...state.assets, [agentId]: asset },
    })),
  setCurrentAgent: (agentId) => set({ currentAgent: agentId }),
  setListening: (isListening) => set({ isListening }),
  setThinking: (isThinking) => set({ isThinking }),
}))
