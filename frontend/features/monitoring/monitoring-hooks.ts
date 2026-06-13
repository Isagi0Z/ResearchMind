import { useQuery } from '@tanstack/react-query'
import { generateMockMonitoring } from '@/services/mock-monitoring'
import { useMonitoringStore } from './monitoring-store'

export function useMonitoringData() {
  const { timeRange } = useMonitoringStore()

  return useQuery({
    queryKey: ['monitoring', timeRange],
    queryFn: async () => {
      // Simulate network delay
      await new Promise(r => setTimeout(r, 600))
      return generateMockMonitoring(timeRange)
    },
    refetchInterval: 10000 // Poll every 10s for real-time feel
  })
}
