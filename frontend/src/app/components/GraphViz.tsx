/**
 * Force-directed graph visualization for the trusted literature knowledge graph.
 * Uses react-force-graph-2d (D3-based, no WebGL required).
 */

import { useCallback, useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { GraphNode, GraphEdge } from '../../api/client';

interface GraphVizProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedDois?: string[];
  onNodeClick?: (node: GraphNode) => void;
  width?: number;
  height?: number;
}

// Tier → color mapping
const TIER_COLOR: Record<string, string> = {
  Trusted: '#00e676',
  Caution: '#ffd166',
  Untrusted: '#ff4757',
};

const EDGE_COLOR: Record<string, string> = {
  CITES: 'rgba(77,136,255,0.55)',
  SHARES_TOPIC: 'rgba(255,255,255,0.15)',
};

export function GraphViz({
  nodes,
  edges,
  highlightedDois = [],
  onNodeClick,
  width = 600,
  height = 480,
}: GraphVizProps) {
  const fgRef = useRef<any>(null);

  // Fit graph to view when data changes
  useEffect(() => {
    if (fgRef.current && nodes.length > 0) {
      setTimeout(() => fgRef.current?.zoomToFit(400, 48), 300);
    }
  }, [nodes.length]);

  const graphData = {
    nodes: nodes.map(n => ({
      ...n,
      // react-force-graph needs these
      id: n.id,
      name: n.title,
      val: n.val || Math.max(4, Math.round(n.score / 15)),
    })),
    links: edges.map(e => ({
      source: e.source,
      target: e.target,
      type: e.type,
    })),
  };

  const nodeCanvasObject = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isHighlighted = highlightedDois.includes(node.id);
      const color = TIER_COLOR[node.tier as string] || '#aaa';
      const r = node.val || 5;

      // Glow for highlighted
      if (isHighlighted) {
        ctx.shadowBlur = 18;
        ctx.shadowColor = color;
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
      ctx.fillStyle = isHighlighted ? color : color + '99';
      ctx.fill();

      // Ring
      ctx.strokeStyle = color;
      ctx.lineWidth = isHighlighted ? 2 : 1;
      ctx.stroke();

      ctx.shadowBlur = 0;

      // Label (only when zoomed in enough)
      if (globalScale >= 1.4 || isHighlighted) {
        const label =
          node.name.length > 30 ? node.name.slice(0, 28) + '…' : node.name;
        const fontSize = Math.max(10 / globalScale, 3);
        ctx.font = `${fontSize}px Inter, sans-serif`;
        ctx.fillStyle = 'rgba(255,255,255,0.82)';
        ctx.textAlign = 'center';
        ctx.fillText(label, node.x, node.y + r + fontSize + 1);
      }
    },
    [highlightedDois]
  );

  const linkColor = useCallback(
    (link: any) => EDGE_COLOR[link.type as string] || 'rgba(255,255,255,0.12)',
    []
  );

  const linkDirectionalArrowLength = useCallback(
    (link: any) => (link.type === 'CITES' ? 4 : 0),
    []
  );

  if (nodes.length === 0) {
    return (
      <div
        style={{
          width,
          height,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(255,255,255,0.015)',
          borderRadius: '16px',
          border: '1px dashed rgba(255,255,255,0.08)',
          gap: '12px',
        }}
      >
        <div style={{ fontSize: '32px', opacity: 0.2 }}>🕸</div>
        <p style={{ color: 'rgba(255,255,255,0.28)', fontSize: '13px', textAlign: 'center', maxWidth: '220px' }}>
          Add papers to build your<br />trusted knowledge graph
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        borderRadius: '16px',
        overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.07)',
        background: 'rgba(6,8,15,0.85)',
      }}
    >
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        backgroundColor="transparent"
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        linkColor={linkColor}
        linkDirectionalArrowLength={linkDirectionalArrowLength}
        linkDirectionalArrowRelPos={1}
        linkWidth={1}
        onNodeClick={(node: any) => onNodeClick?.(node as GraphNode)}
        cooldownTicks={80}
        enableNodeDrag={true}
        enableZoomInteraction={true}
      />
    </div>
  );
}
