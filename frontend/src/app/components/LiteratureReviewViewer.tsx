/**
 * LiteratureReviewViewer — Renders a synthesised literature review with
 * clickable inline citations [1] [2] that reveal paper info in a popover.
 */

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X } from 'lucide-react';
import { TierBadge } from './TierBadge';
import type { Paper } from '../../api/client';

interface LiteratureReviewViewerProps {
  reviewText: string;
  citedPapers: Paper[];
}

interface CitationPopoverProps {
  paper: Paper;
  index: number;
  onClose: () => void;
}

function CitationPopover({ paper, index, onClose }: CitationPopoverProps) {
  const score = paper.score ?? paper.composite_score ?? 0;
  const scoreColor = score >= 70 ? '#00e676' : score >= 45 ? '#ffd166' : '#ff4757';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.96 }}
      transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
      style={{
        position: 'fixed',
        bottom: '32px',
        right: '32px',
        width: '360px',
        maxHeight: '85vh',
        zIndex: 200,
        borderRadius: '16px',
        background: 'rgba(10,12,28,0.98)',
        border: '1px solid rgba(124,58,237,0.35)',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 32px rgba(124,58,237,0.1)',
        backdropFilter: 'blur(24px)',
        padding: '18px',
        overflow: 'auto',
      }}
    >
      {/* Accent line */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: 'linear-gradient(90deg, #7c3aed, #06b6d4)' }} />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px', fontWeight: 700,
          padding: '2px 8px', borderRadius: '5px',
          background: 'rgba(124,58,237,0.15)',
          border: '1px solid rgba(124,58,237,0.35)',
          color: '#a78bfa',
        }}>
          REF [{index}]
        </span>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.3)', padding: '2px' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
        >
          <X size={14} />
        </button>
      </div>

      <p style={{
        fontSize: '13px', fontWeight: 500,
        color: 'rgba(255,255,255,0.9)',
        lineHeight: 1.45, marginBottom: '10px',
        display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      }}>
        {paper.title}
      </p>

      <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)', fontStyle: 'italic', marginBottom: '12px' }}>
        {paper.venue}{paper.year ? `, ${paper.year}` : ''}
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '20px', fontWeight: 700, color: scoreColor,
        }}>
          {score}<span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.25)', fontWeight: 400 }}>/100</span>
        </span>
        <TierBadge tier={paper.tier as any} size="sm" />
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {paper.doi && (
          <>
            {/* <button
              onClick={() => { onClose(); navigate(`/paper?doi=${encodeURIComponent(paper.doi!)}&from=review`); }}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px',
                padding: '7px 12px', borderRadius: '8px', fontSize: '12px', fontWeight: 500,
                background: 'rgba(124,58,237,0.15)', border: '1px solid rgba(124,58,237,0.35)',
                color: '#a78bfa', cursor: 'pointer', transition: 'all 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(124,58,237,0.25)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(124,58,237,0.15)')}
            >
              View Paper
            </button> */}
            <button
              onClick={() => { onClose(); window.open(`/paper?doi=${encodeURIComponent(paper.doi!)}&from=review`, '_blank'); }}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px',
                padding: '7px 12px', borderRadius: '8px', fontSize: '12px', fontWeight: 500,
                background: 'rgba(6,182,212,0.15)', border: '1px solid rgba(6,182,212,0.35)',
                color: '#06b6d4', cursor: 'pointer', transition: 'all 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(6,182,212,0.25)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(6,182,212,0.15)')}
              title="Open in new tab"
            >
              View Paper
            </button>
          </>
        )}
        {paper.doi && (
          <a
            href={`https://doi.org/${paper.doi}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex', alignItems: 'center', padding: '7px 10px',
              borderRadius: '8px', background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.3)',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.7)';
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.3)';
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
            }}
          >
            DOI
          </a>
        )}
      </div>
    </motion.div>
  );
}

/** Parse text and split on [N] citation markers */
function parseReviewText(text: string): Array<{ type: 'text' | 'cite'; content: string; index?: number }> {
  const parts: Array<{ type: 'text' | 'cite'; content: string; index?: number }> = [];
  const regex = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    parts.push({ type: 'cite', content: match[0], index: parseInt(match[1]) });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push({ type: 'text', content: text.slice(lastIndex) });
  return parts;
}

export function LiteratureReviewViewer({ reviewText, citedPapers }: LiteratureReviewViewerProps) {
  const [activeRef, setActiveRef] = useState<number | null>(null);
  const activePaper = activeRef != null ? citedPapers[activeRef - 1] : null;

  const segments = useMemo(() => parseReviewText(reviewText), [reviewText]);

  return (
    <div style={{ position: 'relative' }}>

      {/* Review body */}
      <div style={{
        background: 'rgba(255,255,255,0.02)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: '14px',
        padding: '28px 32px',
        lineHeight: 1.85,
        fontSize: '14px',
        color: 'rgba(255,255,255,0.8)',
        fontFamily: "'Inter', sans-serif",
        maxHeight: '520px', overflowY: 'auto',
      }}>
        {segments.map((seg, i) =>
          seg.type === 'text' ? (
            <span key={i}>{seg.content}</span>
          ) : (
            <button
              key={i}
              onClick={() => setActiveRef(activeRef === seg.index ? null : seg.index!)}
              style={{
                display: 'inline-flex', alignItems: 'center',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px', fontWeight: 700,
                padding: '1px 5px', borderRadius: '4px',
                background: activeRef === seg.index ? 'rgba(124,58,237,0.25)' : 'rgba(124,58,237,0.12)',
                border: `1px solid ${activeRef === seg.index ? 'rgba(124,58,237,0.5)' : 'rgba(124,58,237,0.28)'}`,
                color: '#a78bfa',
                cursor: 'pointer', transition: 'all 0.15s',
                verticalAlign: 'super',
                margin: '0 1px',
              }}
            >
              {seg.content}
            </button>
          )
        )}
      </div>



      {/* Citation popover */}
      <AnimatePresence>
        {activePaper && activeRef != null && (
          <CitationPopover
            paper={activePaper}
            index={activeRef}
            onClose={() => setActiveRef(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
