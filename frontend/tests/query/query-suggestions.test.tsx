import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QuerySuggestions } from '@/features/query/query-suggestions';
import { useQueryStore } from '@/features/query/query-store';
import { MOCK_QUERY_SUGGESTIONS } from '@/services/mock-query';

describe('QuerySuggestions Component', () => {
  beforeEach(() => {
    useQueryStore.setState({ activeQueryText: '' });
  });

  it('renders all mock suggestions', () => {
    render(<QuerySuggestions />);
    expect(screen.getByText('Suggested Queries')).toBeInTheDocument();
    
    MOCK_QUERY_SUGGESTIONS.forEach(suggestion => {
      expect(screen.getByText(suggestion.text)).toBeInTheDocument();
      expect(screen.getByText(suggestion.type)).toBeInTheDocument();
    });
  });

  describe('interactivity', () => {
    it.each(MOCK_QUERY_SUGGESTIONS)('clicking on suggestion "%s.text" updates active query text', (suggestion) => {
      render(<QuerySuggestions />);
      const button = screen.getByText(suggestion.text).closest('button');
      expect(button).not.toBeNull();
      fireEvent.click(button!);
      expect(useQueryStore.getState().activeQueryText).toBe(suggestion.text);
    });
  });

  describe('accessibility', () => {
    it('suggestion buttons should be focusable', () => {
      render(<QuerySuggestions />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        button.focus();
        expect(button).toHaveFocus();
      });
    });
  });
});
