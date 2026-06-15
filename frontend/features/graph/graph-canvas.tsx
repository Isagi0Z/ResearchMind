"use client"

import { useMemo, useCallback } from 'react'
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, BackgroundVariant, NodeTypes, EdgeTypes } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { EntityNode, DocumentNode, ThemeNode, ClusterNode } from './custom-nodes'
import { CustomEdge } from './custom-edges'
import { useGraphStore } from './graph-store'

import { GraphDataResponse } from '@/services/graph'

const nodeTypes: NodeTypes = {
  entity: EntityNode,
  document: DocumentNode,
  theme: ThemeNode,
  cluster: ClusterNode,
};

const edgeTypes: EdgeTypes = {
  customEdge: CustomEdge,
};

export function GraphCanvas({ data }: { data: GraphDataResponse }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(data.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(data.edges)
  
  const { setSelectedNodeId, setSelectedEdgeId } = useGraphStore()

  const onNodeClick = useCallback((_: any, node: any) => {
    setSelectedNodeId(node.id)
  }, [setSelectedNodeId])

  const onEdgeClick = useCallback((_: any, edge: any) => {
    setSelectedEdgeId(edge.id)
  }, [setSelectedEdgeId])

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null)
    setSelectedEdgeId(null)
  }, [setSelectedNodeId, setSelectedEdgeId])

  return (
    <div className="w-full h-full relative" role="region" aria-label="Graph visualization canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        fitView
        minZoom={0.1}
        maxZoom={4}
        nodesConnectable={false}
        nodesDraggable={false} // Deterministic read-only graph
        elementsSelectable={true}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        <Controls showInteractive={false} />
        <MiniMap 
          zoomable 
          pannable 
          nodeColor={(n) => {
            if (n.type === 'entity') return '#3b82f6'
            if (n.type === 'document') return '#10b981'
            if (n.type === 'cluster') return '#f59e0b'
            return '#8b5cf6'
          }}
        />
      </ReactFlow>
    </div>
  )
}
