import { create } from 'zustand'
import { ParsedQuery, ExecutionState, ResearchAnswer } from '@/types/query'

interface QueryState {
  // Input
  activeQueryText: string
  setActiveQueryText: (text: string) => void
  
  // Execution
  executionState: ExecutionState
  setExecutionState: (state: ExecutionState) => void
  
  // Results
  currentAnswer: ResearchAnswer | null
  setCurrentAnswer: (answer: ResearchAnswer | null) => void
  
  // History
  queryHistory: ParsedQuery[]
  addToHistory: (query: ParsedQuery) => void
  
  // Selections
  selectedEvidenceId: string | null
  setSelectedEvidenceId: (id: string | null) => void
  
  selectedReasoningStepId: string | null
  setSelectedReasoningStepId: (id: string | null) => void
}

export const useQueryStore = create<QueryState>((set) => ({
  activeQueryText: '',
  setActiveQueryText: (text) => set({ activeQueryText: text }),
  
  executionState: 'idle',
  setExecutionState: (state) => set({ executionState: state }),
  
  currentAnswer: null,
  setCurrentAnswer: (answer) => set({ currentAnswer: answer }),
  
  queryHistory: [],
  addToHistory: (query) => set((state) => ({ 
    queryHistory: [query, ...state.queryHistory.filter(q => q.id !== query.id)].slice(0, 50) 
  })),
  
  selectedEvidenceId: null,
  setSelectedEvidenceId: (id) => set({ selectedEvidenceId: id }),
  
  selectedReasoningStepId: null,
  setSelectedReasoningStepId: (id) => set({ selectedReasoningStepId: id }),
}))
