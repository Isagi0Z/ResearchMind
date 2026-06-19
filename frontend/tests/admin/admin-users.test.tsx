import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminUsers } from '@/features/admin/admin-users'
import * as adminServices from '@/services/admin'

vi.mock('@/services/admin', () => ({
  listUsers: vi.fn(),
  updateUserRole: vi.fn(),
  updateUserStatus: vi.fn(),
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

const mockUser = (id: string, username: string, email: string, role = 'user', isActive = true) => ({
  id,
  username,
  email,
  role,
  is_active: isActive,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
})

const mockPage = (users: any[]) => ({
  data: users,
  total: users.length,
})

describe('AdminUsers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    vi.mocked(adminServices.listUsers).mockReturnValue(new Promise(() => {}) as any)

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(screen.getByText('Admin Console')).toBeInTheDocument()
    expect(screen.getByText('User management and administration.')).toBeInTheDocument()
  })

  it('renders empty state when no data', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(mockPage([]))

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('No users found')).toBeInTheDocument()
  })

  it('renders empty state for search with no results', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(mockPage([]))

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('No users have been registered yet.')).toBeInTheDocument()
  })

  it('renders user table with data', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(
      mockPage([mockUser('u1', 'johndoe', 'john@example.com', 'user', true)])
    )

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('johndoe')).toBeInTheDocument()
    expect(screen.getByText('john@example.com')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('renders different role values', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(
      mockPage([
        mockUser('u1', 'user1', 'user1@test.com', 'user', true),
        mockUser('u2', 'admin1', 'admin1@test.com', 'admin', true),
      ])
    )

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('user1')).toBeInTheDocument()
    expect(screen.getByText('admin1')).toBeInTheDocument()
  })

  it('renders inactive user status', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(
      mockPage([mockUser('u1', 'inactiveuser', 'inactive@test.com', 'user', false)])
    )

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('Inactive')).toBeInTheDocument()
  })

  it('renders error state', async () => {
    vi.mocked(adminServices.listUsers).mockRejectedValue({ status: 500, message: 'Server error' })

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('Failed to load users')).toBeInTheDocument()
  })

  it('renders 401 error state', async () => {
    vi.mocked(adminServices.listUsers).mockRejectedValue({ status: 401, message: 'Unauthorized' })

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('Authentication Required')).toBeInTheDocument()
    expect(screen.getByText('Go to Login')).toBeInTheDocument()
  })

  it('renders 403 error state', async () => {
    vi.mocked(adminServices.listUsers).mockRejectedValue({ status: 403, message: 'Forbidden' })

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('Access Restricted')).toBeInTheDocument()
  })

  it('handles search input', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(mockPage([]))

    render(<AdminUsers />, { wrapper: createWrapper() })
    const input = await screen.findByPlaceholderText('Search users by username or email...') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'admin' } })

    expect(input.value).toBe('admin')
  })

  it('shows pagination when multiple pages', async () => {
    const users = Array.from({ length: 15 }).map((_, i) =>
      mockUser(`u${i}`, `user${i}`, `user${i}@test.com`)
    )
    vi.mocked(adminServices.listUsers).mockResolvedValue({ data: users.slice(0, 10), total: 15 })

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Next')).toBeInTheDocument()
    expect(screen.getByText('Previous')).toBeInTheDocument()
  })

  it('disables previous button on first page', async () => {
    const users = Array.from({ length: 15 }).map((_, i) =>
      mockUser(`u${i}`, `user${i}`, `user${i}@test.com`)
    )
    vi.mocked(adminServices.listUsers).mockResolvedValue({ data: users.slice(0, 10), total: 15 })

    render(<AdminUsers />, { wrapper: createWrapper() })
    const prevButton = await screen.findByText('Previous')
    expect(prevButton.closest('button')).toBeDisabled()
  })

  it('shows pagination info with total users', async () => {
    vi.mocked(adminServices.listUsers).mockResolvedValue(
      mockPage([mockUser('u1', 'user1', 'user1@test.com')])
    )

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('1 registered user')).toBeInTheDocument()
  })

  it('shows plural users count', async () => {
    const users = Array.from({ length: 3 }).map((_, i) =>
      mockUser(`u${i}`, `user${i}`, `user${i}@test.com`)
    )
    vi.mocked(adminServices.listUsers).mockResolvedValue({ data: users, total: 3 })

    render(<AdminUsers />, { wrapper: createWrapper() })
    expect(await screen.findByText('3 registered users')).toBeInTheDocument()
  })
})
