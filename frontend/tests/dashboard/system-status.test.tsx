import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SystemStatusPanel } from '@/features/dashboard/system-status'
import { useSystemStatus } from '@/features/dashboard/use-dashboard-data'

vi.mock('@/features/dashboard/use-dashboard-data', () => ({
  useSystemStatus: vi.fn(),
}))

describe('SystemStatusPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state', () => {
    vi.mocked(useSystemStatus).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any)

    render(<SystemStatusPanel />)
    expect(screen.getByText('System Status')).toBeInTheDocument()
    expect(screen.getByText('Extraction Engine')).toBeInTheDocument()
  })

  it('renders populated state', () => {
    const mockData = {
      extraction: 'healthy',
      resolution: 'warning',
      graph: 'error',
      reasoning: 'healthy',
      synthesis: 'healthy'
    }
    
    vi.mocked(useSystemStatus).mockReturnValue({
      data: mockData,
      isLoading: false,
    } as any)

    render(<SystemStatusPanel />)
    
    expect(screen.getByText('System Status')).toBeInTheDocument()
    
    const healthyBadges = screen.getAllByText('healthy')
    expect(healthyBadges).toHaveLength(3) // extraction, reasoning, synthesis
    
    expect(screen.getByText('warning')).toBeInTheDocument() // resolution
    expect(screen.getByText('error')).toBeInTheDocument() // graph
  })
})
