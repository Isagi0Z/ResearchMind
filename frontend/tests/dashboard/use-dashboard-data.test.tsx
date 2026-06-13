import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { 
  useCorpusSummary, 
  useRecentDocuments, 
  useSystemStatus, 
  useRecentReviews 
} from '@/features/dashboard/use-dashboard-data'
import * as dashboardServices from '@/services/dashboard'

// Mock the dashboard services
vi.mock('@/services/dashboard', () => ({
  getCorpusSummary: vi.fn(),
  getRecentDocuments: vi.fn(),
  getSystemStatus: vi.fn(),
  getRecentReviews: vi.fn(),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('Dashboard Hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('useCorpusSummary', () => {
    it('fetches and returns corpus summary data', async () => {
      const mockData = { totalDocuments: 10, processing: 2, completed: 8 }
      vi.mocked(dashboardServices.getCorpusSummary).mockResolvedValue(mockData as any)

      const { result } = renderHook(() => useCorpusSummary(), {
        wrapper: createWrapper(),
      })

      expect(result.current.isLoading).toBe(true)
      
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockData)
      expect(dashboardServices.getCorpusSummary).toHaveBeenCalledTimes(1)
    })
  })

  describe('useRecentDocuments', () => {
    it('fetches and returns recent documents', async () => {
      const mockData = [{ id: '1', title: 'Doc 1' }]
      vi.mocked(dashboardServices.getRecentDocuments).mockResolvedValue(mockData as any)

      const { result } = renderHook(() => useRecentDocuments(), {
        wrapper: createWrapper(),
      })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockData)
      expect(dashboardServices.getRecentDocuments).toHaveBeenCalledTimes(1)
    })
  })

  describe('useSystemStatus', () => {
    it('fetches and returns system status', async () => {
      const mockData = { status: 'healthy', memory: '50%' }
      vi.mocked(dashboardServices.getSystemStatus).mockResolvedValue(mockData as any)

      const { result } = renderHook(() => useSystemStatus(), {
        wrapper: createWrapper(),
      })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockData)
      expect(dashboardServices.getSystemStatus).toHaveBeenCalledTimes(1)
    })
  })

  describe('useRecentReviews', () => {
    it('fetches and returns recent reviews', async () => {
      const mockData = [{ id: '1', rating: 5 }]
      vi.mocked(dashboardServices.getRecentReviews).mockResolvedValue(mockData as any)

      const { result } = renderHook(() => useRecentReviews(), {
        wrapper: createWrapper(),
      })

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockData)
      expect(dashboardServices.getRecentReviews).toHaveBeenCalledTimes(1)
    })
  })
})
