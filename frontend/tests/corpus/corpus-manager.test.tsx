import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CorpusManager } from '@/features/corpus/corpus-manager'
import { useDocuments } from '@/features/corpus/use-corpus-data'
import { useCorpusStore } from '@/features/corpus/corpus-store'

vi.mock('@/features/corpus/use-corpus-data', () => ({
  useDocuments: vi.fn(),
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
      data: { data: [], total: 0, pageCount: 0 },
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
        data: [
          {
            meta: { ruo_id: 'doc-1', pipeline_stages: ['extracted'] },
            header: {
              title: 'Test Document 1',
              authors: [{ full_name: 'Author 1' }],
              publication_date: '2023-01-01',
            },
            entities: [{ id: 'ent-1' }]
          }
        ],
        total: 1,
        pageCount: 1,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    expect(screen.getByText('Test Document 1')).toBeInTheDocument()
    expect(screen.getByText('Author 1')).toBeInTheDocument()
    expect(screen.getByText('2023')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument() // entities count
    expect(screen.getByText('extracted')).toBeInTheDocument()
  })

  it('handles search input', async () => {
    vi.mocked(useDocuments).mockReturnValue({
      data: { data: [], total: 0, pageCount: 0 },
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
        data: [
          {
            meta: { ruo_id: 'doc-1', pipeline_stages: [] },
            header: { title: 'Test Document 1', authors: [] },
            entities: []
          }
        ],
        total: 1,
        pageCount: 1,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any)

    render(<CorpusManager />)
    const checkboxes = screen.getAllByRole('checkbox')
    // First is select all, second is row checkbox
    const rowCheckbox = checkboxes[1]
    
    await userEvent.click(rowCheckbox)
    expect(useCorpusStore.getState().selectedRows['doc-1']).toBe(true)
  })

  describe('Virtualization behavior', () => {
    it('sets up the virtualizer with correct count', () => {
      const largeData = Array.from({ length: 500 }).map((_, i) => ({
        meta: { ruo_id: `doc-${i}`, pipeline_stages: [] },
        header: { title: `Test Document ${i}`, authors: [] },
        entities: []
      }))

      vi.mocked(useDocuments).mockReturnValue({
        data: {
          data: largeData,
          total: 500,
          pageCount: 1,
        },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any)

      render(<CorpusManager />)
      expect(mockVirtualizerCount).toBe(500)
    })

    it('renders only virtual items returned by virtualizer (DOM count limit)', () => {
      const largeData = Array.from({ length: 500 }).map((_, i) => ({
        meta: { ruo_id: `doc-${i}`, pipeline_stages: [] },
        header: { title: `Test Document ${i}`, authors: [] },
        entities: []
      }))

      vi.mocked(useDocuments).mockReturnValue({
        data: {
          data: largeData,
          total: 500,
          pageCount: 1,
        },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any)

      // Mock only 3 visible items
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
    
    it('select all selects only available rows but correctly updates state for all rows', async () => {
      const rowsData = [
        { meta: { ruo_id: `doc-1`, pipeline_stages: [] }, header: { title: `D1`, authors: [] }, entities: [] },
        { meta: { ruo_id: `doc-2`, pipeline_stages: [] }, header: { title: `D2`, authors: [] }, entities: [] },
        { meta: { ruo_id: `doc-3`, pipeline_stages: [] }, header: { title: `D3`, authors: [] }, entities: [] },
      ];
      
      vi.mocked(useDocuments).mockReturnValue({
        data: { data: rowsData, total: 3, pageCount: 1 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any)

      mockVirtualItems = [
        { index: 0, start: 0, end: 50, size: 50 },
      ]

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
