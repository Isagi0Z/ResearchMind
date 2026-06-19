import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { GraphExplorer } from '@/features/graph/graph-explorer'

vi.mock('@/features/graph/graph-hooks', () => ({
  useGraphData: vi.fn(),
}))

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children: React.ReactNode }) => <div data-testid="reactflow">{children}</div>,
  MiniMap: () => <div data-testid="minimap" />,
  Controls: () => <div data-testid="controls" />,
  Background: () => <div data-testid="background" />,
  BackgroundVariant: { Dots: 'dots' },
  useNodesState: () => [[], vi.fn(), vi.fn()],
  useEdgesState: () => [[], vi.fn(), vi.fn()],
  Handle: () => null,
  Position: { Top: 'top', Bottom: 'bottom' },
}))

vi.mock('@/features/graph/custom-nodes', () => ({
  EntityNode: () => <div data-testid="entity-node" />,
  DocumentNode: () => <div data-testid="document-node" />,
  ThemeNode: () => <div data-testid="theme-node" />,
  ClusterNode: () => <div data-testid="cluster-node" />,
}))

vi.mock('@/features/graph/custom-edges', () => ({
  CustomEdge: () => <div data-testid="custom-edge" />,
}))

import { useGraphData } from '@/features/graph/graph-hooks'

const mockGraphData = {
  nodes: [
    { id: 'doc-0', type: 'document', position: { x: 100, y: 100 }, data: { label: 'Doc 0', type: 'document', title: 'Doc 0' } },
    { id: 'ent-0-0', type: 'entity', position: { x: 140, y: 130 }, data: { label: 'Entity 0', type: 'entity', confidence: 0.8, relatedDocuments: 1 } },
  ],
  edges: [
    { id: 'edge-ent-0-0-doc-0', source: 'ent-0-0', target: 'doc-0', type: 'customEdge', data: { type: 'CO_OCCURS', confidence: 0.8 } },
  ],
}

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('GraphExplorer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state', () => {
    vi.mocked(useGraphData).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as any)
    renderWithQuery(<GraphExplorer />)
    expect(screen.getByText('Loading...')).toBeTruthy()
  })

  it('shows error state with retry button', () => {
    vi.mocked(useGraphData).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Network error'),
      refetch: vi.fn(),
    } as any)
    renderWithQuery(<GraphExplorer />)
    expect(screen.getByText('Something went wrong')).toBeTruthy()
    expect(screen.getByText('Try Again')).toBeTruthy()
  })

  it('shows empty state when no nodes returned', () => {
    vi.mocked(useGraphData).mockReturnValue({
      data: { nodes: [], edges: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    renderWithQuery(<GraphExplorer />)
    expect(screen.getByText('No graph data available')).toBeTruthy()
  })

  it('renders canvas with graph data', () => {
    vi.mocked(useGraphData).mockReturnValue({
      data: mockGraphData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)
    renderWithQuery(<GraphExplorer />)
    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getByText('1')).toBeTruthy()
  })
})
