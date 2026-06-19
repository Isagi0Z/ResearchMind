import { apiClient } from "@/lib/api-client";
import { GraphNodeData, GraphEdgeData } from "@/types/graph";
import { Node, Edge } from '@xyflow/react';

export interface GraphDataResponse {
  nodes: Node<GraphNodeData>[];
  edges: Edge<GraphEdgeData>[];
}

export interface GraphQueryParams {
  nodeType?: string;
  search?: string;
  offset?: number;
  limit?: number;
}

export async function getGraphData(params?: GraphQueryParams): Promise<GraphDataResponse> {
  const query = new URLSearchParams();
  if (params?.nodeType) query.set('nodeType', params.nodeType);
  if (params?.search) query.set('search', params.search);
  if (params?.offset !== undefined) query.set('offset', String(params.offset));
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  const qs = query.toString();
  return await apiClient.get<GraphDataResponse>(`/api/v1/graph${qs ? '?' + qs : ''}`);
}

export async function getGraphNode(id: string): Promise<GraphNodeData> {
  return await apiClient.get<GraphNodeData>(`/api/v1/graph/node/${id}`);
}
