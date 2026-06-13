import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from '@/components/shared/empty-state'

describe('EmptyState Component', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No items found" description="Try adjusting your search criteria." />)
    
    expect(screen.getByText('No items found')).toBeInTheDocument()
    expect(screen.getByText('Try adjusting your search criteria.')).toBeInTheDocument()
  })

  it('renders with an icon if provided', () => {
    render(
      <EmptyState 
        title="No items found" 
        description="Try adjusting your search criteria." 
        icon={<div data-testid="test-icon">Icon</div>} 
      />
    )
    
    expect(screen.getByTestId('test-icon')).toBeInTheDocument()
  })

  it('renders with an action element if provided', () => {
    render(
      <EmptyState 
        title="No items found" 
        description="Try adjusting your search criteria." 
        action={<button>Create new</button>} 
      />
    )
    
    expect(screen.getByRole('button', { name: 'Create new' })).toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(
      <EmptyState 
        title="No items" 
        description="Desc" 
        className="custom-empty-class"
      />
    )
    
    expect(container.firstChild).toHaveClass('custom-empty-class')
  })
})
