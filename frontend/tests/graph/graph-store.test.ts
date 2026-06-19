import { describe, it, expect } from 'vitest'
import { useGraphStore } from '@/features/graph/graph-store'

describe('graphStore', () => {
  it('starts with default values', () => {
    const state = useGraphStore.getState()
    expect(state.searchQuery).toBe('')
    expect(state.selectedNodeId).toBeNull()
    expect(state.selectedEdgeId).toBeNull()
    expect(state.highlightedNodeIds.size).toBe(0)
    expect(state.nodeTypeFilter).toBe('')
    expect(state.page).toBe(0)
  })

  it('sets search query', () => {
    useGraphStore.getState().setSearchQuery('neural')
    expect(useGraphStore.getState().searchQuery).toBe('neural')
    useGraphStore.getState().setSearchQuery('')
  })

  it('sets selected node id and clears edge', () => {
    useGraphStore.getState().setSelectedEdgeId('edge-1')
    useGraphStore.getState().setSelectedNodeId('node-1')
    expect(useGraphStore.getState().selectedNodeId).toBe('node-1')
    expect(useGraphStore.getState().selectedEdgeId).toBeNull()
  })

  it('sets selected edge id and clears node', () => {
    useGraphStore.getState().setSelectedNodeId('node-1')
    useGraphStore.getState().setSelectedEdgeId('edge-1')
    expect(useGraphStore.getState().selectedEdgeId).toBe('edge-1')
    expect(useGraphStore.getState().selectedNodeId).toBeNull()
  })

  it('sets highlighted node ids', () => {
    const ids = new Set(['doc-0', 'doc-1'])
    useGraphStore.getState().setHighlightedNodeIds(ids)
    expect(useGraphStore.getState().highlightedNodeIds).toEqual(ids)
    useGraphStore.getState().setHighlightedNodeIds(new Set())
  })

  it('sets node type filter and resets page', () => {
    useGraphStore.getState().setPage(3)
    useGraphStore.getState().setNodeTypeFilter('document')
    expect(useGraphStore.getState().nodeTypeFilter).toBe('document')
    expect(useGraphStore.getState().page).toBe(0)
  })

  it('sets page', () => {
    useGraphStore.getState().setPage(2)
    expect(useGraphStore.getState().page).toBe(2)
    useGraphStore.getState().setPage(0)
  })
})
