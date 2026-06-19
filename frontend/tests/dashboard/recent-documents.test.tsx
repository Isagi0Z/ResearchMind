import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RecentDocuments } from '@/features/dashboard/recent-documents'
import { useRecentDocuments } from '@/features/dashboard/use-dashboard-data'

vi.mock('@/features/dashboard/use-dashboard-data', () => ({
  useRecentDocuments: vi.fn(),
}))

describe('RecentDocuments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    vi.mocked(useRecentDocuments).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)

    render(<RecentDocuments />)
    expect(screen.getByText('Recent Documents')).toBeInTheDocument()
  })

  it('renders populated state with new flat shape', () => {
    const mockData = [
      {
        ruo_id: 'doc-1',
        title: 'Test Document Title',
        authors: ['Author Name'],
        year: 2023,
        status: 'extracted',
        entity_count: 5,
        source: 'Test Venue',
      },
    ]

    vi.mocked(useRecentDocuments).mockReturnValue({
      data: mockData,
      isLoading: false,
    } as any)

    render(<RecentDocuments />)

    expect(screen.getByText('Recent Documents')).toBeInTheDocument()
    expect(screen.getByText('Test Document Title')).toBeInTheDocument()
    expect(screen.getByText('Author Name (2023)')).toBeInTheDocument()
    expect(screen.getByText('Test Venue')).toBeInTheDocument()
    expect(screen.getByText('extracted')).toBeInTheDocument()
  })
})
