import { create } from 'zustand'

export type TimeRangeFilter = '1h' | '24h' | '7d' | '30d'

interface MonitoringState {
  timeRange: TimeRangeFilter
  setTimeRange: (range: TimeRangeFilter) => void
  
  selectedModuleId: string | null
  setSelectedModuleId: (id: string | null) => void
  
  queueFilter: 'all' | 'active' | 'pending' | 'completed' | 'failed'
  setQueueFilter: (filter: 'all' | 'active' | 'pending' | 'completed' | 'failed') => void
}

export const useMonitoringStore = create<MonitoringState>((set) => ({
  timeRange: '24h',
  setTimeRange: (range) => set({ timeRange: range }),
  
  selectedModuleId: null,
  setSelectedModuleId: (id) => set({ selectedModuleId: id }),
  
  queueFilter: 'all',
  setQueueFilter: (filter) => set({ queueFilter: filter })
}))
