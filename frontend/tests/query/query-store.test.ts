import { describe, it, expect, beforeEach } from 'vitest';
import { useQueryStore } from '@/features/query/query-store';
import { ParsedQuery, ResearchAnswer } from '@/types/query';

describe('QueryStore', () => {
  beforeEach(() => {
    useQueryStore.setState({
      activeQueryText: '',
      executionState: 'idle',
      currentAnswer: null,
      queryHistory: [],
      selectedEvidenceId: null,
      selectedReasoningStepId: null,
    });
  });

  describe('activeQueryText', () => {
    const texts = Array.from({ length: 10 }, (_, i) => `Test query ${i}`);
    it.each(texts)('should update active query text to %s', (text) => {
      useQueryStore.getState().setActiveQueryText(text);
      expect(useQueryStore.getState().activeQueryText).toBe(text);
    });
  });

  describe('executionState', () => {
    const states: any[] = ['idle', 'parsing', 'planning', 'reasoning', 'synthesis', 'completed', 'failed'];
    it.each(states)('should update execution state to %s', (state) => {
      useQueryStore.getState().setExecutionState(state);
      expect(useQueryStore.getState().executionState).toBe(state);
    });
  });

  describe('currentAnswer', () => {
    it('should set current answer', () => {
      const mockAnswer: ResearchAnswer = {
        queryId: '123', text: 'test', confidence: 0.9, evidence: [], traces: [], metrics: { executionTimeMs: 100, evidenceCount: 0, reasoningSteps: 0, overallConfidence: 0.9 }
      };
      useQueryStore.getState().setCurrentAnswer(mockAnswer);
      expect(useQueryStore.getState().currentAnswer).toEqual(mockAnswer);
    });

    it('should set current answer to null', () => {
      useQueryStore.getState().setCurrentAnswer(null);
      expect(useQueryStore.getState().currentAnswer).toBeNull();
    });
  });

  describe('queryHistory', () => {
    it('should add to history', () => {
      const query1: ParsedQuery = { id: '1', text: 'Q1', type: 'FACTUAL' };
      useQueryStore.getState().addToHistory(query1);
      expect(useQueryStore.getState().queryHistory).toEqual([query1]);
    });

    it('should prepend to history', () => {
      const query1: ParsedQuery = { id: '1', text: 'Q1', type: 'FACTUAL' };
      const query2: ParsedQuery = { id: '2', text: 'Q2', type: 'EXPLANATION' };
      useQueryStore.getState().addToHistory(query1);
      useQueryStore.getState().addToHistory(query2);
      expect(useQueryStore.getState().queryHistory).toEqual([query2, query1]);
    });

    it('should deduplicate history based on id and move to top', () => {
      const query1: ParsedQuery = { id: '1', text: 'Q1', type: 'FACTUAL' };
      const query2: ParsedQuery = { id: '2', text: 'Q2', type: 'EXPLANATION' };
      useQueryStore.getState().addToHistory(query1);
      useQueryStore.getState().addToHistory(query2);
      useQueryStore.getState().addToHistory(query1);
      expect(useQueryStore.getState().queryHistory).toEqual([query1, query2]);
    });

    it('should limit history to 50 items', () => {
      for (let i = 0; i < 60; i++) {
        useQueryStore.getState().addToHistory({ id: `${i}`, text: `Q${i}`, type: 'FACTUAL' });
      }
      expect(useQueryStore.getState().queryHistory).toHaveLength(50);
      expect(useQueryStore.getState().queryHistory[0].id).toBe('59');
      expect(useQueryStore.getState().queryHistory[49].id).toBe('10');
    });
  });

  describe('selections', () => {
    it('should set selected evidence id', () => {
      useQueryStore.getState().setSelectedEvidenceId('ev-1');
      expect(useQueryStore.getState().selectedEvidenceId).toBe('ev-1');
      useQueryStore.getState().setSelectedEvidenceId(null);
      expect(useQueryStore.getState().selectedEvidenceId).toBeNull();
    });

    it('should set selected reasoning step id', () => {
      useQueryStore.getState().setSelectedReasoningStepId('step-1');
      expect(useQueryStore.getState().selectedReasoningStepId).toBe('step-1');
      useQueryStore.getState().setSelectedReasoningStepId(null);
      expect(useQueryStore.getState().selectedReasoningStepId).toBeNull();
    });
  });
});
