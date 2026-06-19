import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { Node, Edge } from '@xyflow/react'
import { GraphNodeData, GraphEdgeData } from '@/types/graph'

interface GraphState {
  searchQuery: string
  setSearchQuery: (query: string) => void

  selectedNodeId: string | null
  setSelectedNodeId: (id: string | null) => void

  selectedEdgeId: string | null
  setSelectedEdgeId: (id: string | null) => void

  highlightedNodeIds: Set<string>
  setHighlightedNodeIds: (ids: Set<string>) => void

  nodeTypeFilter: string
  setNodeTypeFilter: (filter: string) => void

  page: number
  setPage: (page: number) => void
}

export const useGraphStore = create<GraphState>()(
  persist(
    (set) => ({
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),

  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedEdgeId: null }),

  selectedEdgeId: null,
  setSelectedEdgeId: (id) => set({ selectedEdgeId: id, selectedNodeId: null }),

  highlightedNodeIds: new Set(),
  setHighlightedNodeIds: (ids) => set({ highlightedNodeIds: ids }),

  nodeTypeFilter: '',
  setNodeTypeFilter: (filter) => set({ nodeTypeFilter: filter, page: 0 }),

  page: 0,
  setPage: (page) => set({ page }),
}),
    {
      name: 'graph-store',
      partialize: (state) => ({
        nodeTypeFilter: state.nodeTypeFilter,
      }),
    }
  )
)
