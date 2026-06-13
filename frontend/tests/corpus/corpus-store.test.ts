import { describe, it, expect, beforeEach } from 'vitest'
import { useCorpusStore } from '@/features/corpus/corpus-store'

describe('Corpus Store', () => {
  beforeEach(() => {
    useCorpusStore.setState({
      searchQuery: '',
      filters: { yearRange: [2000, 2026], authors: [], source: [], status: [] },
      sort: { column: 'year', direction: 'desc' },
      pagination: { pageIndex: 0, pageSize: 1000 },
      selectedRows: {},
    })
  })

  it('initializes with default state', () => {
    const state = useCorpusStore.getState()
    expect(state.searchQuery).toBe('')
    expect(state.filters.yearRange).toEqual([2000, 2026])
    expect(state.sort).toEqual({ column: 'year', direction: 'desc' })
    expect(state.pagination).toEqual({ pageIndex: 0, pageSize: 1000 })
    expect(state.selectedRows).toEqual({})
  })

  it('updates search query and resets pagination', () => {
    useCorpusStore.getState().setSearchQuery('test query')
    const state = useCorpusStore.getState()
    expect(state.searchQuery).toBe('test query')
    expect(state.pagination.pageIndex).toBe(0)
  })

  it('updates filters and resets pagination', () => {
    useCorpusStore.getState().setFilters({ authors: ['John Doe'] })
    const state = useCorpusStore.getState()
    expect(state.filters.authors).toEqual(['John Doe'])
    expect(state.pagination.pageIndex).toBe(0)
  })

  it('clears filters and resets pagination', () => {
    useCorpusStore.getState().setFilters({ authors: ['John Doe'] })
    useCorpusStore.getState().clearFilters()
    const state = useCorpusStore.getState()
    expect(state.filters.authors).toEqual([])
    expect(state.pagination.pageIndex).toBe(0)
  })

  it('updates sort config', () => {
    useCorpusStore.getState().setSort({ column: 'title', direction: 'asc' })
    const state = useCorpusStore.getState()
    expect(state.sort).toEqual({ column: 'title', direction: 'asc' })
  })

  it('updates pagination', () => {
    useCorpusStore.getState().setPagination({ pageIndex: 2 })
    const state = useCorpusStore.getState()
    expect(state.pagination.pageIndex).toBe(2)
    expect(state.pagination.pageSize).toBe(1000) // retains old value
  })

  it('sets selected rows', () => {
    useCorpusStore.getState().setSelectedRows({ 'doc-1': true })
    const state = useCorpusStore.getState()
    expect(state.selectedRows).toEqual({ 'doc-1': true })
  })

  it('toggles row selection', () => {
    useCorpusStore.getState().toggleRowSelection('doc-1')
    expect(useCorpusStore.getState().selectedRows['doc-1']).toBe(true)
    
    useCorpusStore.getState().toggleRowSelection('doc-1')
    expect(useCorpusStore.getState().selectedRows['doc-1']).toBe(false)
  })

  it('clears selection', () => {
    useCorpusStore.getState().setSelectedRows({ 'doc-1': true })
    useCorpusStore.getState().clearSelection()
    const state = useCorpusStore.getState()
    expect(state.selectedRows).toEqual({})
  })
})
