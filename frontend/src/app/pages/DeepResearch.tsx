/**
 * Deep Research — autonomous literature synthesis page.
 *
 * Design theme: "Research Observatory"
 * Dark base #06080f · violet #7c3aed/#a78bfa · cyan #06b6d4
 * Glassmorphism panels · terminal aesthetic
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Telescope,
  Sparkles,
  SlidersHorizontal,
  Search,
  ChevronDown,
  AlertCircle,
  Database,
  FileText,
} from 'lucide-react';
import { toast } from 'sonner';
import { Layout } from '../components/Layout';
import { JobStatusTracker } from '../components/JobStatusTracker';
import { ScoringWeightCustomizer } from '../components/ScoringWeightCustomizer';
import { TierBadge } from '../components/TierBadge';
import {
  startDeepResearch,
  type ScoringWeights,
  type DeepResearchJobStatus,
  type Paper,
} from '../../api/client';
import { type Tier } from '../data/mockData';

// ─── Tier colors ─────────────────────────────────────────────────────────────

const TIER_COLOR: Record<string, string> = {
  Trusted: '#00e676',
  Caution: '#ffd166',
  Untrusted: '#ff4757',
};

// ─── Compact paper row for accepted papers list ───────────────────────────────

function MiniPaperRow({ paper }: { paper: Paper }) {
  const [hovered, setHovered] = useState(false);
  const tierColor = TIER_COLOR[paper.tier] ?? 'rgba(255,255,255,0.35)';
  const displayScore = paper.composite_score ?? paper.score;

  const handleClick = () => {
    if (paper.doi) {
      window.open(`/paper?doi=${encodeURIComponent(paper.doi)}&from=results`, '_blank');
    }
  };

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '9px 12px',
        borderRadius: '9px',
        background: hovered ? 'rgba(124,58,237,0.08)' : 'rgba(255,255,255,0.025)',
        border: `1px solid ${hovered ? 'rgba(124,58,237,0.22)' : 'rgba(255,255,255,0.06)'}`,
        cursor: 'pointer',
        transition: 'background 0.15s, border-color 0.15s',
        minWidth: 0,
        overflow: 'hidden',
      }}
    >
      {/* Score chip */}
      <span style={{
        flexShrink: 0,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '12px',
        fontWeight: 700,
        color: tierColor,
        minWidth: '28px',
        textAlign: 'right',
      }}>
        {displayScore ?? '—'}
      </span>

      {/* Title */}
      <span style={{
        flex: 1,
        fontSize: '12px',
        color: 'rgba(255,255,255,0.72)',
        lineHeight: 1.35,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {paper.title ?? paper.doi ?? 'Unknown paper'}
      </span>

      {/* Venue · year — hidden on very small screens to avoid overflow */}
      {(paper.venue || paper.year) && (
        <span className="dr-paper-meta" style={{
          flexShrink: 0,
          fontSize: '10px',
          color: 'rgba(255,255,255,0.25)',
          fontFamily: "'JetBrains Mono', monospace",
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: '140px',
        }}>
          {[paper.venue, paper.year].filter(Boolean).join(' · ')}
        </span>
      )}

      {/* Tier badge */}
      {paper.tier && (
        <span style={{ flexShrink: 0 }}>
          <TierBadge tier={paper.tier.toLowerCase() as Tier} />
        </span>
      )}
    </div>
  );
}

// ─── Chip ─────────────────────────────────────────────────────────────────────

function Chip({ label, color = '#a78bfa' }: { label: string; color?: string }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '3px 10px',
      borderRadius: '20px',
      fontSize: '11px',
      fontWeight: 500,
      background: `${color}14`,
      border: `1px solid ${color}30`,
      color,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {label}
    </span>
  );
}

// ─── Section label ────────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p style={{
      fontSize: '10px',
      fontWeight: 700,
      color: 'rgba(255,255,255,0.35)',
      letterSpacing: '0.09em',
      textTransform: 'uppercase',
      margin: '0 0 8px',
    }}>
      {children}
    </p>
  );
}

// ─── Gradient top rule ────────────────────────────────────────────────────────

function GradientRule() {
  return (
    <div style={{
      height: '1px',
      background: 'linear-gradient(90deg, transparent, #7c3aed, #06b6d4, transparent)',
      marginBottom: '0',
    }} />
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function DeepResearch() {
  const [prompt, setPrompt] = useState('');
  const [topK, setTopK] = useState(15);
  const [minTier, setMinTier] = useState<'Trusted' | 'Caution' | 'Untrusted'>('Caution');
  const [weights, setWeights] = useState<ScoringWeights | undefined>();
  const [showWeights, setShowWeights] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DeepResearchJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Hover state for submit button
  const [submitHovered, setSubmitHovered] = useState(false);
  const [weightsHovered, setWeightsHovered] = useState(false);

  const isRunning = !!jobId && !result && !error;
  const canSubmit = prompt.trim().length > 0 && !isRunning && !isSubmitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError(null);
    setResult(null);
    setJobId(null);

    try {
      const res = await startDeepResearch(prompt.trim(), topK, minTier, undefined, weights);
      setJobId(res.job_id);
      toast.success('Research job started — synthesising literature…');
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? err?.message ?? 'Failed to start research job';
      setError(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleComplete = (status: DeepResearchJobStatus) => {
    setResult(status);
    toast.success('Deep research complete!');
  };

  const handleError = (msg: string) => {
    setError(msg);
    toast.error(msg);
  };

  const papers = result?.accepted_papers ?? [];
  const generatedQueries: string[] = result?.generated_queries ?? [];
  const meshTerms: string[] = result?.mesh_terms ?? [];

  return (
    <Layout showBack>
      {/* Decorative background orb — violet top-left */}
      <div style={{
        position: 'fixed',
        top: '-10%',
        left: '-8%',
        width: '600px',
        height: '600px',
        background: 'radial-gradient(circle, rgba(124,58,237,0.09) 0%, transparent 65%)',
        filter: 'blur(90px)',
        pointerEvents: 'none',
        zIndex: 0,
      }} />

      <div style={{ maxWidth: '1320px', margin: '0 auto', padding: '32px 24px 100px', position: 'relative', zIndex: 10 }} className="deep-research-container">

        {/* ── Page header ────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          style={{ marginBottom: '32px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '8px' }}>
            {/* Icon block */}
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              background: 'linear-gradient(135deg, rgba(124,58,237,0.22), rgba(6,182,212,0.14))',
              border: '1px solid rgba(124,58,237,0.32)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 28px rgba(124,58,237,0.18)',
            }}>
              <Telescope size={22} color="#a78bfa" />
            </div>

            <div>
              <h1 style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontSize: '26px',
                fontWeight: 700,
                margin: 0,
                background: 'linear-gradient(135deg, #ffffff 0%, #a78bfa 50%, #06b6d4 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                lineHeight: 1.15,
              }}>
                Deep Research
              </h1>
              <p style={{
                fontSize: '12px',
                color: 'rgba(255,255,255,0.32)',
                margin: '2px 0 0',
                fontFamily: "'JetBrains Mono', monospace",
                letterSpacing: '0.03em',
              }}>
                Autonomous literature synthesis · LLM-graded credibility · Citation graph
              </p>
            </div>
          </div>
        </motion.div>

        {/* ── Two-column layout ───────────────────────────────────────────── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(300px, 380px) 1fr',
          gap: '20px',
          alignItems: 'start',
        }} className="deep-research-grid">

          {/* ═══════════════════════════════════ LEFT: Config panel ═════════ */}
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.08 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
          >

            {/* Research prompt card */}
            <div style={{
              borderRadius: '16px',
              overflow: 'hidden',
              border: '1px solid rgba(124,58,237,0.2)',
              background: 'rgba(255,255,255,0.025)',
            }}>
              <GradientRule />
              <div style={{ padding: '20px' }}>
                <SectionLabel>Research Prompt</SectionLabel>

                <textarea
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  placeholder="e.g. What is the evidence for GLP-1 receptor agonists in reducing cardiovascular events in diabetic patients?"
                  rows={5}
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    minHeight: '100px',
                    resize: 'vertical',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(124,58,237,0.2)',
                    color: 'rgba(255,255,255,0.85)',
                    fontSize: '13px',
                    lineHeight: 1.6,
                    outline: 'none',
                    fontFamily: "'Inter', sans-serif",
                    transition: 'border-color 0.2s',
                  }}
                  onFocus={e => { e.currentTarget.style.borderColor = 'rgba(124,58,237,0.45)'; }}
                  onBlur={e => { e.currentTarget.style.borderColor = 'rgba(124,58,237,0.2)'; }}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit(); }}
                />

                <p style={{
                  fontSize: '10px',
                  color: 'rgba(255,255,255,0.18)',
                  margin: '5px 0 0',
                  textAlign: 'right',
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  ⌘↵ to run
                </p>
              </div>
            </div>

            {/* Parameters card */}
            <div style={{
              borderRadius: '16px',
              overflow: 'hidden',
              border: '1px solid rgba(255,255,255,0.07)',
              background: 'rgba(255,255,255,0.025)',
            }}>
              <div style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '18px' }}>

                {/* Top-K slider */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <SectionLabel>Papers to retrieve</SectionLabel>
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '13px',
                      fontWeight: 700,
                      color: '#a78bfa',
                      background: 'rgba(124,58,237,0.14)',
                      border: '1px solid rgba(124,58,237,0.28)',
                      borderRadius: '6px',
                      padding: '1px 8px',
                    }}>
                      {topK}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={5}
                    max={50}
                    step={5}
                    value={topK}
                    onChange={e => setTopK(Number(e.target.value))}
                    style={{
                      width: '100%',
                      accentColor: '#7c3aed',
                      cursor: 'pointer',
                    }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono', monospace" }}>5</span>
                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono', monospace" }}>50</span>
                  </div>
                </div>

                {/* Min tier selector */}
                <div>
                  <SectionLabel>Minimum tier</SectionLabel>
                  <div style={{ display: 'flex', gap: '7px' }}>
                    {(['Trusted', 'Caution', 'Untrusted'] as const).map(tier => {
                      const color = TIER_COLOR[tier];
                      const active = minTier === tier;
                      return (
                        <button
                          key={tier}
                          onClick={() => setMinTier(tier)}
                          style={{
                            flex: 1,
                            padding: '7px 0',
                            borderRadius: '8px',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            border: `1px solid ${active ? color + '55' : 'rgba(255,255,255,0.07)'}`,
                            background: active ? `${color}14` : 'rgba(255,255,255,0.03)',
                            color: active ? color : 'rgba(255,255,255,0.28)',
                            transition: 'all 0.15s',
                          }}
                        >
                          {tier}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Customize weights button */}
                <button
                  onClick={() => setShowWeights(true)}
                  onMouseEnter={() => setWeightsHovered(true)}
                  onMouseLeave={() => setWeightsHovered(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '9px 14px',
                    borderRadius: '9px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: `1px solid ${weightsHovered ? 'rgba(6,182,212,0.35)' : 'rgba(255,255,255,0.09)'}`,
                    background: weightsHovered ? 'rgba(6,182,212,0.08)' : 'rgba(255,255,255,0.03)',
                    color: weightsHovered ? '#06b6d4' : 'rgba(255,255,255,0.45)',
                    transition: 'all 0.2s',
                  }}
                >
                  <SlidersHorizontal size={13} />
                  Customize Weights
                  {/* Active indicator dot */}
                  {weights && (
                    <span style={{
                      marginLeft: 'auto',
                      width: '7px',
                      height: '7px',
                      borderRadius: '50%',
                      background: '#06b6d4',
                      boxShadow: '0 0 8px rgba(6,182,212,0.6)',
                    }} />
                  )}
                </button>
              </div>
            </div>

            {/* Submit button */}
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              onMouseEnter={() => setSubmitHovered(true)}
              onMouseLeave={() => setSubmitHovered(false)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '9px',
                padding: '14px',
                borderRadius: '12px',
                fontSize: '14px',
                fontWeight: 700,
                fontFamily: "'Space Grotesk', sans-serif",
                cursor: canSubmit ? 'pointer' : 'not-allowed',
                border: 'none',
                background: canSubmit
                  ? submitHovered
                    ? 'linear-gradient(135deg, #6d28d9, #0e7490)'
                    : 'linear-gradient(135deg, #7c3aed, #0891b2)'
                  : 'rgba(255,255,255,0.06)',
                color: canSubmit ? 'white' : 'rgba(255,255,255,0.25)',
                boxShadow: canSubmit
                  ? submitHovered
                    ? '0 4px 24px rgba(124,58,237,0.45)'
                    : '0 4px 18px rgba(124,58,237,0.28)'
                  : 'none',
                transition: 'all 0.25s',
                letterSpacing: '0.01em',
              }}
            >
              {isSubmitting
                ? <>
                  <span style={{
                    width: '14px', height: '14px',
                    border: '2px solid rgba(255,255,255,0.3)',
                    borderTopColor: 'white',
                    borderRadius: '50%',
                    animation: 'spin 0.7s linear infinite',
                    display: 'inline-block',
                  }} />
                  Starting research…
                </>
                : isRunning
                  ? <>
                    <span style={{
                      width: '14px', height: '14px',
                      border: '2px solid rgba(255,255,255,0.3)',
                      borderTopColor: 'white',
                      borderRadius: '50%',
                      animation: 'spin 0.7s linear infinite',
                      display: 'inline-block',
                    }} />
                    Research in progress…
                  </>
                  : <><Sparkles size={15} /> Run Deep Research</>
              }
            </button>

            {/* Error banner */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '10px',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    background: 'rgba(255,71,87,0.07)',
                    border: '1px solid rgba(255,71,87,0.22)',
                  }}
                >
                  <AlertCircle size={14} color="#ff4757" style={{ flexShrink: 0, marginTop: '1px' }} />
                  <p style={{ fontSize: '12px', color: '#ff4757', margin: 0, lineHeight: 1.5 }}>
                    {error}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* ═══════════════════════════════════ RIGHT: Results panel ═══════ */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, delay: 0.12 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '16px', minHeight: '400px', minWidth: 0 }}
          >

            {/* Job status tracker while running */}
            {jobId && !result && (
              <JobStatusTracker
                jobId={jobId}
                onComplete={handleComplete}
                onError={handleError}
              />
            )}

            {/* Empty state */}
            {!jobId && !result && (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: '380px',
                borderRadius: '16px',
                border: '1px dashed rgba(124,58,237,0.18)',
                background: 'rgba(124,58,237,0.025)',
                gap: '14px',
                textAlign: 'center',
                padding: '40px 32px',
              }}>
                <div style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '16px',
                  background: 'rgba(124,58,237,0.1)',
                  border: '1px solid rgba(124,58,237,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <Telescope size={26} color="rgba(167,139,250,0.55)" />
                </div>
                <div>
                  <p style={{ fontSize: '15px', fontWeight: 600, fontFamily: "'Space Grotesk', sans-serif", color: 'rgba(255,255,255,0.45)', margin: '0 0 6px' }}>
                    Ready to synthesise
                  </p>
                  <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.2)', margin: 0, lineHeight: 1.6, maxWidth: '340px' }}>
                    Enter a research prompt and click <em>Run Deep Research</em>. The agent will retrieve papers, score them for credibility, and synthesise a structured report.
                  </p>
                </div>

                {/* Feature chips */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '7px', justifyContent: 'center', marginTop: '6px' }}>
                  {[
                    { icon: <Search size={10} />, label: 'Multi-source retrieval' },
                    { icon: <Database size={10} />, label: 'Credibility scoring' },
                    { icon: <FileText size={10} />, label: 'Structured synthesis' },
                  ].map(f => (
                    <span key={f.label} style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      padding: '4px 11px',
                      borderRadius: '20px',
                      fontSize: '11px',
                      color: 'rgba(255,255,255,0.28)',
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.06)',
                    }}>
                      {f.icon}
                      {f.label}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Results section */}
            <AnimatePresence>
              {result && (
                <motion.div
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45 }}
                  style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
                >

                  {/* ── Summary bar ── */}
                  <div style={{
                    borderRadius: '14px',
                    overflow: 'hidden',
                    border: '1px solid rgba(124,58,237,0.2)',
                    background: 'rgba(124,58,237,0.04)',
                  }}>
                    <GradientRule />
                    <div className="dr-stats-bar" style={{ padding: '16px 18px', alignItems: 'center' }}>
                      {[
                        { label: 'Accepted', value: papers.length, color: '#a78bfa' },
                        { label: 'Trusted', value: papers.filter((p: Paper) => p.tier === 'Trusted').length, color: '#00e676' },
                        { label: 'Caution', value: papers.filter((p: Paper) => p.tier === 'Caution').length, color: '#ffd166' },
                        { label: 'Queries', value: generatedQueries.length, color: '#06b6d4' },
                        { label: 'MeSH terms', value: meshTerms.length, color: 'rgba(255,255,255,0.4)' },
                      ].map(s => (
                        <div key={s.label} style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '7px',
                          padding: '5px 12px',
                          borderRadius: '8px',
                          background: 'rgba(255,255,255,0.03)',
                          border: '1px solid rgba(255,255,255,0.07)',
                        }}>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '14px', fontWeight: 700, color: s.color }}>
                            {s.value}
                          </span>
                          <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)' }}>{s.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* ── Generated queries ── */}
                  {generatedQueries.length > 0 && (
                    <div style={{
                      padding: '16px 18px',
                      borderRadius: '14px',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.07)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '10px' }}>
                        <Search size={13} color="#a78bfa" />
                        <SectionLabel>Generated queries</SectionLabel>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {generatedQueries.map((q, i) => (
                          <Chip key={i} label={q} color="#a78bfa" />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── MeSH terms ── */}
                  {meshTerms.length > 0 && (
                    <div style={{
                      padding: '16px 18px',
                      borderRadius: '14px',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.07)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '10px' }}>
                        <Database size={13} color="#06b6d4" />
                        <SectionLabel>MeSH terms</SectionLabel>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {meshTerms.map((t, i) => (
                          <Chip key={i} label={t} color="#06b6d4" />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── Accepted papers list ── */}
                  {papers.length > 0 && (
                    <div style={{
                      borderRadius: '14px',
                      overflow: 'hidden',
                      border: '1px solid rgba(255,255,255,0.07)',
                      background: 'rgba(255,255,255,0.02)',
                    }}>
                      {/* Header */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '12px 16px',
                        borderBottom: '1px solid rgba(255,255,255,0.06)',
                        background: 'rgba(255,255,255,0.025)',
                      }}>
                        <FileText size={13} color="#a78bfa" />
                        <span style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                          Accepted papers
                        </span>
                        <span style={{
                          marginLeft: 'auto',
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: '11px',
                          fontWeight: 700,
                          color: '#a78bfa',
                        }}>
                          {papers.length}
                        </span>
                      </div>

                      {/* Paper rows */}
                      <div style={{ padding: '10px', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                        {papers.map((p: Paper, i: number) => (
                          <MiniPaperRow key={p.doi ?? i} paper={p} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Reset / new research button */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '4px' }}>
                    <button
                      onClick={() => {
                        setResult(null);
                        setJobId(null);
                        setError(null);
                        setPrompt('');
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '7px',
                        padding: '8px 16px',
                        borderRadius: '9px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.09)',
                        color: 'rgba(255,255,255,0.4)',
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
                        (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)';
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
                        (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
                      }}
                    >
                      <ChevronDown size={13} style={{ transform: 'rotate(90deg)' }} />
                      New research
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>

      {/* ── Scoring Weight Customizer modal ─────────────────────────────────── */}
      <AnimatePresence>
        {showWeights && (
          <ScoringWeightCustomizer
            initialWeights={weights}
            onApply={w => {
              setWeights(w);
              setShowWeights(false);
              toast.success('Custom weights saved');
            }}
            onCancel={() => setShowWeights(false)}
          />
        )}
      </AnimatePresence>

      {/* Responsive styles */}
      <style>{`
        @media (max-width: 1024px) {
          .deep-research-container {
            padding: 24px 16px 100px !important;
          }
          .deep-research-grid {
            grid-template-columns: 1fr !important;
          }
        }

        @media (max-width: 768px) {
          .deep-research-container {
            padding: 16px 12px 100px !important;
          }
          .deep-research-grid {
            grid-template-columns: 1fr !important;
            gap: 16px !important;
          }
        }

        @media (max-width: 640px) {
          .deep-research-container {
            padding: 12px 10px 110px !important;
          }
          /* Hide venue/year meta on very small screens */
          .dr-paper-meta {
            display: none !important;
          }
        }

        @media (max-width: 480px) {
          .deep-research-container {
            padding: 8px 8px 120px !important;
          }
        }

        /* Prevent the summary stats bar from overflowing */
        .dr-stats-bar {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
      `}</style>
    </Layout>
  );
}
