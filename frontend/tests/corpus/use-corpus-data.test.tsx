import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useDocuments } from '@/features/corpus/use-corpus-data'
import * as corpusServices from '@/services/corpus'

vi.mock('@/services/corpus', () => ({
  getDocuments: vi.fn(),
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

describe('useDocuments Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches and returns documents data based on params', async () => {
    const mockData = {
      documents: [{ id: '1', title: 'Doc 1' }],
      totalCount: 1,
      pageIndex: 0,
      pageSize: 50,
      pageCount: 1
    }
    vi.mocked(corpusServices.getDocuments).mockResolvedValue(mockData as any)

    const params = { pageIndex: 0, pageSize: 50 }
    const { result } = renderHook(() => useDocuments(params), {
      wrapper: createWrapper(),
    })

    expect(result.current.isLoading).toBe(true)
    
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockData)
    expect(corpusServices.getDocuments).toHaveBeenCalledWith(params)
  })

  it('handles query errors', async () => {
    const error = new Error('Failed to fetch')
    vi.mocked(corpusServices.getDocuments).mockRejectedValue(error)

    const { result } = renderHook(() => useDocuments({ pageIndex: 0, pageSize: 50 }), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toEqual(error)
  })
})
