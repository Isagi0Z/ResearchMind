export type GraphNodeType = 'entity' | 'document' | 'theme' | 'cluster';
export type GraphEdgeType = 'USES_METHOD' | 'COMPARES_WITH' | 'SUPPORTS' | 'CONTRADICTS' | 'REFERENCES' | 'CO_OCCURS';

export interface GraphNodeData extends Record<string, unknown> {
  label: string;
  type: GraphNodeType;
  // entity specific
  confidence?: number;
  relatedDocuments?: number;
  // document specific
  title?: string;
  year?: number;
  authors?: string[];
  // cluster specific
  size?: number;
  containedEntities?: string[];
}

export interface GraphEdgeData extends Record<string, unknown> {
  type: GraphEdgeType;
  confidence?: number;
}
