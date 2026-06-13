import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CorpusSummaryCards } from '@/features/dashboard/corpus-summary-cards'
import { useCorpusSummary } from '@/features/dashboard/use-dashboard-data'

vi.mock('@/features/dashboard/use-dashboard-data', () => ({
  useCorpusSummary: vi.fn(),
}))

describe('CorpusSummaryCards', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    vi.mocked(useCorpusSummary).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusSummaryCards />)
    
    // Total documents is one of the titles
    expect(screen.getByText('Total Documents')).toBeInTheDocument()
    // It should render 4 skeletons
    // We can just verify the titles are rendered correctly for all items
    expect(screen.getByText('Entity Clusters')).toBeInTheDocument()
    expect(screen.getByText('Graph Nodes')).toBeInTheDocument()
    expect(screen.getByText('Graph Edges')).toBeInTheDocument()
  })

  it('renders error state', () => {
    vi.mocked(useCorpusSummary).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    } as any)

    render(<CorpusSummaryCards />)
    
    expect(screen.getByText('Failed to load summary')).toBeInTheDocument()
    expect(screen.getByText('Could not load corpus statistics.')).toBeInTheDocument()
  })

  it('renders populated state with data', () => {
    vi.mocked(useCorpusSummary).mockReturnValue({
      data: {
        totalDocuments: 1000,
        entityClusters: 500,
        graphNodes: 2000,
        graphEdges: 1500,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusSummaryCards />)
    
    expect(screen.getByText('1,000')).toBeInTheDocument()
    expect(screen.getByText('500')).toBeInTheDocument()
    expect(screen.getByText('2,000')).toBeInTheDocument()
    expect(screen.getByText('1,500')).toBeInTheDocument()
  })
})
