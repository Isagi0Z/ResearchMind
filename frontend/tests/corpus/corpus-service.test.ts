import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getDocuments } from '@/services/corpus'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api-client'

const mockPage = {
  data: [
    { ruo_id: 'doc-0000', title: 'Doc 0', authors: ['Smith, J.'], year: 2020, status: 'success', entity_count: 8, source: null },
    { ruo_id: 'doc-0001', title: 'Doc 1', authors: ['Doe, A.'], year: 2021, status: 'success', entity_count: 12, source: 'Journal' },
  ],
  total: 1000,
}

describe('getDocuments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls /api/v1/documents with page params', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockPage)
    const result = await getDocuments({ pageIndex: 0, pageSize: 10 })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/documents?pageIndex=0&pageSize=10')
    expect(result).toEqual(mockPage)
  })

  it('applies search query', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockPage)
    await getDocuments({ pageIndex: 0, pageSize: 10, searchQuery: 'biology' })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/documents?pageIndex=0&pageSize=10&searchQuery=biology')
  })

  it('applies sort params', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockPage)
    await getDocuments({ pageIndex: 0, pageSize: 10, sortBy: 'title', sortDirection: 'asc' })
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/documents?pageIndex=0&pageSize=10&sortBy=title&sortDirection=asc')
  })

  it('returns paginated response shape', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockPage)
    const data = await getDocuments({ pageIndex: 0, pageSize: 2 })
    expect(data).toHaveProperty('data')
    expect(data).toHaveProperty('total')
    expect(data.data).toHaveLength(2)
    expect(data.total).toBe(1000)
  })

  it('returns DocumentListItem shape', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockPage)
    const data = await getDocuments({ pageIndex: 0, pageSize: 1 })
    const item = data.data[0]
    expect(item).toHaveProperty('ruo_id')
    expect(item).toHaveProperty('title')
    expect(item).toHaveProperty('authors')
    expect(item).toHaveProperty('year')
    expect(item).toHaveProperty('status')
    expect(item).toHaveProperty('entity_count')
  })
})
