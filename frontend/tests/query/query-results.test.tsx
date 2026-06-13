import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryResults } from '@/features/query/query-results';
import { useQueryStore } from '@/features/query/query-store';

describe('QueryResults Component', () => {
  beforeEach(() => {
    useQueryStore.setState({ executionState: 'idle', currentAnswer: null });
  });

  it('renders nothing when idle', () => {
    const { container } = render(<QueryResults />);
    expect(container).toBeEmptyDOMElement();
  });

  describe('loading states', () => {
    const loadingStates = [
      { state: 'parsing', text: 'Analyzing query...' },
      { state: 'planning', text: 'Formulating execution plan...' },
      { state: 'reasoning', text: 'Extracting semantic evidence...' },
      { state: 'synthesis', text: 'Synthesizing research response...' },
    ];

    it.each(loadingStates)('renders loading UI for %s state with text "%s"', ({ state, text }) => {
      useQueryStore.setState({ executionState: state as any });
      render(<QueryResults />);
      expect(screen.getByText(text)).toBeInTheDocument();
      // Accessibility check for aria-live
      const liveRegion = screen.getByText(text).closest('[aria-live="polite"]');
      expect(liveRegion).not.toBeNull();
    });
  });

  it('renders failure state', () => {
    useQueryStore.setState({ executionState: 'failed' });
    render(<QueryResults />);
    expect(screen.getByText('Failed to execute query.')).toBeInTheDocument();
  });

  it('renders failure state when completed but no answer', () => {
    useQueryStore.setState({ executionState: 'completed', currentAnswer: null });
    render(<QueryResults />);
    expect(screen.getByText('Failed to execute query.')).toBeInTheDocument();
  });

  describe('completed state with answer', () => {
    beforeEach(() => {
      useQueryStore.setState({ 
        executionState: 'completed', 
        currentAnswer: {
          queryId: '1',
          text: 'First paragraph.\n\nSecond paragraph.\n\nThird paragraph.',
          confidence: 0.9,
          evidence: [],
          traces: [],
          metrics: { executionTimeMs: 100, evidenceCount: 0, reasoningSteps: 0, overallConfidence: 0.9 }
        }
      });
    });

    it('renders Research Synthesis title', () => {
      render(<QueryResults />);
      expect(screen.getByText('Research Synthesis')).toBeInTheDocument();
    });

    it('splits text by double newline and renders multiple paragraphs', () => {
      render(<QueryResults />);
      expect(screen.getByText('First paragraph.')).toBeInTheDocument();
      expect(screen.getByText('Second paragraph.')).toBeInTheDocument();
      expect(screen.getByText('Third paragraph.')).toBeInTheDocument();
    });
  });
});
