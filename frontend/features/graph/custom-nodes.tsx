import { Handle, Position } from '@xyflow/react';
import { GraphNodeData } from '@/types/graph';
import { cn } from '@/lib/utils';
import { FileText, Database, Layers, Network } from 'lucide-react';
import { memo } from 'react';

function NodeWrapper({
  id,
  selected,
  data,
  children,
  className,
  icon: Icon
}: {
  id: string,
  selected: boolean,
  data: GraphNodeData,
  children?: React.ReactNode,
  className: string,
  icon: any
}) {
  return (
    <div
      className={cn(
        "px-4 py-2 shadow-sm rounded-md border-2 bg-background flex items-center gap-2 transition-all duration-200",
        selected && "border-primary ring-2 ring-primary/20",
        className
      )}
      tabIndex={0}
      aria-label={`${data.type} node: ${data.label}`}
      role="button"
    >
      <Handle type="target" position={Position.Top} className="opacity-0 w-full h-full absolute inset-0 z-0 pointer-events-none" />
      <Icon className="w-4 h-4 shrink-0" />
      <div className="flex flex-col z-10">
        <span className="text-sm font-semibold truncate max-w-[150px]">{data.label}</span>
        {children}
      </div>
      <Handle type="source" position={Position.Bottom} className="opacity-0 w-full h-full absolute inset-0 z-0 pointer-events-none" />
    </div>
  );
}

export const EntityNode = memo(({ id, data, selected }: { id: string, data: GraphNodeData, selected: boolean }) => {
  return (
    <NodeWrapper id={id} selected={selected} data={data} icon={Database} className="border-blue-500/50">
      <span className="text-[10px] text-muted-foreground">{data.relatedDocuments} docs</span>
    </NodeWrapper>
  );
});
EntityNode.displayName = 'EntityNode';

export const DocumentNode = memo(({ id, data, selected }: { id: string, data: GraphNodeData, selected: boolean }) => {
  return (
    <NodeWrapper id={id} selected={selected} data={data} icon={FileText} className="border-emerald-500/50">
      <span className="text-[10px] text-muted-foreground">{data.year}</span>
    </NodeWrapper>
  );
});
DocumentNode.displayName = 'DocumentNode';

export const ThemeNode = memo(({ id, data, selected }: { id: string, data: GraphNodeData, selected: boolean }) => {
  return (
    <NodeWrapper id={id} selected={selected} data={data} icon={Layers} className="border-purple-500/50">
    </NodeWrapper>
  );
});
ThemeNode.displayName = 'ThemeNode';

export const ClusterNode = memo(({ id, data, selected }: { id: string, data: GraphNodeData, selected: boolean }) => {
  return (
    <NodeWrapper id={id} selected={selected} data={data} icon={Network} className="border-amber-500 bg-amber-500/10">
      <div className="absolute -top-2 -right-2 bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
        {data.size}
      </div>
    </NodeWrapper>
  );
});
ClusterNode.displayName = 'ClusterNode';
