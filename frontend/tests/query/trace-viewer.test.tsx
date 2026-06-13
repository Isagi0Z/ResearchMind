import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TraceViewer } from '@/features/query/trace-viewer';
import { useQueryStore } from '@/features/query/query-store';

describe('TraceViewer Component', () => {
  beforeEach(() => {
    useQueryStore.setState({ currentAnswer: null, selectedReasoningStepId: null });
  });

  it('renders nothing when there is no currentAnswer', () => {
    const { container } = render(<TraceViewer />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when there are no traces', () => {
    useQueryStore.setState({ 
      currentAnswer: {
        queryId: '1', text: 'T', confidence: 1, evidence: [], traces: [], metrics: {
          executionTimeMs: 100, evidenceCount: 0, reasoningSteps: 0, overallConfidence: 1
        }
      } 
    });
    const { container } = render(<TraceViewer />);
    expect(container).toBeEmptyDOMElement();
  });

  describe('with traces', () => {
    const mockTraces = [
      { id: 'tr1', order: 1, description: 'Step 1 description', confidence: 0.9, pathId: 'path-101' },
      { id: 'tr2', order: 2, description: 'Step 2 description', confidence: 0.8, pathId: 'path-102' },
      { id: 'tr3', order: 3, description: 'Step 3 description', confidence: 0.7, pathId: 'path-103' },
    ];

    beforeEach(() => {
      useQueryStore.setState({ 
        currentAnswer: {
          queryId: '1', text: 'T', confidence: 1, evidence: [], traces: mockTraces, metrics: {
            executionTimeMs: 100, evidenceCount: 0, reasoningSteps: mockTraces.length, overallConfidence: 1
          }
        } 
      });
    });

    it('renders the header and trace count', () => {
      render(<TraceViewer />);
      expect(screen.getByText('Reasoning Trace')).toBeInTheDocument();
      expect(screen.getByText('3 steps')).toBeInTheDocument();
    });

    it('renders all trace items', () => {
      render(<TraceViewer />);
      mockTraces.forEach(tr => {
        expect(screen.getByText(tr.order.toString())).toBeInTheDocument();
        expect(screen.getByText(tr.description)).toBeInTheDocument();
        expect(screen.getByText(tr.pathId)).toBeInTheDocument();
        expect(screen.getByText(`conf: ${tr.confidence.toFixed(2)}`)).toBeInTheDocument();
      });
    });

    describe('interactivity & accessibility', () => {
      it('selects trace on click', () => {
        render(<TraceViewer />);
        const firstTr = screen.getByText('Step 1 description').closest('[role="button"]');
        expect(firstTr).not.toBeNull();
        fireEvent.click(firstTr!);
        expect(useQueryStore.getState().selectedReasoningStepId).toBe('tr1');
      });

      it('deselects trace on second click', () => {
        useQueryStore.setState({ selectedReasoningStepId: 'tr1' });
        render(<TraceViewer />);
        const firstTr = screen.getByText('Step 1 description').closest('[role="button"]');
        fireEvent.click(firstTr!);
        expect(useQueryStore.getState().selectedReasoningStepId).toBeNull();
      });

      it('can be triggered by Enter key', () => {
        render(<TraceViewer />);
        const firstTr = screen.getByText('Step 1 description').closest('[role="button"]');
        fireEvent.keyDown(firstTr!, { key: 'Enter', code: 'Enter' });
        expect(useQueryStore.getState().selectedReasoningStepId).toBe('tr1');
      });

      it('can be triggered by Space key', () => {
        render(<TraceViewer />);
        const firstTr = screen.getByText('Step 1 description').closest('[role="button"]');
        fireEvent.keyDown(firstTr!, { key: ' ', code: 'Space' });
        expect(useQueryStore.getState().selectedReasoningStepId).toBe('tr1');
      });
      
      it('items should have tabIndex=0 for keyboard nav', () => {
         render(<TraceViewer />);
         const buttons = screen.getAllByRole('button');
         buttons.forEach(btn => {
            expect(btn).toHaveAttribute('tabindex', '0');
         });
      });
    });
  });
});
