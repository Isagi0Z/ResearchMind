import { useQuery } from '@tanstack/react-query'
import { getMonitoringData } from '@/services/monitoring'
import { useMonitoringStore } from './monitoring-store'

export function useMonitoringData() {
  const { timeRange } = useMonitoringStore()

  return useQuery({
    queryKey: ['monitoring', timeRange],
    queryFn: async () => {
      return await getMonitoringData(timeRange)
    },
    refetchInterval: 10000 // Poll every 10s for real-time feel
  })
}
