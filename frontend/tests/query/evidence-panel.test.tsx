import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EvidencePanel } from '@/features/query/evidence-panel';
import { useQueryStore } from '@/features/query/query-store';

describe('EvidencePanel Component', () => {
  beforeEach(() => {
    useQueryStore.setState({ currentAnswer: null, selectedEvidenceId: null });
  });

  it('renders nothing when there is no currentAnswer', () => {
    const { container } = render(<EvidencePanel />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when there is no evidence', () => {
    useQueryStore.setState({ 
      currentAnswer: {
        queryId: '1', text: 'T', confidence: 1, evidence: [], traces: [], metrics: {
          executionTimeMs: 100, evidenceCount: 0, reasoningSteps: 0, overallConfidence: 1
        }
      } 
    });
    const { container } = render(<EvidencePanel />);
    expect(container).toBeEmptyDOMElement();
  });

  describe('with evidence', () => {
    const mockEvidence = [
      { id: 'ev1', sourceDocId: 'doc1', sourceTitle: 'Source 1 Title', excerpt: 'Excerpt 1', confidence: 0.95 },
      { id: 'ev2', sourceDocId: 'doc2', sourceTitle: 'Source 2 Title', excerpt: 'Excerpt 2', confidence: 0.85 },
      { id: 'ev3', sourceDocId: 'doc3', sourceTitle: 'Source 3 Title', excerpt: 'Excerpt 3', confidence: 0.75 },
    ];

    beforeEach(() => {
      useQueryStore.setState({ 
        currentAnswer: {
          queryId: '1', text: 'T', confidence: 1, evidence: mockEvidence, traces: [], metrics: {
            executionTimeMs: 100, evidenceCount: mockEvidence.length, reasoningSteps: 0, overallConfidence: 1
          }
        } 
      });
    });

    it('renders the header and evidence count', () => {
      render(<EvidencePanel />);
      expect(screen.getByText('Evidence Sources')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument(); // count badge
    });

    it('renders all evidence items', () => {
      render(<EvidencePanel />);
      mockEvidence.forEach(ev => {
        expect(screen.getByText(ev.sourceTitle)).toBeInTheDocument();
        expect(screen.getByText(`"${ev.excerpt}"`)).toBeInTheDocument();
        expect(screen.getByText(Math.round(ev.confidence * 100).toString())).toBeInTheDocument();
      });
    });

    describe('interactivity & accessibility', () => {
      it('selects evidence on click', () => {
        render(<EvidencePanel />);
        const firstEv = screen.getByText('Source 1 Title').closest('[role="button"]');
        expect(firstEv).not.toBeNull();
        fireEvent.click(firstEv!);
        expect(useQueryStore.getState().selectedEvidenceId).toBe('ev1');
      });

      it('deselects evidence on second click', () => {
        useQueryStore.setState({ selectedEvidenceId: 'ev1' });
        render(<EvidencePanel />);
        const firstEv = screen.getByText('Source 1 Title').closest('[role="button"]');
        fireEvent.click(firstEv!);
        expect(useQueryStore.getState().selectedEvidenceId).toBeNull();
      });

      it('has aria-pressed set correctly', () => {
        useQueryStore.setState({ selectedEvidenceId: 'ev1' });
        render(<EvidencePanel />);
        const firstEv = screen.getByText('Source 1 Title').closest('[role="button"]');
        const secondEv = screen.getByText('Source 2 Title').closest('[role="button"]');
        expect(firstEv).toHaveAttribute('aria-pressed', 'true');
        expect(secondEv).toHaveAttribute('aria-pressed', 'false');
      });

      it('can be triggered by Enter key', () => {
        render(<EvidencePanel />);
        const firstEv = screen.getByText('Source 1 Title').closest('[role="button"]');
        fireEvent.keyDown(firstEv!, { key: 'Enter', code: 'Enter' });
        expect(useQueryStore.getState().selectedEvidenceId).toBe('ev1');
      });

      it('can be triggered by Space key', () => {
        render(<EvidencePanel />);
        const firstEv = screen.getByText('Source 1 Title').closest('[role="button"]');
        fireEvent.keyDown(firstEv!, { key: ' ', code: 'Space' });
        expect(useQueryStore.getState().selectedEvidenceId).toBe('ev1');
      });
      
      it('items should have tabIndex=0', () => {
         render(<EvidencePanel />);
         const buttons = screen.getAllByRole('button');
         buttons.forEach(btn => {
            expect(btn).toHaveAttribute('tabindex', '0');
         });
      });
    });
  });
});
