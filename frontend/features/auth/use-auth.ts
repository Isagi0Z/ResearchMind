"use client"

import { useEffect, useCallback } from "react"
import { apiClient } from "@/lib/api-client"
import { useAuthStore } from "@/stores/auth-store"

interface UserProfile {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export function useAuth() {
  const { user, isLoading, setUser, setLoading } = useAuthStore()

  const fetchUser = useCallback(async () => {
    const tokens = apiClient.getTokens()
    if (!tokens.access) {
      setUser(null)
      return
    }
    try {
      const profile = await apiClient.get<UserProfile>("/auth/me")
      setUser(profile)
    } catch {
      setUser(null)
    }
  }, [setUser])

  useEffect(() => {
    if (isLoading) {
      fetchUser()
    }
  }, [isLoading, fetchUser])

  return {
    user,
    isLoading,
    isAdmin: user?.role === "admin",
    isAuthenticated: !!user,
  }
}
