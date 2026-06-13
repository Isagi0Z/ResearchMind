import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingState } from '@/components/shared/loading-state'

describe('LoadingState Component', () => {
  it('renders loading text for screen readers', () => {
    render(<LoadingState />)
    
    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.getByText('Loading...')).toHaveClass('sr-only')
  })

  it('applies custom className', () => {
    const { container } = render(<LoadingState className="custom-loading-class" />)
    
    expect(container.firstChild).toHaveClass('custom-loading-class')
  })
})
