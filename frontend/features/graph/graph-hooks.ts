import { useQuery } from '@tanstack/react-query'
import { getGraphData } from '@/services/graph'

export function useGraphData() {
  return useQuery({
    queryKey: ['graphData'],
    queryFn: async () => {
      return await getGraphData()
    },
    staleTime: 60000,
  })
}
