/**
 * StructuredReportDisplay — Renders the per-dimension credibility breakdown
 * returned by the scoring agent LLM. Shows verdict, dimension bars with
 * rationale, key concerns, positive signals, and a recommendation.
 */

import { useState } from 'react';
import { motion } from 'motion/react';
import {
  AlertTriangle, CheckCircle2, Lightbulb,
  ChevronDown, ChevronUp, ShieldCheck,
} from 'lucide-react';
import type { StructuredReport } from '../../api/client';

interface StructuredReportDisplayProps {
  report: StructuredReport;
}

const DIMENSION_COLORS: Record<string, string> = {
  statistical_integrity: '#06b6d4',
  reproducibility:       '#7c3aed',
  methodology:           '#4d88ff',
  citation_network:      '#a78bfa',
  publication_metadata:  '#ffd166',
};

function getBarColor(dim: string, score: number) {
  return DIMENSION_COLORS[dim] ?? (score >= 70 ? '#00e676' : score >= 45 ? '#ffd166' : '#ff4757');
}

/** Detect raw LLM prompt text that leaked into structured report fields */
const GARBAGE_MARKERS = [
  'Must not use markdown',
  'We must not',
  'no asterisks',
  'score_breakdown',
  'One sentence only',
  'So we need to',
  'SCORE BREAKDOWN',
  'RECOMMENDATION',
  'POSITIVE SIGNALS',
  'KEY CONCERNS',
  'DimensionName',
];

function isGarbage(text: string): boolean {
  if (!text) return false;
  if (text.length > 300) return true;
  return GARBAGE_MARKERS.some(m => text.includes(m));
}

function cleanStrings(arr: string[]): string[] {
  return arr.filter(s => s && !isGarbage(s));
}

export function StructuredReportDisplay({ report }: StructuredReportDisplayProps) {
  const [expandedDim, setExpandedDim] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);

  const dims = report.score_breakdown ?? [];
  const concerns = cleanStrings(report.key_concerns ?? []);
  const signals  = cleanStrings(report.positive_signals ?? []);
  const verdict      = isGarbage(report.overall_verdict ?? '')  ? null : report.overall_verdict;
  const recommendation = isGarbage(report.recommendation ?? '') ? null : report.recommendation;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

      {/* Overall Verdict — only show if not garbage */}
      {verdict && (
        <div style={{
          padding: '16px 18px',
          borderRadius: '12px',
          background: 'rgba(77,136,255,0.06)',
          border: '1px solid rgba(77,136,255,0.18)',
          borderLeft: '3px solid #4d88ff',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <ShieldCheck size={14} color="#4d88ff" />
            <span style={{
              fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
              color: '#4d88ff',
            }}>
              Overall Verdict
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.82)', lineHeight: 1.6, margin: 0 }}>
            {verdict}
          </p>
        </div>
      )}

      {/* Dimension Bars */}
      {dims.length > 0 && (
        <div style={{
          padding: '16px 18px',
          borderRadius: '12px',
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.07)',
        }}>
          <p style={{
            fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
            color: 'rgba(255,255,255,0.25)', marginBottom: '14px',
          }}>
            Score Breakdown
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {(showAll ? dims : dims.slice(0, 5)).map((dim, i) => {
              // Backend sends score_pct (0-100 int) OR score (0.0-1.0 float)
              const rawScore = (dim as any).score_pct ?? dim.score ?? 0;
              const score = Math.round(rawScore > 1 ? rawScore : rawScore * 100);
              const color = getBarColor(dim.dimension, score);
              const isOpen = expandedDim === i;
              return (
                <div key={i}>
                  <div
                    style={{ cursor: ((dim as any).rationale ?? dim.reason) ? 'pointer' : 'default' }}
                    onClick={() => ((dim as any).rationale ?? dim.reason) && setExpandedDim(isOpen ? null : i)}
                  >
                    <div style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      marginBottom: '6px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgba(255,255,255,0.7)' }}>
                          {dim.dimension.replace(/_/g, ' ')}
                        </span>
                        {((dim as any).rationale ?? dim.reason) && (
                          <span style={{ color: 'rgba(255,255,255,0.2)' }}>
                            {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                          </span>
                        )}
                      </div>
                      <span style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: '12px', fontWeight: 600, color,
                      }}>
                        {score}%
                      </span>
                    </div>
                    <div style={{ height: '4px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${score}%` }}
                        transition={{ duration: 0.65, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                        style={{
                          height: '100%',
                          background: `linear-gradient(90deg, ${color}88, ${color})`,
                          borderRadius: '3px',
                        }}
                      />
                    </div>
                  </div>
                  {/* Expandable rationale */}
                  {isOpen && ((dim as any).rationale ?? dim.reason) && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      style={{
                        fontSize: '12px', color: 'rgba(255,255,255,0.45)',
                        lineHeight: 1.6, marginTop: '8px',
                        paddingLeft: '10px', borderLeft: `2px solid ${color}44`,
                      }}
                    >
                      {((dim as any).rationale ?? dim.reason)}
                    </motion.p>
                  )}
                </div>
              );
            })}
          </div>
          {dims.length > 5 && (
            <button
              onClick={() => setShowAll(v => !v)}
              style={{
                marginTop: '12px',
                fontSize: '12px', color: 'rgba(255,255,255,0.35)',
                background: 'none', border: 'none', cursor: 'pointer', padding: 0,
              }}
            >
              {showAll ? '↑ Show less' : `↓ Show ${dims.length - 5} more`}
            </button>
          )}
        </div>
      )}

      {/* Two-col row: Concerns + Signals */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>

        {/* Key Concerns */}
        {concerns.length > 0 && (
          <div style={{
            padding: '14px 16px',
            borderRadius: '12px',
            background: 'rgba(255,71,87,0.05)',
            border: '1px solid rgba(255,71,87,0.15)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <AlertTriangle size={13} color="#ff4757" />
              <span style={{
                fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
                color: '#ff4757',
              }}>
                Key Concerns
              </span>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {concerns.map((c, i) => (
                <li key={i} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  <span style={{ color: 'rgba(255,71,87,0.5)', flexShrink: 0, marginTop: '2px' }}>•</span>
                  <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.5 }}>{c}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Positive Signals */}
        {signals.length > 0 && (
          <div style={{
            padding: '14px 16px',
            borderRadius: '12px',
            background: 'rgba(0,230,118,0.04)',
            border: '1px solid rgba(0,230,118,0.14)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
              <CheckCircle2 size={13} color="#00e676" />
              <span style={{
                fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
                color: '#00e676',
              }}>
                Positive Signals
              </span>
            </div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {signals.map((s, i) => (
                <li key={i} style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
                  <span style={{ color: 'rgba(0,230,118,0.5)', flexShrink: 0, marginTop: '2px' }}>✓</span>
                  <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.5 }}>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Recommendation */}
      {recommendation && (
        <div style={{
          padding: '14px 16px',
          borderRadius: '12px',
          background: 'rgba(124,58,237,0.05)',
          border: '1px solid rgba(124,58,237,0.18)',
          borderLeft: '3px solid #7c3aed',
          display: 'flex', alignItems: 'flex-start', gap: '10px',
        }}>
          <Lightbulb size={14} color="#a78bfa" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <p style={{
              fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
              color: '#a78bfa', marginBottom: '5px',
            }}>
              Recommendation
            </p>
            <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.72)', lineHeight: 1.6, margin: 0 }}>
              {recommendation}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
