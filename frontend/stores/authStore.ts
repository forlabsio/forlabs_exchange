import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface UserInfo {
  id: number;
  wallet_address: string;
  role: string;
  is_subscribed: boolean;
}

interface AuthStore {
  token: string | null;
  user: UserInfo | null;
  walletAddress: string | null;
  connecting: boolean;
  setToken: (token: string | null) => void;
  connectWallet: () => Promise<void>;
  logout: () => void;
  hydrate: () => Promise<void>;
}

declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      isMetaMask?: boolean;
    };
  }
}

export const useAuthStore = create<AuthStore>((set) => ({
  token: null,
  user: null,
  walletAddress: null,
  connecting: false,

  setToken: (token) => set({ token }),

  hydrate: async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      set({ token: null, user: null });
      return;
    }
    set({ token });
    try {
      const user = await apiFetch("/api/auth/me");
      set({ user, walletAddress: user.wallet_address });
    } catch {
      localStorage.removeItem("token");
      set({ token: null, user: null });
    }
  },

  connectWallet: async () => {
    if (!window.ethereum) {
      throw new Error("MetaMask가 설치되어 있지 않습니다.");
    }

    set({ connecting: true });
    try {
      const accounts = (await window.ethereum.request({
        method: "eth_requestAccounts",
      })) as string[];
      const address = accounts[0];
      set({ walletAddress: address });

      const { nonce } = await apiFetch(`/api/auth/nonce?address=${address}`);

      const message = `ForLabsEX Login\nNonce: ${nonce}`;
      const signature = (await window.ethereum.request({
        method: "personal_sign",
        params: [message, address],
      })) as string;

      const data = await apiFetch("/api/auth/verify", {
        method: "POST",
        body: JSON.stringify({ address, signature }),
      });

      localStorage.setItem("token", data.access_token);
      set({ token: data.access_token });

      const user = await apiFetch("/api/auth/me");
      set({ user });
    } finally {
      set({ connecting: false });
    }
  },

  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null, walletAddress: null });
  },
}));
