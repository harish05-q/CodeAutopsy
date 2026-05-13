"use client";

import React, { useCallback, useEffect, useMemo } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Panel,
  Edge,
  Node
} from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';
import { GraphData } from '@/lib/api';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 200;
const nodeHeight = 50;

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes as Node[], edges };
};

interface GraphViewerProps {
  graphData: GraphData;
  title: string;
}

export default function GraphViewer({ graphData, title }: GraphViewerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (!graphData) return;

    const initialNodes: Node[] = graphData.nodes.map((node) => ({
      id: node.id,
      data: { label: node.label },
      position: { x: 0, y: 0 },
      type: 'default',
      style: {
        background: node.type === 'module' ? '#3b82f6' : '#10b981',
        color: 'white',
        border: 'none',
        borderRadius: '8px',
        padding: '10px',
        fontWeight: 'bold',
        fontSize: '12px',
        wordWrap: 'break-word',
        boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
      },
    }));

    const initialEdges: Edge[] = graphData.edges.map((edge, i) => ({
      id: `e${i}-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: edge.relationship,
      animated: edge.relationship === 'calls',
      style: { stroke: '#9ca3af', strokeWidth: 2 },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#9ca3af',
      },
      labelStyle: { fill: '#6b7280', fontWeight: 'bold' },
      labelBgStyle: { fill: 'white', opacity: 0.8 },
    }));

    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      initialNodes,
      initialEdges,
      graphData.graph_type === 'dependency' ? 'TB' : 'LR'
    );

    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [graphData, setNodes, setEdges]);

  return (
    <div className="w-full h-[600px] border border-gray-200 rounded-xl bg-gray-50 overflow-hidden relative shadow-inner">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        attributionPosition="bottom-right"
      >
        <Panel position="top-left" className="bg-white p-3 rounded-lg shadow-md border border-gray-100">
          <h3 className="font-bold text-gray-800">{title}</h3>
          <p className="text-xs text-gray-500 mt-1">
            {graphData.nodes.length} Nodes • {graphData.edges.length} Edges
          </p>
        </Panel>
        <Controls />
        <MiniMap zoomable pannable nodeColor={(n) => {
            return n.style?.background as string || '#ccc';
        }}/>
        <Background color="#aaa" gap={16} />
      </ReactFlow>
    </div>
  );
}
