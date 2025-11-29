import { create } from 'zustand';

export interface Message {
    role: 'user' | 'assistant';
    text: string;
    timestamp: string;
}

interface ConversationStore {
    messages: Message[];
    currentMessage: string;  // Streaming text
    addMessage: (message: Message) => void;
    updateCurrentMessage: (text: string) => void;
    commitCurrentMessage: () => void;
    clearConversation: () => void;
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
    messages: [],
    currentMessage: '',

    addMessage: (message) => set((state) => ({
        messages: [...state.messages, message]
    })),

    updateCurrentMessage: (text) => set({ currentMessage: text }),

    commitCurrentMessage: () => set((state) => ({
        messages: [
            ...state.messages,
            {
                role: 'assistant',
                text: state.currentMessage,
                timestamp: new Date().toISOString()
            }
        ],
        currentMessage: ''
    })),

    clearConversation: () => set({ messages: [], currentMessage: '' })
}));
