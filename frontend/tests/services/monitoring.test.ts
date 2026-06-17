import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getMonitoringData } from '@/services/monitoring'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api-client'

const mockSnapshot = {
  id: 'snap-123',
  health: [
    { moduleId: 'm1', name: 'M1 Extraction Engine', status: 'Healthy', uptime: '—', activeThreads: 0 },
    { moduleId: 'm2', name: 'M2 Entity Resolution', status: 'Healthy', uptime: '—', activeThreads: 0 },
    { moduleId: 'm3', name: 'M3 Corpus Graph', status: 'Healthy', uptime: '—', activeThreads: 0 },
    { moduleId: 'm4', name: 'M4 Reasoning Engine', status: 'Healthy', uptime: '—', activeThreads: 0 },
    { moduleId: 'm5', name: 'M5 Query System', status: 'Healthy', uptime: '—', activeThreads: 0 },
    { moduleId: 'm6', name: 'M6 Synthesis Engine', status: 'Healthy', uptime: '—', activeThreads: 0 },
  ],
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

describe('getMonitoringData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls the metrics endpoint with the given time range', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockSnapshot)

    const result = await getMonitoringData('24h')

    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/monitoring/metrics?timeRange=24h')
    expect(result).toEqual(mockSnapshot)
  })

  it('passes different time ranges correctly', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockSnapshot)

    await getMonitoringData('7d')
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/monitoring/metrics?timeRange=7d')

    await getMonitoringData('1h')
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/monitoring/metrics?timeRange=1h')
  })

  it('returns the expected snapshot shape', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockSnapshot)

    const data = await getMonitoringData('24h')
    expect(data).toHaveProperty('id')
    expect(data).toHaveProperty('health')
    expect(data).toHaveProperty('metrics')
    expect(data).toHaveProperty('charts')
    expect(data).toHaveProperty('queue')
    expect(data).toHaveProperty('recentErrors')
    expect(data).toHaveProperty('corpus')
    expect(data.health).toHaveLength(6)
    expect(data.metrics.queriesExecuted).toBe(100)
    expect(data.metrics.registeredUsers).toBe(25)
    expect(data.metrics.activeUsers).toBe(20)
  })
})
