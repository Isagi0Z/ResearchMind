import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ErrorState } from '@/components/shared/error-state'

describe('ErrorState Component', () => {
  it('renders default title and description', () => {
    render(<ErrorState />)
    
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('There was a problem loading this content. Please try again.')).toBeInTheDocument()
  })

  it('renders custom title and description', () => {
    render(<ErrorState title="Custom Error" description="Custom Description" />)
    
    expect(screen.getByText('Custom Error')).toBeInTheDocument()
    expect(screen.getByText('Custom Description')).toBeInTheDocument()
  })

  it('does not render retry button if onRetry is not provided', () => {
    render(<ErrorState />)
    
    expect(screen.queryByRole('button', { name: 'Try Again' })).not.toBeInTheDocument()
  })

  it('renders retry button if onRetry is provided and handles click', async () => {
    const onRetryMock = vi.fn()
    render(<ErrorState onRetry={onRetryMock} />)
    
    const retryButton = screen.getByRole('button', { name: 'Try Again' })
    expect(retryButton).toBeInTheDocument()
    
    await userEvent.click(retryButton)
    expect(onRetryMock).toHaveBeenCalledTimes(1)
  })
})
