import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CorpusManager } from '@/features/corpus/corpus-manager'
import { useDocuments } from '@/features/corpus/use-corpus-data'
import { useCorpusStore } from '@/features/corpus/corpus-store'

vi.mock('@/features/corpus/use-corpus-data', () => ({
  useDocuments: vi.fn(),
}))

vi.mock('@/services/jobs', () => ({
  getJob: vi.fn(),
  listJobs: vi.fn(),
}))

vi.mock('@/features/jobs/use-jobs', () => ({
  useJobStatus: vi.fn(() => ({ data: undefined, isLoading: false })),
  useJobEvents: vi.fn(() => ({ connectionStatus: 'idle', close: vi.fn() })),
  useJobList: vi.fn(() => ({ data: { data: [] }, isLoading: false, isError: false })),
}))

let mockVirtualItems: any[] = []
let mockVirtualizerCount = 0

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: vi.fn().mockImplementation((options) => {
    mockVirtualizerCount = options.count
    return {
      getVirtualItems: () => mockVirtualItems,
      getTotalSize: () => options.count * 50,
      measureElement: vi.fn(),
    }
  })
}))

const mockDoc = (id: string, title: string, author = 'Author 1', year = 2023, status = 'success', entityCount = 5) => ({
  ruo_id: id,
  title,
  authors: [author],
  year,
  status,
  entity_count: entityCount,
  source: null,
})

describe('CorpusManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockVirtualItems = []
    mockVirtualizerCount = 0
    useCorpusStore.setState({
      searchQuery: '',
      filters: { yearRange: [2000, 2026], authors: [], source: [], status: [] },
      sort: { column: 'year', direction: 'desc' },
      pagination: { pageIndex: 0, pageSize: 1000 },
      selectedRows: {},
    })
  })

  it('renders correctly', () => {
    vi.mocked(useDocuments).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    expect(screen.getByText('Corpus Manager')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Search documents by title or author...')).toBeInTheDocument()
  })

  it('renders empty state when no data', () => {
    vi.mocked(useDocuments).mockReturnValue({
      data: { data: [], total: 0 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    expect(screen.getByText('No documents found')).toBeInTheDocument()
  })

  it('renders error state', () => {
    vi.mocked(useDocuments).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    expect(screen.getByText('Failed to load documents')).toBeInTheDocument()
  })

  it('renders populated table via virtualization', () => {
    mockVirtualItems = [{ index: 0, start: 0, end: 50, size: 50 }]
    vi.mocked(useDocuments).mockReturnValue({
      data: {
        data: [mockDoc('doc-1', 'Test Document 1', 'Author 1', 2023, 'success', 5)],
        total: 1,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    expect(screen.getByText('Test Document 1')).toBeInTheDocument()
    expect(screen.getByText('Author 1')).toBeInTheDocument()
    expect(screen.getByText('2023')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
  })

  it('handles search input', async () => {
    vi.mocked(useDocuments).mockReturnValue({
      data: { data: [], total: 0 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    const input = screen.getByPlaceholderText('Search documents by title or author...')
    await userEvent.type(input, 'test query')

    expect(input).toHaveValue('test query')
  })

  it('handles row selection toggle', async () => {
    mockVirtualItems = [{ index: 0, start: 0, end: 50, size: 50 }]
    vi.mocked(useDocuments).mockReturnValue({
      data: {
        data: [mockDoc('doc-1', 'Test Document 1')],
        total: 1,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    const checkboxes = screen.getAllByRole('checkbox')
    const rowCheckbox = checkboxes[1]

    await userEvent.click(rowCheckbox)
    expect(useCorpusStore.getState().selectedRows['doc-1']).toBe(true)
  })

  describe('Virtualization behavior', () => {
    it('sets up the virtualizer with correct count', () => {
      const largeData = Array.from({ length: 500 }).map((_, i) => mockDoc(`doc-${i}`, `Test Document ${i}`))

      vi.mocked(useDocuments).mockReturnValue({
        data: { data: largeData, total: 500 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any)

      render(<CorpusManager />)
      expect(mockVirtualizerCount).toBe(500)
    })

    it('renders only virtual items returned by virtualizer', () => {
      const largeData = Array.from({ length: 500 }).map((_, i) => mockDoc(`doc-${i}`, `Test Document ${i}`))

      vi.mocked(useDocuments).mockReturnValue({
        data: { data: largeData, total: 500 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any)

      mockVirtualItems = [
        { index: 100, start: 5000, end: 5050, size: 50 },
        { index: 101, start: 5050, end: 5100, size: 50 },
        { index: 102, start: 5100, end: 5150, size: 50 },
      ]

      render(<CorpusManager />)

      expect(screen.getByText('Test Document 100')).toBeInTheDocument()
      expect(screen.getByText('Test Document 101')).toBeInTheDocument()
      expect(screen.getByText('Test Document 102')).toBeInTheDocument()
      expect(screen.queryByText('Test Document 0')).not.toBeInTheDocument()
      expect(screen.queryByText('Test Document 499')).not.toBeInTheDocument()
    })

    it('select all selects only available rows', async () => {
      const rows = [
        mockDoc('doc-1', 'D1', 'A1'),
        mockDoc('doc-2', 'D2', 'A2'),
        mockDoc('doc-3', 'D3', 'A3'),
      ]

      vi.mocked(useDocuments).mockReturnValue({
        data: { data: rows, total: 3 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any)

      mockVirtualItems = [{ index: 0, start: 0, end: 50, size: 50 }]

      render(<CorpusManager />)
      const checkboxes = screen.getAllByRole('checkbox')
      const selectAll = checkboxes[0]
      await userEvent.click(selectAll)

      const state = useCorpusStore.getState().selectedRows
      expect(state['doc-1']).toBe(true)
      expect(state['doc-2']).toBe(true)
      expect(state['doc-3']).toBe(true)
    })
  })
})
