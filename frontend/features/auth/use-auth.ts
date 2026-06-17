"use client"

import { useState, useEffect, useCallback } from "react"
import { apiClient } from "@/lib/api-client"

interface UserProfile {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export function useAuth() {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchUser = useCallback(async () => {
    const tokens = apiClient.getTokens()
    if (!tokens.access) {
      setUser(null)
      setIsLoading(false)
      return
    }
    try {
      const profile = await apiClient.get<UserProfile>("/auth/me")
      setUser(profile)
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  return {
    user,
    isLoading,
    isAdmin: user?.role === "admin",
    isAuthenticated: !!user,
  }
}
