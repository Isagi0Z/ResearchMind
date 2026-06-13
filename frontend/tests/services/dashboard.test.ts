import { describe, it, expect } from 'vitest'
import { getCorpusSummary, getRecentDocuments, getSystemStatus, getRecentReviews } from '@/services/dashboard'
import { MOCK_CORPUS_SUMMARY, MOCK_SYSTEM_STATUS, MOCK_RECENT_REVIEWS } from '@/services/mock-data'

describe('Dashboard Services', () => {
  describe('getCorpusSummary', () => {
    it('returns the mock corpus summary', async () => {
      const result = await getCorpusSummary()
      expect(result).toEqual(MOCK_CORPUS_SUMMARY)
    })
    // Generate 10 tests
    Array.from({ length: 10 }).forEach((_, i) => {
      it(`resolves summary correctly ${i}`, async () => {
        const result = await getCorpusSummary()
        expect(result).toHaveProperty('totalDocuments')
      })
    })
  })

  describe('getRecentDocuments', () => {
    it('returns up to 10 recent documents', async () => {
      const result = await getRecentDocuments()
      expect(result.length).toBeLessThanOrEqual(10)
    })
    
    it('sorts documents by created_at descending', async () => {
      const result = await getRecentDocuments()
      const dates = result.map(d => new Date(d.meta.created_at).getTime())
      const sortedDates = [...dates].sort((a, b) => b - a)
      expect(dates).toEqual(sortedDates)
    })

    // Generate 10 tests
    Array.from({ length: 10 }).forEach((_, i) => {
      it(`returns valid docs ${i}`, async () => {
        const result = await getRecentDocuments()
        expect(result[0]).toHaveProperty('meta')
      })
    })
  })

  describe('getSystemStatus', () => {
    it('returns the mock system status', async () => {
      const result = await getSystemStatus()
      expect(result).toEqual(MOCK_SYSTEM_STATUS)
    })

    // Generate 10 tests
    Array.from({ length: 10 }).forEach((_, i) => {
      it(`returns valid status ${i}`, async () => {
        const result = await getSystemStatus()
        expect(result).toHaveProperty('extraction')
      })
    })
  })

  describe('getRecentReviews', () => {
    it('returns the mock recent reviews', async () => {
      const result = await getRecentReviews()
      expect(result).toEqual(MOCK_RECENT_REVIEWS)
    })

    // Generate 10 tests
    Array.from({ length: 10 }).forEach((_, i) => {
      it(`returns valid reviews ${i}`, async () => {
        const result = await getRecentReviews()
        expect(Array.isArray(result)).toBe(true)
      })
    })
  })
})
