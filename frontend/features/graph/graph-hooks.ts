import { useQuery } from '@tanstack/react-query'
import { getGraphData, getGraphNode, GraphQueryParams } from '@/services/graph'

export function useGraphData(params?: GraphQueryParams) {
  return useQuery({
    queryKey: ['graphData', params],
    queryFn: async () => {
      return await getGraphData(params)
    },
    staleTime: 60000,
  })
}

export function useGraphNode(id: string | null) {
  return useQuery({
    queryKey: ['graphNode', id],
    queryFn: async () => {
      if (!id) throw new Error('No node id')
      return await getGraphNode(id)
    },
    enabled: !!id,
    staleTime: 60000,
  })
}
