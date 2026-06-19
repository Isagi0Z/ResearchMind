import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { CorpusFilters, SortConfig, PaginationState } from '@/types/corpus'
import { StageStatus } from '@/types/enums'

interface CorpusState {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  
  filters: CorpusFilters;
  setFilters: (filters: Partial<CorpusFilters>) => void;
  clearFilters: () => void;
  
  sort: SortConfig;
  setSort: (config: SortConfig) => void;
  
  pagination: PaginationState;
  setPagination: (pagination: Partial<PaginationState>) => void;
  
  selectedRows: Record<string, boolean>;
  setSelectedRows: (rows: Record<string, boolean>) => void;
  toggleRowSelection: (id: string) => void;
  clearSelection: () => void;
}

const initialFilters: CorpusFilters = {
  yearRange: [2000, 2026],
  authors: [],
  source: [],
  status: [],
}

export const useCorpusStore = create<CorpusState>()(
  persist(
    (set) => ({
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query, pagination: { pageIndex: 0, pageSize: 1000 } }),
  
  filters: initialFilters,
  setFilters: (newFilters) => set((state) => ({ 
    filters: { ...state.filters, ...newFilters },
    pagination: { ...state.pagination, pageIndex: 0 } // Reset page on filter change
  })),
  clearFilters: () => set({ filters: initialFilters, pagination: { pageIndex: 0, pageSize: 1000 } }),
  
  sort: { column: 'year', direction: 'desc' },
  setSort: (config) => set({ sort: config }),
  
  pagination: { pageIndex: 0, pageSize: 1000 },
  setPagination: (newPagination) => set((state) => ({
    pagination: { ...state.pagination, ...newPagination }
  })),
  
  selectedRows: {},
  setSelectedRows: (rows) => set({ selectedRows: rows }),
  toggleRowSelection: (id) => set((state) => ({
    selectedRows: {
      ...state.selectedRows,
      [id]: !state.selectedRows[id]
    }
  })),
  clearSelection: () => set({ selectedRows: {} }),
}),
    {
      name: 'corpus-store',
      partialize: (state) => ({
        searchQuery: state.searchQuery,
        filters: state.filters,
        sort: state.sort,
      }),
    }
  )
)
