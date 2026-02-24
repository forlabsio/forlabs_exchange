import { create } from "zustand";
import { apiFetch } from "@/lib/api";

interface UserInfo {
  id: number;
  email: string;
  role: string;
  is_subscribed: boolean;
}

interface AuthStore {
  token: string | null;
  user: UserInfo | null;
  setToken: (token: string | null) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  token: null,
  user: null,
  setToken: (token) => set({ token }),
  hydrate: async () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) { set({ token: null, user: null }); return; }
    set({ token });
    try {
      const user = await apiFetch("/api/auth/me");
      set({ user });
    } catch {
      set({ user: null });
    }
  },
  login: async (email, password) => {
    const data = await apiFetch("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem("token", data.access_token);
    set({ token: data.access_token });
    const user = await apiFetch("/api/auth/me");
    set({ user });
  },
  register: async (email, password) => {
    await apiFetch("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  logout: () => {
    localStorage.removeItem("token");
    set({ token: null, user: null });
  },
}));
