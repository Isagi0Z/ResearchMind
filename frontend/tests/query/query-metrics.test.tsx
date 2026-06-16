import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryMetrics } from '@/features/query/query-metrics';
import { useQueryStore } from '@/features/query/query-store';
import { ResearchAnswer } from '@/types/query';

describe('QueryMetrics Component', () => {
  beforeEach(() => {
    useQueryStore.setState({ currentAnswer: null });
  });

  it('renders nothing when there is no currentAnswer', () => {
    const { container } = render(<QueryMetrics />);
    expect(container).toBeEmptyDOMElement();
  });

  describe('with mock answer', () => {
    const mockAnswer: ResearchAnswer = {
      queryId: '1',
      text: 'Sample answer',
      confidence: 0.9,
      evidence: [],
      traces: [],
      metrics: {
        executionTimeMs: 1250,
        evidenceCount: 5,
        reasoningSteps: 3,
        overallConfidence: 0.85
      }
    };

    beforeEach(() => {
      useQueryStore.setState({ currentAnswer: mockAnswer });
    });

    it('renders Execution Time correctly formatted', () => {
      render(<QueryMetrics />);
      expect(screen.getByText('Execution Time')).toBeInTheDocument();
      expect(screen.getByText('1.25s')).toBeInTheDocument();
    });

    it('renders Evidence Extracted count correctly', () => {
      render(<QueryMetrics />);
      expect(screen.getByText('Evidence Extracted')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('renders Reasoning Steps count correctly', () => {
      render(<QueryMetrics />);
      expect(screen.getByText('Reasoning Steps')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('renders Overall Confidence correctly formatted as percentage', () => {
      render(<QueryMetrics />);
      expect(screen.getByText('Overall Confidence')).toBeInTheDocument();
      expect(screen.getByText('85%')).toBeInTheDocument();
    });
  });

  describe('edge case metrics', () => {
    const edgeCases = [
      { executionTimeMs: 0, evidenceCount: 0, reasoningSteps: 0, overallConfidence: 0, timeStr: '0.00s', confStr: '0%' },
      { executionTimeMs: 99, evidenceCount: 1, reasoningSteps: 1, overallConfidence: 0.01, timeStr: '0.10s', confStr: '1%' },
      { executionTimeMs: 10000, evidenceCount: 100, reasoningSteps: 50, overallConfidence: 1, timeStr: '10.00s', confStr: '100%' },
    ];

    it.each(edgeCases)('renders metric values correctly for edge case %o', (metrics) => {
      useQueryStore.setState({ 
        currentAnswer: {
          queryId: '1', text: 'T', confidence: 1, evidence: [], traces: [], metrics: {
            executionTimeMs: metrics.executionTimeMs,
            evidenceCount: metrics.evidenceCount,
            reasoningSteps: metrics.reasoningSteps,
            overallConfidence: metrics.overallConfidence
          }
        } 
      });
      render(<QueryMetrics />);
      expect(screen.getByText(metrics.timeStr)).toBeInTheDocument();
      expect(screen.getAllByText(metrics.evidenceCount.toString())[0]).toBeInTheDocument();
      expect(screen.getAllByText(metrics.reasoningSteps.toString())[0]).toBeInTheDocument();
      expect(screen.getByText(metrics.confStr)).toBeInTheDocument();
    });
  });
});
