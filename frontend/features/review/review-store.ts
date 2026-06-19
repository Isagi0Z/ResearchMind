import { create } from 'zustand'
import { ReviewRequest, ReviewResult, GenerationStage } from '@/types/review'

interface ReviewState {
  // Configuration
  reviewConfig: Partial<ReviewRequest>
  setReviewConfig: (config: Partial<ReviewRequest>) => void
  
  // Generation
  generationStage: GenerationStage
  setGenerationStage: (stage: GenerationStage) => void
  
  // Viewer
  activeReview: ReviewResult | null
  setActiveReview: (review: ReviewResult | null) => void
  
  // Selection/Traceability
  selectedFindingId: string | null
  setSelectedFindingId: (id: string | null) => void
  
  selectedSectionId: string | null
  setSelectedSectionId: (id: string | null) => void

  // Async job tracking
  jobId: string | null
  setJobId: (id: string | null) => void
}

export const useReviewStore = create<ReviewState>((set) => ({
  reviewConfig: {
    topic: '',
    type: 'GENERAL',
    documentScope: 'all',
    targetEntities: []
  },
  setReviewConfig: (config) => set((state) => ({ reviewConfig: { ...state.reviewConfig, ...config } })),
  
  generationStage: 'idle',
  setGenerationStage: (stage) => set({ generationStage: stage }),
  
  activeReview: null,
  setActiveReview: (review) => set({ activeReview: review }),
  
  selectedFindingId: null,
  setSelectedFindingId: (id) => set({ selectedFindingId: id }),
  
  selectedSectionId: null,
  setSelectedSectionId: (id) => set({ selectedSectionId: id }),

  jobId: null,
  setJobId: (id) => set({ jobId: id })
}))
