/**
 * LiteratureReviewViewer — Renders a synthesised literature review with
 * clickable inline citations [1] [2] that reveal paper info in a popover.
 */

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Copy, Download, BookOpen, X, ExternalLink, Clock, AlignLeft } from 'lucide-react';
import { toast } from 'sonner';
import { TierBadge } from './TierBadge';
import { useNavigate } from 'react-router';
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
  const navigate = useNavigate();
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
        bottom: '24px', right: '24px',
        width: '340px',
        zIndex: 200,
        borderRadius: '16px',
        background: 'rgba(10,12,28,0.97)',
        border: '1px solid rgba(124,58,237,0.35)',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 32px rgba(124,58,237,0.1)',
        backdropFilter: 'blur(24px)',
        padding: '18px',
        overflow: 'hidden',
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
        <TierBadge tier={paper.tier} size="sm" />
      </div>

      <div style={{ display: 'flex', gap: '8px' }}>
        {paper.doi && (
          <button
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
          </button>
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
            <ExternalLink size={13} />
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

  const wordCount = useMemo(() => reviewText.trim().split(/\s+/).length, [reviewText]);
  const readingMins = Math.max(1, Math.ceil(wordCount / 200));
  const segments = useMemo(() => parseReviewText(reviewText), [reviewText]);

  const copyReview = () => {
    navigator.clipboard.writeText(reviewText).then(() => toast.success('Review copied to clipboard'));
  };

  return (
    <div style={{ position: 'relative' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '16px', flexWrap: 'wrap', gap: '10px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlignLeft size={13} color="rgba(255,255,255,0.3)" />
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
              {wordCount.toLocaleString()} words
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Clock size={13} color="rgba(255,255,255,0.3)" />
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
              ~{readingMins} min read
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <BookOpen size={13} color="rgba(255,255,255,0.3)" />
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
              {citedPapers.length} sources
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={copyReview}
            style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              padding: '6px 12px', borderRadius: '8px',
              fontSize: '12px', fontWeight: 500,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)',
              color: 'rgba(255,255,255,0.45)', cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.45)';
            }}
          >
            <Copy size={12} /> Copy
          </button>
          <button
            onClick={() => {
              const blob = new Blob([reviewText], { type: 'text/plain' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url; a.download = 'literature-review.txt'; a.click();
              URL.revokeObjectURL(url);
            }}
            style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              padding: '6px 12px', borderRadius: '8px',
              fontSize: '12px', fontWeight: 500,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)',
              color: 'rgba(255,255,255,0.45)', cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.45)';
            }}
          >
            <Download size={12} /> Export
          </button>
        </div>
      </div>

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

      {/* Cited papers list */}
      {citedPapers.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <p style={{
            fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
            color: 'rgba(255,255,255,0.25)', marginBottom: '10px',
          }}>
            {citedPapers.length} References
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {citedPapers.map((p, i) => {
              const score = p.score ?? p.composite_score ?? 0;
              const scoreColor = score >= 70 ? '#00e676' : score >= 45 ? '#ffd166' : '#ff4757';
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25, delay: i * 0.04 }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '12px',
                    padding: '10px 14px', borderRadius: '10px',
                    background: activeRef === i + 1 ? 'rgba(124,58,237,0.08)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${activeRef === i + 1 ? 'rgba(124,58,237,0.25)' : 'rgba(255,255,255,0.05)'}`,
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                  onClick={() => setActiveRef(activeRef === i + 1 ? null : i + 1)}
                >
                  <span style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '11px', color: 'rgba(255,255,255,0.2)', minWidth: '24px',
                  }}>
                    [{i + 1}]
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{
                      fontSize: '12px', color: 'rgba(255,255,255,0.75)',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0,
                    }}>
                      {p.title}
                    </p>
                    <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.28)', margin: 0, fontStyle: 'italic' }}>
                      {p.venue}{p.year ? `, ${p.year}` : ''}
                    </p>
                  </div>
                  <span style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '12px', fontWeight: 700, color: scoreColor, flexShrink: 0,
                  }}>
                    {score}
                  </span>
                  <TierBadge tier={p.tier} size="sm" />
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

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
