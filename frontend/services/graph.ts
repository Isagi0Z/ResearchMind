import { apiClient } from "@/lib/api-client";
import { GraphNodeData, GraphEdgeData } from "@/types/graph";
import { Node, Edge } from '@xyflow/react';

export interface GraphDataResponse {
  nodes: Node<GraphNodeData>[];
  edges: Edge<GraphEdgeData>[];
}

export async function getGraphData(): Promise<GraphDataResponse> {
  return await apiClient.get<GraphDataResponse>("/api/v1/graph");
}
