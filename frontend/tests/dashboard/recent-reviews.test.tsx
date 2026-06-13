import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RecentReviews } from '@/features/dashboard/recent-reviews'
import { useRecentReviews } from '@/features/dashboard/use-dashboard-data'

vi.mock('@/features/dashboard/use-dashboard-data', () => ({
  useRecentReviews: vi.fn(),
}))

describe('RecentReviews', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    vi.mocked(useRecentReviews).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)

    render(<RecentReviews />)
    expect(screen.getByText('Recent Reviews')).toBeInTheDocument()
  })

  it('renders populated state', () => {
    const mockData = [
      {
        id: 'rev-1',
        title: 'Review of AI progress',
        type: 'systematic_review',
        confidence: 0.95,
        createdAt: '2023-01-01T00:00:00.000Z',
      }
    ]
    
    vi.mocked(useRecentReviews).mockReturnValue({
      data: mockData,
      isLoading: false,
    } as any)

    render(<RecentReviews />)
    
    expect(screen.getByText('Recent Reviews')).toBeInTheDocument()
    expect(screen.getByText('Review of AI progress')).toBeInTheDocument()
    expect(screen.getByText('systematic review')).toBeInTheDocument()
    expect(screen.getByText('95% conf')).toBeInTheDocument()
  })
})
