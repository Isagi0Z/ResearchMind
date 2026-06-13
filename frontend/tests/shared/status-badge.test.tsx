import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from '@/components/shared/status-badge'

describe('StatusBadge Component', () => {
  it('renders healthy status with correct classes', () => {
    render(<StatusBadge status="healthy" />)
    const badge = screen.getByText('healthy')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-emerald-50')
  })

  it('renders success status with correct classes', () => {
    render(<StatusBadge status="success" />)
    const badge = screen.getByText('success')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-emerald-50')
  })

  it('renders warning status with correct classes', () => {
    render(<StatusBadge status="warning" />)
    const badge = screen.getByText('warning')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-amber-50')
  })

  it('renders error status with correct classes', () => {
    render(<StatusBadge status="error" />)
    const badge = screen.getByText('error')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('text-destructive')
  })

  it('renders failed status with correct classes', () => {
    render(<StatusBadge status="failed" />)
    const badge = screen.getByText('failed')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('text-destructive')
  })

  it('applies custom className', () => {
    render(<StatusBadge status="healthy" className="custom-badge" />)
    const badge = screen.getByText('healthy')
    expect(badge).toHaveClass('custom-badge')
  })
})
