import { useQuery } from '@tanstack/react-query'
import { getMonitoringData } from '@/services/monitoring'
import { useMonitoringStore } from './monitoring-store'

export function useMonitoringData() {
  const { timeRange } = useMonitoringStore()

  return useQuery({
    queryKey: ['monitoring', timeRange],
    queryFn: async () => {
      const result = await getMonitoringData(timeRange)
      return result
    },
    refetchInterval: 10000,
    retry: false,
  })
}
