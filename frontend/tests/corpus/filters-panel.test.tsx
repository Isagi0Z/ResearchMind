import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FiltersPanel } from '@/features/corpus/filters-panel'
import { useCorpusStore } from '@/features/corpus/corpus-store'

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = MockResizeObserver
window.ResizeObserver = MockResizeObserver

describe('FiltersPanel', () => {
  beforeEach(() => {
    useCorpusStore.setState({
      filters: { yearRange: [2000, 2026], authors: [], source: [], status: [] },
    })
  })

  it('renders correctly with default values', () => {
    render(<FiltersPanel />)
    
    expect(screen.getByText('Year Range')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Min')).toHaveValue(2000)
    expect(screen.getByPlaceholderText('Max')).toHaveValue(2026)
    
    expect(screen.getByText('Authors')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Type and press Enter...')).toBeInTheDocument()
    
    expect(screen.getByText('Status')).toBeInTheDocument()
    expect(screen.getByLabelText('Processed')).not.toBeChecked()
    expect(screen.getByLabelText('Pending')).not.toBeChecked()
    expect(screen.getByLabelText('Failed')).not.toBeChecked()
    
    expect(screen.getByText('Source / Venue')).toBeInTheDocument()
    expect(screen.getByLabelText('Journal')).not.toBeChecked()
    expect(screen.getByLabelText('Conference')).not.toBeChecked()
  })

  it('handles typing into min and max year and applying', async () => {
    const onClose = vi.fn()
    render(<FiltersPanel onClose={onClose} />)
    
    const minInput = screen.getByPlaceholderText('Min')
    const maxInput = screen.getByPlaceholderText('Max')
    
    await userEvent.clear(minInput)
    await userEvent.type(minInput, '2010')
    
    await userEvent.clear(maxInput)
    await userEvent.type(maxInput, '2020')
    
    await userEvent.click(screen.getByRole('button', { name: 'Apply Filters' }))
    
    expect(useCorpusStore.getState().filters.yearRange).toEqual([2010, 2020])
    expect(onClose).toHaveBeenCalled()
  })

  it('handles applying with invalid year (uses defaults)', async () => {
    render(<FiltersPanel />)
    
    const minInput = screen.getByPlaceholderText('Min')
    await userEvent.clear(minInput)
    await userEvent.type(minInput, 'invalid')
    
    await userEvent.click(screen.getByRole('button', { name: 'Apply Filters' }))
    expect(useCorpusStore.getState().filters.yearRange[0]).toBe(2000)
  })

  it('handles adding and removing authors via Enter', async () => {
    render(<FiltersPanel />)
    
    const authorInput = screen.getByPlaceholderText('Type and press Enter...')
    
    // Add author 1
    await userEvent.type(authorInput, 'John Doe{Enter}')
    expect(useCorpusStore.getState().filters.authors).toContain('John Doe')
    expect(authorInput).toHaveValue('')
    
    // Add author 2
    await userEvent.type(authorInput, 'Jane Doe{Enter}')
    expect(useCorpusStore.getState().filters.authors).toContain('Jane Doe')
    
    // Test empty string doesn't add
    await userEvent.type(authorInput, '   {Enter}')
    expect(useCorpusStore.getState().filters.authors.length).toBe(2)
    
    // Add duplicate doesn't add
    await userEvent.type(authorInput, 'John Doe{Enter}')
    expect(useCorpusStore.getState().filters.authors.length).toBe(2)
    
    // Remove author
    const removeButtons = screen.getAllByRole('button')
    // Badge removal div has role='button'. We'll find it by clicking the first one inside the authors container
    // Since there are Apply/Clear buttons, we get the specific badge close button.
    // Find the badge containing John Doe. The badge itself contains the text and the button.
    const johnDoeBadge = screen.getByText('John Doe').closest('div.inline-flex')!
    const closeBtn = within(johnDoeBadge).getByRole('button')
    
    await userEvent.click(closeBtn)
    expect(useCorpusStore.getState().filters.authors).not.toContain('John Doe')
    expect(useCorpusStore.getState().filters.authors).toContain('Jane Doe')
  })

  it('removes author via keyboard Enter on remove button', async () => {
    render(<FiltersPanel />)
    
    const authorInput = screen.getByPlaceholderText('Type and press Enter...')
    await userEvent.type(authorInput, 'John Doe{Enter}')
    
    const johnDoeBadge = screen.getByText('John Doe').closest('div.inline-flex')!
    const closeBtn = within(johnDoeBadge).getByRole('button')
    
    closeBtn.focus()
    await userEvent.keyboard('{Enter}')
    
    expect(useCorpusStore.getState().filters.authors).not.toContain('John Doe')
  })

  it('handles toggling statuses', async () => {
    render(<FiltersPanel />)
    
    const processedCheckbox = screen.getByLabelText('Processed')
    const pendingCheckbox = screen.getByLabelText('Pending')
    
    await userEvent.click(processedCheckbox)
    expect(useCorpusStore.getState().filters.status).toContain('success')
    
    await userEvent.click(pendingCheckbox)
    expect(useCorpusStore.getState().filters.status).toContain('partial')
    
    // Uncheck
    await userEvent.click(processedCheckbox)
    expect(useCorpusStore.getState().filters.status).not.toContain('success')
    expect(useCorpusStore.getState().filters.status).toContain('partial')
  })

  it('handles toggling sources', async () => {
    render(<FiltersPanel />)
    
    const journalCheckbox = screen.getByLabelText('Journal')
    const arxivCheckbox = screen.getByLabelText('ArXiv')
    
    await userEvent.click(journalCheckbox)
    expect(useCorpusStore.getState().filters.source).toContain('Journal')
    
    await userEvent.click(arxivCheckbox)
    expect(useCorpusStore.getState().filters.source).toContain('ArXiv')
    
    // Uncheck
    await userEvent.click(journalCheckbox)
    expect(useCorpusStore.getState().filters.source).not.toContain('Journal')
    expect(useCorpusStore.getState().filters.source).toContain('ArXiv')
  })

  it('handles clear behavior', async () => {
    useCorpusStore.setState({
      filters: { yearRange: [2010, 2020], authors: ['Test'], source: ['Journal'], status: ['success'] },
    })
    
    render(<FiltersPanel />)
    
    // Verify initial mock state is reflected in inputs
    expect(screen.getByPlaceholderText('Min')).toHaveValue(2010)
    expect(screen.getByLabelText('Journal')).toBeChecked()
    
    const clearBtn = screen.getByRole('button', { name: 'Clear Filters' })
    await userEvent.click(clearBtn)
    
    const state = useCorpusStore.getState().filters
    expect(state.yearRange).toEqual([2000, 2026])
    expect(state.authors).toEqual([])
    expect(state.source).toEqual([])
    expect(state.status).toEqual([])
    
    // Verify inputs reset
    expect(screen.getByPlaceholderText('Min')).toHaveValue(2000)
    expect(screen.getByLabelText('Journal')).not.toBeChecked()
  })
})
