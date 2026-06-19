"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  user: UserProfile | null;
  isLoading: boolean;
  setUser: (user: UserProfile | null) => void;
  setLoading: (loading: boolean) => void;
  isAdmin: () => boolean;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isLoading: true,
      setUser: (user) => set({ user, isLoading: false }),
      setLoading: (loading) => set({ isLoading: loading }),
      isAdmin: () => get().user?.role === "admin",
      isAuthenticated: () => !!get().user,
    }),
    {
      name: "auth-store",
      partialize: (state) => ({
        user: state.user,
      }),
    }
  )
);
