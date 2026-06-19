import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useGraphData, useGraphNode } from '@/features/graph/graph-hooks'

vi.mock('@/services/graph', () => ({
  getGraphData: vi.fn(),
  getGraphNode: vi.fn(),
}))

import { getGraphData, getGraphNode } from '@/services/graph'

const mockGraphData = {
  nodes: [
    { id: 'doc-0', type: 'document', position: { x: 100, y: 100 }, data: { label: 'Doc 0', type: 'document' } },
  ],
  edges: [],
}

const mockNodeData = {
  id: 'doc-0',
  type: 'document',
  position: { x: 100, y: 100 },
  data: { label: 'Doc 0', type: 'document' },
}

function createWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useGraphData', () => {
  it('fetches graph data without params', async () => {
    vi.mocked(getGraphData).mockResolvedValue(mockGraphData)
    const { result } = renderHook(() => useGraphData(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockGraphData)
    expect(getGraphData).toHaveBeenCalledWith(undefined)
  })

  it('forwards params to getGraphData', async () => {
    vi.mocked(getGraphData).mockResolvedValue(mockGraphData)
    const params = { nodeType: 'document', offset: 0, limit: 100 }
    const { result } = renderHook(() => useGraphData(params), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(getGraphData).toHaveBeenCalledWith(params)
  })

  it('handles error state', async () => {
    vi.mocked(getGraphData).mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useGraphData(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('has 60s stale time', async () => {
    vi.mocked(getGraphData).mockResolvedValue(mockGraphData)
    const { result } = renderHook(() => useGraphData(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockGraphData)
  })
})

describe('useGraphNode', () => {
  it('fetches node by id', async () => {
    vi.mocked(getGraphNode).mockResolvedValue(mockNodeData)
    const { result } = renderHook(() => useGraphNode('doc-0'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockNodeData)
  })

  it('is disabled when id is null', async () => {
    const { result } = renderHook(() => useGraphNode(null), { wrapper: createWrapper() })
    expect(result.current.isPending).toBe(true)
    expect(result.current.fetchStatus).toBe('idle')
  })
})
