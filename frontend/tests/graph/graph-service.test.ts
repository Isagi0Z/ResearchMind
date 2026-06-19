import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getGraphData, getGraphNode } from '@/services/graph'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api-client'

const mockResponse = {
  nodes: [
    { id: 'doc-0', type: 'document', position: { x: 100, y: 100 }, data: { label: 'Doc 0', type: 'document', title: 'Doc 0' } },
    { id: 'ent-0-0', type: 'entity', position: { x: 140, y: 130 }, data: { label: 'Entity 0', type: 'entity', confidence: 0.8, relatedDocuments: 1 } },
  ],
  edges: [
    { id: 'edge-ent-0-0-doc-0', source: 'ent-0-0', target: 'doc-0', type: 'customEdge', data: { type: 'CO_OCCURS', confidence: 0.8 } },
  ],
}

describe('getGraphData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls /api/v1/graph with no params', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)
    const result = await getGraphData()
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/graph')
    expect(result).toEqual(mockResponse)
  })

  it('applies nodeType filter', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)
    await getGraphData({ nodeType: 'document' })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/graph?nodeType=document')
  })

  it('applies search query', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)
    await getGraphData({ search: 'biology' })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/graph?search=biology')
  })

  it('applies offset and limit', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)
    await getGraphData({ offset: 10, limit: 50 })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/graph?offset=10&limit=50')
  })

  it('combines multiple params', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)
    await getGraphData({ nodeType: 'entity', search: 'neural', offset: 20, limit: 100 })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/graph?nodeType=entity&search=neural&offset=20&limit=100')
  })

  it('returns expected shape', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse)
    const data = await getGraphData()
    expect(data).toHaveProperty('nodes')
    expect(data).toHaveProperty('edges')
    expect(data.nodes).toHaveLength(2)
    expect(data.edges).toHaveLength(1)
  })
})

describe('getGraphNode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls /api/v1/graph/node/{id}', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse.nodes[0])
    const result = await getGraphNode('doc-0')
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/graph/node/doc-0')
    expect(result).toEqual(mockResponse.nodes[0])
  })
})
