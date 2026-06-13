import { describe, it, expect } from 'vitest';
import { generateMockAnswer, determineQueryType, MOCK_QUERY_SUGGESTIONS } from '@/services/mock-query';

describe('mock-query services', () => {
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

  describe('generateMockAnswer determinism', () => {
    const seeds = Array.from({ length: 20 }, (_, i) => `deterministic test query seed ${i}`);
    
    it.each(seeds)('should produce identical results for "%s"', (seed) => {
      const result1 = generateMockAnswer(seed);
      const result2 = generateMockAnswer(seed);
      expect(result1).toEqual(result2);
    });

    it('should produce different results for different inputs', () => {
      const result1 = generateMockAnswer('query 1');
      const result2 = generateMockAnswer('query 2');
      expect(result1.queryId).not.toEqual(result2.queryId);
      expect(result1).not.toEqual(result2);
    });
    
    it('should format COMPARISON text correctly', () => {
      const res = generateMockAnswer('compare A and B');
      expect(res.text).toContain('On one hand:');
      expect(res.text).toContain('On the other hand:');
    });

    it('should format CONTRADICTION text correctly', () => {
      const res = generateMockAnswer('contradict A and B');
      expect(res.text).toContain('Conflict Detected!');
      expect(res.text).toContain('However, conflicting evidence suggests:');
    });
    
    it('should format EXPLANATION text correctly', () => {
      const res = generateMockAnswer('explain A and B');
      expect(res.text).toContain('Therefore, we conclude the system is bounded.');
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

    describe('Generated Answer Constraints', () => {
       const res = generateMockAnswer('What is the future gap?');
       it('should have evidence between 3 and 12', () => {
          expect(res.evidence.length).toBeGreaterThanOrEqual(3);
          expect(res.evidence.length).toBeLessThanOrEqual(12);
       });
       it('should have traces between 2 and 6', () => {
          expect(res.traces.length).toBeGreaterThanOrEqual(2);
          expect(res.traces.length).toBeLessThanOrEqual(6);
       });
       it('should populate metrics correctly', () => {
          expect(res.metrics.evidenceCount).toBe(res.evidence.length);
          expect(res.metrics.reasoningSteps).toBe(res.traces.length);
          expect(res.metrics.executionTimeMs).toBeGreaterThanOrEqual(800);
          expect(res.metrics.executionTimeMs).toBeLessThanOrEqual(4500);
          expect(res.metrics.overallConfidence).toBeGreaterThanOrEqual(0.8);
          expect(res.metrics.overallConfidence).toBeLessThanOrEqual(1.0);
       });
    });
  });
});
