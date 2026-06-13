import { create } from 'zustand'
import { Node, Edge } from '@xyflow/react'
import { GraphNodeData, GraphEdgeData } from '@/types/graph'

interface GraphState {
  searchQuery: string
  setSearchQuery: (query: string) => void
  
  selectedNodeId: string | null
  setSelectedNodeId: (id: string | null) => void
  
  selectedEdgeId: string | null
  setSelectedEdgeId: (id: string | null) => void
  
  // To track highlighted nodes from search
  highlightedNodeIds: Set<string>
  setHighlightedNodeIds: (ids: Set<string>) => void
}

export const useGraphStore = create<GraphState>((set) => ({
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),
  
  selectedNodeId: null,
  setSelectedNodeId: (id) => set({ selectedNodeId: id, selectedEdgeId: null }),
  
  selectedEdgeId: null,
  setSelectedEdgeId: (id) => set({ selectedEdgeId: id, selectedNodeId: null }),
  
  highlightedNodeIds: new Set(),
  setHighlightedNodeIds: (ids) => set({ highlightedNodeIds: ids }),
}))
