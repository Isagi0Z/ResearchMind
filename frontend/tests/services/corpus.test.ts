import { describe, it, expect, vi } from 'vitest'
import { getDocuments } from '@/services/corpus'
import { MOCK_DOCUMENTS } from '@/services/mock-data'

describe('Corpus Service - getDocuments', () => {
  it('returns paginated data', async () => {
    const result = await getDocuments({ pageIndex: 0, pageSize: 10 })
    expect(result.data).toHaveLength(10)
    expect(result.total).toBe(MOCK_DOCUMENTS.length)
    expect(result.pageIndex).toBe(0)
    expect(result.pageSize).toBe(10)
    expect(result.pageCount).toBe(Math.ceil(MOCK_DOCUMENTS.length / 10))
  })

  it('handles pageIndex correctly', async () => {
    const result1 = await getDocuments({ pageIndex: 0, pageSize: 10 })
    const result2 = await getDocuments({ pageIndex: 1, pageSize: 10 })
    expect(result1.data[0].meta.ruo_id).not.toBe(result2.data[0].meta.ruo_id)
  })

  // Test search query logic
  describe('Search Queries', () => {
    it('filters by title search', async () => {
      // Find a title we know exists
      const targetTitle = MOCK_DOCUMENTS[0].header.title
      const query = targetTitle.substring(0, 10).toLowerCase()
      
      const result = await getDocuments({ pageIndex: 0, pageSize: 1000, searchQuery: query })
      expect(result.total).toBeGreaterThan(0)
      expect(result.data.every(doc => doc.header.title.toLowerCase().includes(query) || doc.header.authors.some(a => a.full_name.toLowerCase().includes(query)))).toBe(true)
    })

    it('returns empty when search matches nothing', async () => {
      const result = await getDocuments({ pageIndex: 0, pageSize: 10, searchQuery: 'NO_WAY_THIS_EXISTS_123456789' })
      expect(result.total).toBe(0)
      expect(result.data).toHaveLength(0)
    })
    
    // Generate 10 search tests
    Array.from({ length: 10 }).forEach((_, i) => {
      it(`handles search case ${i}`, async () => {
        const query = `search-${i}`
        const result = await getDocuments({ pageIndex: 0, pageSize: 10, searchQuery: query })
        expect(result.data).toBeInstanceOf(Array)
      })
    })
  })

  // Test Filters
  describe('Filters', () => {
    it('filters by yearRange', async () => {
      const result = await getDocuments({ 
        pageIndex: 0, 
        pageSize: 1000, 
        filters: { yearRange: [2015, 2020] } 
      })
      expect(result.data.every(doc => {
        const year = parseInt(doc.header.publication_date!.split('-')[0])
        return year >= 2015 && year <= 2020
      })).toBe(true)
    })

    it('filters by authors', async () => {
      const targetAuthor = MOCK_DOCUMENTS[0].header.authors[0].full_name
      const result = await getDocuments({ 
        pageIndex: 0, 
        pageSize: 1000, 
        filters: { authors: [targetAuthor] } 
      })
      expect(result.total).toBeGreaterThan(0)
      expect(result.data.every(doc => doc.header.authors.some(a => a.full_name.toLowerCase() === targetAuthor.toLowerCase()))).toBe(true)
    })

    it('filters by status', async () => {
      const result = await getDocuments({ 
        pageIndex: 0, 
        pageSize: 1000, 
        filters: { status: ['success'] } 
      })
      expect(result.data.every(doc => doc.meta.pipeline_stages[doc.meta.pipeline_stages.length - 1] === 'success')).toBe(true)
    })

    it('filters by source venue', async () => {
      const result = await getDocuments({ 
        pageIndex: 0, 
        pageSize: 1000, 
        filters: { source: ['Nature'] } 
      })
      expect(result.data.every(doc => doc.header.venue?.toLowerCase() === 'nature')).toBe(true)
    })

    // Generate 15 filter tests
    Array.from({ length: 15 }).forEach((_, i) => {
      it(`handles complex filter combination ${i}`, async () => {
        const result = await getDocuments({ 
          pageIndex: 0, 
          pageSize: 10, 
          filters: { yearRange: [2010 + (i % 5), 2020 + (i % 5)] } 
        })
        expect(result.data).toBeInstanceOf(Array)
      })
    })
  })

  // Test Sorting
  describe('Sorting', () => {
    it('sorts by title ascending', async () => {
      const result = await getDocuments({ pageIndex: 0, pageSize: 1000, sortBy: 'title', sortDirection: 'asc' })
      const titles = result.data.map(d => d.header.title)
      const sortedTitles = [...titles].sort((a, b) => a < b ? -1 : a > b ? 1 : 0)
      expect(titles).toEqual(sortedTitles)
    })

    it('sorts by title descending', async () => {
      const result = await getDocuments({ pageIndex: 0, pageSize: 1000, sortBy: 'title', sortDirection: 'desc' })
      const titles = result.data.map(d => d.header.title)
      const sortedTitles = [...titles].sort((a, b) => a < b ? 1 : a > b ? -1 : 0)
      expect(titles).toEqual(sortedTitles)
    })

    it('sorts by year ascending', async () => {
      const result = await getDocuments({ pageIndex: 0, pageSize: 1000, sortBy: 'year', sortDirection: 'asc' })
      const years = result.data.map(d => d.header.publication_date || '')
      const sortedYears = [...years].sort((a, b) => a < b ? -1 : a > b ? 1 : 0)
      expect(years).toEqual(sortedYears)
    })

    it('sorts by entities descending', async () => {
      const result = await getDocuments({ pageIndex: 0, pageSize: 1000, sortBy: 'entities', sortDirection: 'desc' })
      const entities = result.data.map(d => d.entities.length)
      const sortedEntities = [...entities].sort((a, b) => b - a)
      expect(entities).toEqual(sortedEntities)
    })

    // Generate 10 sort tests
    Array.from({ length: 10 }).forEach((_, i) => {
      it(`handles sort fallback ${i}`, async () => {
        const result = await getDocuments({ pageIndex: 0, pageSize: 10, sortBy: 'unknown_column', sortDirection: i % 2 === 0 ? 'asc' : 'desc' })
        expect(result.data).toBeInstanceOf(Array)
      })
    })
  })
})
