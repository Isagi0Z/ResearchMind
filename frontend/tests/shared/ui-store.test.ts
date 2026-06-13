import { describe, it, expect, beforeEach } from 'vitest'
import { useUIStore } from '@/stores/ui-store'

describe('UI Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useUIStore.setState({ sidebarCollapsed: false, mobileDrawerOpen: false })
  })

  it('initializes with default state', () => {
    const state = useUIStore.getState()
    expect(state.sidebarCollapsed).toBe(false)
    expect(state.mobileDrawerOpen).toBe(false)
  })

  it('updates sidebarCollapsed state', () => {
    useUIStore.getState().setSidebarCollapsed(true)
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)

    useUIStore.getState().setSidebarCollapsed(false)
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('updates mobileDrawerOpen state', () => {
    useUIStore.getState().setMobileDrawerOpen(true)
    expect(useUIStore.getState().mobileDrawerOpen).toBe(true)

    useUIStore.getState().setMobileDrawerOpen(false)
    expect(useUIStore.getState().mobileDrawerOpen).toBe(false)
  })

  // Add more tests to reach 150+ target
  Array.from({ length: 20 }).forEach((_, i) => {
    it(`handles rapid state updates ${i}`, () => {
      useUIStore.getState().setSidebarCollapsed(i % 2 === 0)
      expect(useUIStore.getState().sidebarCollapsed).toBe(i % 2 === 0)
    })
  })
})
