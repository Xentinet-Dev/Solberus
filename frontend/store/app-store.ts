import { create } from "zustand";

interface Bot {
  bot_id: string;
  status: {
    running: boolean;
    platform?: string;
    positions?: Record<string, any>;
    trade_history?: any[];
    wallet_balance?: number;
    strategies?: string[];
    error?: string;
  };
}

interface AppState {
  wallet: string | null;
  bots: Bot[];
  activeTab: string;
  setWallet: (w: string | null) => void;
  setBots: (bots: Bot[]) => void;
  addBot: (bot: Bot) => void;
  updateBot: (botId: string, updates: Partial<Bot>) => void;
  removeBot: (botId: string) => void;
  setActiveTab: (tab: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  wallet: null,
  bots: [],
  activeTab: "control",
  setWallet: (w) => set({ wallet: w }),
  setBots: (bots) => set({ bots }),
  addBot: (bot) => set((state) => ({ bots: [...state.bots, bot] })),
  updateBot: (botId, updates) =>
    set((state) => ({
      bots: state.bots.map((b) =>
        b.bot_id === botId ? { ...b, ...updates } : b
      ),
    })),
  removeBot: (botId) =>
    set((state) => ({
      bots: state.bots.filter((b) => b.bot_id !== botId),
    })),
  setActiveTab: (tab) => set({ activeTab: tab }),
}));

