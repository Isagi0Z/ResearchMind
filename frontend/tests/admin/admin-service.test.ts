import { describe, it, expect, vi, beforeEach } from 'vitest'
import { listUsers, getUser, updateUserRole, updateUserStatus } from '@/services/admin'

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api-client'

const mockUser = {
  id: 'user-1',
  username: 'testuser',
  email: 'test@example.com',
  role: 'user',
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const mockPage = {
  data: [mockUser],
  total: 1,
}

describe('Admin Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listUsers', () => {
    it('calls /api/v1/admin/users with page params', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockPage)
      const result = await listUsers({ pageIndex: 0, pageSize: 10 })
      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/admin/users?pageIndex=0&pageSize=10')
      expect(result).toEqual(mockPage)
    })

    it('applies search query', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockPage)
      await listUsers({ pageIndex: 0, pageSize: 10, searchQuery: 'admin' })
      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/admin/users?pageIndex=0&pageSize=10&searchQuery=admin')
    })

    it('applies sort params', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockPage)
      await listUsers({ pageIndex: 0, pageSize: 10, sortBy: 'username', sortDirection: 'asc' })
      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/admin/users?pageIndex=0&pageSize=10&sortBy=username&sortDirection=asc')
    })

    it('returns paginated response shape', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockPage)
      const data = await listUsers({ pageIndex: 0, pageSize: 10 })
      expect(data).toHaveProperty('data')
      expect(data).toHaveProperty('total')
      expect(data.data).toHaveLength(1)
      expect(data.total).toBe(1)
    })
  })

  describe('getUser', () => {
    it('calls /api/v1/admin/users/:id', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockUser)
      const result = await getUser('user-1')
      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/admin/users/user-1')
      expect(result).toEqual(mockUser)
    })
  })

  describe('updateUserRole', () => {
    it('patches /api/v1/admin/users/:id/role', async () => {
      vi.mocked(apiClient.patch).mockResolvedValue({ ...mockUser, role: 'admin' })
      const result = await updateUserRole('user-1', 'admin')
      expect(apiClient.patch).toHaveBeenCalledWith('/api/v1/admin/users/user-1/role', { role: 'admin' })
      expect(result.role).toBe('admin')
    })
  })

  describe('updateUserStatus', () => {
    it('patches /api/v1/admin/users/:id/status', async () => {
      vi.mocked(apiClient.patch).mockResolvedValue({ ...mockUser, is_active: false })
      const result = await updateUserStatus('user-1', false)
      expect(apiClient.patch).toHaveBeenCalledWith('/api/v1/admin/users/user-1/status', { is_active: false })
      expect(result.is_active).toBe(false)
    })
  })
})
