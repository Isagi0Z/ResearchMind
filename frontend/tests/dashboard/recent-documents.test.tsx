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

  it('renders empty/populated state', () => {
    const mockData = [
      {
        meta: { ruo_id: 'doc-1', pipeline_stages: ['extracted'] },
        header: {
          title: 'Test Document Title',
          authors: [{ full_name: 'Author Name' }],
          publication_date: '2023-01-01',
          venue: 'Test Venue',
        }
      }
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
