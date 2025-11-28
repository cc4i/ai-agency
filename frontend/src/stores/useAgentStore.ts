/**
 * Zustand store for agent management.
 *
 * Manages:
 * - List of all agents (local and remote)
 * - Remote agent registration
 * - Agent health status
 * - Circuit breaker states
 */

import { create } from 'zustand';

export interface AgentSkill {
  id: string;
  name: string;
  description: string;
  inputModes: string[];
  outputModes: string[];
}

export interface AgentInfo {
  agent_id: string;
  name: string;
  description: string;
  provider: 'local' | 'remote';
  status: 'ready' | 'working' | 'error' | 'offline';
  skills: AgentSkill[];
  is_active: boolean;
  overrides?: string;
  overridden_by?: string;
}

export interface CircuitBreakerStatus {
  agent_id: string;
  state: 'closed' | 'open' | 'half_open';
  failures: number;
  failure_threshold: number;
  recovery_in_seconds?: number;
}

interface AgentState {
  agents: AgentInfo[];
  isLoading: boolean;
  error: string | null;
  selectedAgent: string | null;
  circuitBreakerStates: Record<string, CircuitBreakerStatus>;

  // Actions
  setAgents: (agents: AgentInfo[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSelectedAgent: (agentId: string | null) => void;
  updateCircuitBreaker: (agentId: string, status: CircuitBreakerStatus) => void;
  addAgent: (agent: AgentInfo) => void;
  removeAgent: (agentId: string) => void;
  updateAgentStatus: (agentId: string, status: AgentInfo['status']) => void;

  // Async actions (API calls)
  fetchAgents: () => Promise<void>;
  registerRemoteAgent: (
    agentCardUrl: string,
    apiKeyRef: string,
    overrideLocal?: string
  ) => Promise<{ success: boolean; error?: string; agent?: AgentInfo }>;
  unregisterAgent: (agentId: string) => Promise<boolean>;
  checkAgentHealth: (agentId: string) => Promise<boolean>;
  resetCircuitBreaker: (agentId: string) => Promise<boolean>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  isLoading: false,
  error: null,
  selectedAgent: null,
  circuitBreakerStates: {},

  setAgents: (agents) => set({ agents }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setSelectedAgent: (agentId) => set({ selectedAgent: agentId }),

  updateCircuitBreaker: (agentId, status) =>
    set((state) => ({
      circuitBreakerStates: {
        ...state.circuitBreakerStates,
        [agentId]: status,
      },
    })),

  addAgent: (agent) =>
    set((state) => ({
      agents: [...state.agents, agent],
    })),

  removeAgent: (agentId) =>
    set((state) => ({
      agents: state.agents.filter((a) => a.agent_id !== agentId),
    })),

  updateAgentStatus: (agentId, status) =>
    set((state) => ({
      agents: state.agents.map((a) =>
        a.agent_id === agentId ? { ...a, status } : a
      ),
    })),

  fetchAgents: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`${API_BASE}/api/agents`);
      if (!response.ok) {
        throw new Error(`Failed to fetch agents: ${response.statusText}`);
      }
      const data = await response.json();
      set({ agents: data.agents, isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  registerRemoteAgent: async (agentCardUrl, apiKey, overrideLocal) => {
    set({ isLoading: true, error: null });
    try {
      const response = await fetch(`${API_BASE}/api/agents/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_card_url: agentCardUrl,
          api_key: apiKey,
          override_local: overrideLocal,
          fallback_to_local: true,
        }),
      });

      const data = await response.json();
      set({ isLoading: false });

      if (data.success && data.agent) {
        // Add to local state
        get().addAgent(data.agent);
        return { success: true, agent: data.agent };
      } else {
        set({ error: data.error });
        return { success: false, error: data.error };
      }
    } catch (error) {
      const errorMsg = (error as Error).message;
      set({ error: errorMsg, isLoading: false });
      return { success: false, error: errorMsg };
    }
  },

  unregisterAgent: async (agentId) => {
    try {
      const response = await fetch(`${API_BASE}/api/agents/${agentId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        get().removeAgent(agentId);
        // Refetch to get updated overrides
        get().fetchAgents();
        return true;
      }
      return false;
    } catch (error) {
      set({ error: (error as Error).message });
      return false;
    }
  },

  checkAgentHealth: async (agentId) => {
    try {
      const response = await fetch(`${API_BASE}/api/agents/${agentId}/health`);
      if (response.ok) {
        const data = await response.json();
        get().updateAgentStatus(agentId, data.healthy ? 'ready' : 'error');
        return data.healthy;
      }
      return false;
    } catch (error) {
      get().updateAgentStatus(agentId, 'offline');
      return false;
    }
  },

  resetCircuitBreaker: async (agentId) => {
    try {
      const response = await fetch(
        `${API_BASE}/api/agents/${agentId}/circuit-breaker/reset`,
        { method: 'POST' }
      );
      if (response.ok) {
        get().updateCircuitBreaker(agentId, {
          agent_id: agentId,
          state: 'closed',
          failures: 0,
          failure_threshold: 5,
        });
        return true;
      }
      return false;
    } catch (error) {
      return false;
    }
  },
}));
