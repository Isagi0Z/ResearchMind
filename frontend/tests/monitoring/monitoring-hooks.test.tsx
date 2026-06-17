import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useMonitoringData } from '@/features/monitoring/monitoring-hooks'
import * as monitoringServices from '@/services/monitoring'

vi.mock('@/services/monitoring', () => ({
  getMonitoringData: vi.fn(),
}))

vi.mock('@/features/monitoring/monitoring-store', () => ({
  useMonitoringStore: vi.fn(() => ({
    timeRange: '24h',
  })),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

const mockSnapshot = {
  id: 'snap-123',
  health: [],
  metrics: {
    queriesExecuted: 100,
    queriesToday: 10,
    querySuccessRate: 0.95,
    reviewsGenerated: 50,
    reviewsToday: 5,
    registeredUsers: 25,
    activeUsers: 20,
    refreshTokensActive: 10,
    documentsProcessed: 200,
  },
  charts: [],
  queue: [],
  recentErrors: [],
  corpus: { documentCount: 200, authorCount: 0, entityCount: 0, reviewCount: 50 },
}

describe('useMonitoringData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches monitoring data on mount', async () => {
    vi.mocked(monitoringServices.getMonitoringData).mockResolvedValue(mockSnapshot as any)

    const { result } = renderHook(() => useMonitoringData(), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockSnapshot)
    expect(monitoringServices.getMonitoringData).toHaveBeenCalledWith('24h')
  })

  it('handles fetch error', async () => {
    vi.mocked(monitoringServices.getMonitoringData).mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useMonitoringData(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeDefined()
  })
})
