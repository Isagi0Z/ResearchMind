import React from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryHistory } from '@/features/query/query-history';
import { useQueryStore } from '@/features/query/query-store';

describe('QueryHistory Component', () => {
  beforeEach(() => {
    useQueryStore.setState({ queryHistory: [], activeQueryText: '' });
  });

  it('renders empty state when history is empty', () => {
    render(<QueryHistory />);
    expect(screen.getByText('No recent queries.')).toBeInTheDocument();
  });

  describe('with history items', () => {
    const mockHistory = [
      { id: '1', text: 'First query', type: 'FACTUAL' as const },
      { id: '2', text: 'Second query', type: 'EXPLANATION' as const },
      { id: '3', text: 'Third query', type: 'COMPARISON' as const },
      { id: '4', text: 'Fourth query', type: 'CONSENSUS' as const },
      { id: '5', text: 'Fifth query', type: 'CONTRADICTION' as const },
    ];

    beforeEach(() => {
      useQueryStore.setState({ queryHistory: mockHistory });
    });

    it('renders all history items', () => {
      render(<QueryHistory />);
      mockHistory.forEach(q => {
        expect(screen.getByText(q.text)).toBeInTheDocument();
      });
    });

    it.each(mockHistory)('clicking on history item "%s.text" updates active query text', (q) => {
      render(<QueryHistory />);
      const button = screen.getByText(q.text).closest('button');
      expect(button).not.toBeNull();
      fireEvent.click(button!);
      expect(useQueryStore.getState().activeQueryText).toBe(q.text);
    });
  });

  describe('accessibility', () => {
    it('history buttons should be focusable', () => {
      useQueryStore.setState({ 
        queryHistory: [{ id: '1', text: 'Test query', type: 'FACTUAL' }] 
      });
      render(<QueryHistory />);
      const button = screen.getByRole('button');
      button.focus();
      expect(button).toHaveFocus();
    });
  });
});
