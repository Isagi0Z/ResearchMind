import { BaseEdge, EdgeProps, Edge, getBezierPath } from '@xyflow/react';
import { GraphEdgeData } from '@/types/graph';
import { memo } from 'react';

const EDGE_COLORS: Record<string, string> = {
  USES_METHOD: '#3b82f6', // blue
  COMPARES_WITH: '#8b5cf6', // purple
  SUPPORTS: '#10b981', // emerald
  CONTRADICTS: '#ef4444', // red
  REFERENCES: '#6b7280', // gray
  CO_OCCURS: '#f59e0b', // amber
};

export const CustomEdge = memo(({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  selected,
}: EdgeProps<Edge<GraphEdgeData, 'customEdge'>>) => {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const edgeType = data?.type || 'REFERENCES';
  const color = EDGE_COLORS[edgeType];

  return (
    <>
      <BaseEdge 
        path={edgePath} 
        markerEnd={markerEnd} 
        style={{
          stroke: color,
          strokeWidth: selected ? 3 : 1.5,
          opacity: selected ? 1 : 0.6,
          transition: 'all 0.2s',
        }} 
      />
      {selected && data?.confidence && (
        <text>
          <textPath href={`#${id}`} startOffset="50%" textAnchor="middle" className="text-[10px] fill-current opacity-70">
            {edgeType} ({data.confidence})
          </textPath>
        </text>
      )}
    </>
  );
});
CustomEdge.displayName = 'CustomEdge';
