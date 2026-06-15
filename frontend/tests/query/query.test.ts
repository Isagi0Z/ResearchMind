import { describe, it, expect, vi, beforeEach } from 'vitest';
import { generateAnswer, determineQueryType, MOCK_QUERY_SUGGESTIONS } from '@/services/query';
import { apiClient } from '@/lib/api-client';

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    post: vi.fn()
  }
}));

describe('query services', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('determineQueryType', () => {
    const queryCases = [
      ['compare A and B', 'COMPARISON'],
      ['A versus B', 'COMPARISON'],
      ['A vs B', 'COMPARISON'],
      ['explain the concept of X', 'EXPLANATION'],
      ['how does Y work', 'EXPLANATION'],
      ['what is the consensus on Z', 'CONSENSUS'],
      ['do researchers agree on W', 'CONSENSUS'],
      ['does A contradict B', 'CONTRADICTION'],
      ['what is the conflict here', 'CONTRADICTION'],
      ['is there a research gap in this area', 'RESEARCH_GAP'],
      ['what is the future of this tech', 'RESEARCH_GAP'],
      ['trace the origins', 'MULTI_HOP'],
      ['connect these ideas', 'MULTI_HOP'],
      ['explore new possibilities', 'EXPLORATION'],
      ['emerging trends in graph UX', 'EXPLORATION'],
      ['what is the capital of France', 'FACTUAL'],
      ['who won the game', 'FACTUAL']
    ];
    
    const variations: [string, string][] = [];
    queryCases.forEach(([text, type]) => {
      variations.push([text, type]);
      variations.push([text.toUpperCase(), type]);
      variations.push([text.charAt(0).toUpperCase() + text.slice(1), type]);
      variations.push([` ${text} `, type]);
      variations.push([`${text}?`, type]);
    });

    it.each(variations)('should determine "%s" as %s', (text, expectedType) => {
      expect(determineQueryType(text as string)).toBe(expectedType);
    });

    it('should default to FACTUAL for empty strings', () => {
      expect(determineQueryType('')).toBe('FACTUAL');
    });

    it('should default to FACTUAL for nonsense', () => {
      expect(determineQueryType('asdfghjkl')).toBe('FACTUAL');
    });
  });

  describe('generateAnswer API interaction', () => {
    it('should call apiClient with correct payload', async () => {
      const mockBackendResponse = {
        answer: {
          query_id: '123',
          text: 'mock response text',
          confidence: 0.95,
          metrics: { execution_time_ms: 1000 }
        },
        evidence: [],
        step_route: { steps: [] }
      };

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockBackendResponse);

      const res = await generateAnswer('test query');
      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/query/answer', {
        query_id: expect.any(String),
        raw_query: 'test query'
      });
      expect(res.text).toBe('mock response text');
    });
  });

  describe('MOCK_QUERY_SUGGESTIONS properties', () => {
    it('should have 8 suggestions', () => {
       expect(MOCK_QUERY_SUGGESTIONS).toHaveLength(8);
    });

    it.each(MOCK_QUERY_SUGGESTIONS.map(s => [s.text, s.type, s.id]))(
      'suggestion "%s" should have type %s and valid id %s', (text, type, id) => {
        expect(text).toBeTruthy();
        expect(type).toBeTruthy();
        expect(id).toBeTruthy();
        // Ensure it matches our parse logic
        expect(determineQueryType(text as string)).toBe(type);
    });
  });
});
