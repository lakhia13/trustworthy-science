/**
 * Score Papers — unified input page for POST /score.
 * Three modes: DOI list · PMID list · Natural-language query.
 * Only one mode is active at a time; switching clears the other inputs.
 */
import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Search, X, RotateCcw, Download, Loader2, Plus,
  Hash, Link2, AlignLeft, CheckCircle2, AlertCircle,
} from 'lucide-react';
import { Layout } from '../components/Layout';
import { PaperCard } from '../components/PaperCard';
import { toast } from 'sonner';
import { scorePapers, getUserErrorMessage, type Paper, type Flag } from '../../api/client';

// ─── helpers ────────────────────────────────────────────────────────────────

type Mode = 'doi' | 'pmid' | 'query';

/** Normalise a flag value (string | Flag) → { code: string } */
function toCodeObj(f: string | Flag): { code: string } {
  if (typeof f === 'string') return { code: f };
  return { code: (f as Flag).code ?? String(f) };
}

/** Adapt raw API Paper to what PaperCard expects */
function adaptPaper(paper: Paper, index: number) {
  return {
    ...paper,
    id: paper.doi || (paper as any).pmid || `paper-${index}`,
    tier: (paper.tier?.toLowerCase() ?? 'untrusted') as any,
    score: paper.score ?? paper.composite_score ?? 0,
    hardFlags: Array.isArray(paper.hard_flags)
      ? (paper.hard_flags as (string | Flag)[]).map(f =>
          typeof f === 'string' ? f : (f as Flag).code)
      : [],
    softFlags: Array.isArray(paper.soft_flags)
      ? (paper.soft_flags as (string | Flag)[]).map(toCodeObj)
      : [],
    qualitySignals: Array.isArray(paper.quality_signals)
      ? (paper.quality_signals as (string | Flag)[]).map(toCodeObj)
      : [],
    authors: Array.isArray(paper.authors) ? paper.authors.join(', ') : (paper.authors ?? ''),
    venue: paper.venue ?? '',
    year: paper.year ?? '',
  };
}

// ─── mode config ─────────────────────────────────────────────────────────────

const MODE_CONFIG = {
  doi: {
    icon: Link2,
    label: 'DOI',
    placeholder: 'e.g. 10.1038/s41586-024-07487-w',
    tip: 'Paste one or multiple DOIs separated by newlines or commas',
    color: '#4d88ff',
    colorAlpha: 'rgba(77,136,255,',
  },
  pmid: {
    icon: Hash,
    label: 'PMID',
    placeholder: 'e.g. 37952131',
    tip: 'Paste one or multiple PubMed IDs separated by newlines or commas',
    color: '#06b6d4',
    colorAlpha: 'rgba(6,182,212,',
  },
  query: {
    icon: AlignLeft,
    label: 'Query',
    placeholder: 'e.g. GLP-1 receptor agonists cardiovascular outcomes in type 2 diabetes',
    tip: 'Natural-language research question — returns top matching papers',
    color: '#a78bfa',
    colorAlpha: 'rgba(167,139,250,',
  },
} as const;

// ─── main component ──────────────────────────────────────────────────────────

export function DOISearch() {
  const [mode, setMode] = useState<Mode>('doi');

  // chip lists for doi / pmid modes
  const [doiChips, setDoiChips] = useState<string[]>([]);
  const [pmidChips, setPmidChips] = useState<string[]>([]);

  // text inputs
  const [chipInput, setChipInput] = useState('');
  const [queryText, setQueryText] = useState('');
  const [topK, setTopK] = useState(10);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Paper[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── chip helpers ──────────────────────────────────────────────────────────

  const chips = mode === 'doi' ? doiChips : pmidChips;
  const setChips = mode === 'doi' ? setDoiChips : setPmidChips;

  const addChips = () => {
    const raw = chipInput
      .split(/[\n,\s]+/)
      .map(s => s.trim().replace(/^https?:\/\/doi\.org\//i, ''))
      .filter(Boolean);
    const novel = raw.filter(v => !chips.includes(v));
    if (novel.length) setChips(prev => [...prev, ...novel]);
    setChipInput('');
  };

  const removeChip = (val: string) => setChips(prev => prev.filter(v => v !== val));

  const handleChipKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addChips(); }
  };

  // ── switch mode ───────────────────────────────────────────────────────────

  const switchMode = (next: Mode) => {
    setMode(next);
    setChipInput('');
    setError(null);
  };

  // ── can submit? ───────────────────────────────────────────────────────────

  const canSubmit = mode === 'query'
    ? queryText.trim().length > 0
    : chips.length > 0;

  // ── submit ────────────────────────────────────────────────────────────────

  const handleScore = async () => {
    if (!canSubmit) { toast.error('Please provide input first'); return; }
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      let resp;
      if (mode === 'doi')   resp = await scorePapers(doiChips, undefined, topK);
      if (mode === 'pmid')  resp = await scorePapers([], undefined, topK, pmidChips);
      if (mode === 'query') resp = await scorePapers([], queryText.trim(), topK);
      const papers = resp!.papers;
      setResults(papers);
      setHasSearched(true);
      toast.success(`Scored ${papers.length} paper${papers.length !== 1 ? 's' : ''}`);
    } catch (err: any) {
      const msg = getUserErrorMessage(err);
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  // ── clear ─────────────────────────────────────────────────────────────────

  const handleClear = () => {
    setDoiChips([]); setPmidChips([]);
    setChipInput(''); setQueryText('');
    setResults([]); setHasSearched(false); setError(null);
  };

  // ── export ────────────────────────────────────────────────────────────────

  const handleExport = () => {
    if (!results.length) return;
    const rows = [
      ['Title', 'DOI', 'PMID', 'Year', 'Venue', 'Score', 'Tier'],
      ...results.map(p => [
        `"${(p.title ?? '').replace(/"/g, '""')}"`,
        p.doi ?? '',
        (p as any).pmid ?? '',
        String(p.year ?? ''),
        `"${(p.venue ?? '').replace(/"/g, '""')}"`,
        String(p.score ?? p.composite_score ?? 0),
        p.tier,
      ]),
    ].map(r => r.join(',')).join('\n');
    navigator.clipboard.writeText(rows).then(() => toast.success('CSV copied to clipboard'));
  };

  // ── render ────────────────────────────────────────────────────────────────

  const cfg = MODE_CONFIG[mode];
  const ModeIcon = cfg.icon;

  return (
    <Layout showBack>
      <div style={{ maxWidth: '780px', margin: '0 auto', padding: '36px 24px 100px' }}>
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.4 }}
        >

          {/* ── Page header ── */}
          <div style={{ marginBottom: '36px' }}>
            <div style={{ width: '48px', height: '3px', borderRadius: '2px', background: 'linear-gradient(90deg, #7c3aed, #06b6d4)', marginBottom: '16px' }} />
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: '30px', fontWeight: 700, letterSpacing: '-0.02em',
              color: 'rgba(255,255,255,0.96)', marginBottom: '6px',
            }}>
              Score Papers
            </h1>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.38)', lineHeight: 1.6 }}>
              Enter DOIs, PubMed IDs, or a research question — get instant credibility scores across 5 AI dimensions
            </p>
          </div>

          {/* ── Mode selector ── */}
          <div style={{
            display: 'flex', gap: '4px', marginBottom: '20px',
            padding: '5px', borderRadius: '14px',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)',
            width: 'fit-content',
          }}>
            {(['doi', 'pmid', 'query'] as Mode[]).map(m => {
              const { label, icon: Icon, color } = MODE_CONFIG[m];
              const active = mode === m;
              return (
                <button
                  key={m}
                  onClick={() => switchMode(m)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '7px',
                    padding: '8px 18px', borderRadius: '10px',
                    fontSize: '13px', fontWeight: 500,
                    border: active ? `1px solid ${color}55` : '1px solid transparent',
                    background: active ? `${color}18` : 'transparent',
                    color: active ? color : 'rgba(255,255,255,0.38)',
                    cursor: 'pointer', transition: 'all 0.18s',
                  }}
                  onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.7)'; }}
                  onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.38)'; }}
                >
                  <Icon size={13} />
                  {label}
                </button>
              );
            })}
          </div>

          {/* ── Input panel ── */}
          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              style={{
                padding: '22px', borderRadius: '16px', marginBottom: '16px',
                background: 'rgba(255,255,255,0.025)',
                border: `1px solid ${cfg.colorAlpha}0.12)`,
                position: 'relative', overflow: 'hidden',
              }}
            >
              {/* accent top line */}
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, height: '2px',
                background: `linear-gradient(90deg, transparent, ${cfg.color}99, transparent)`,
              }} />

              {/* panel label */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '8px',
                  background: `${cfg.colorAlpha}0.12)`,
                  border: `1px solid ${cfg.colorAlpha}0.28)`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <ModeIcon size={13} color={cfg.color} />
                </div>
                <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: cfg.color }}>
                  {cfg.label} Input
                </span>
              </div>

              {/* QUERY mode */}
              {mode === 'query' && (
                <div>
                  <textarea
                    value={queryText}
                    onChange={e => setQueryText(e.target.value)}
                    placeholder={cfg.placeholder}
                    rows={3}
                    style={{
                      width: '100%', padding: '12px 14px', borderRadius: '10px',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.09)',
                      color: 'rgba(255,255,255,0.85)', fontSize: '14px',
                      fontFamily: "'Inter', sans-serif", lineHeight: 1.55,
                      outline: 'none', resize: 'vertical', boxSizing: 'border-box',
                      transition: 'border-color 0.15s',
                    }}
                    onFocus={e => (e.target.style.borderColor = `${cfg.colorAlpha}0.5)`)}
                    onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.09)')}
                  />
                  <div style={{ marginTop: '14px', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.3)', whiteSpace: 'nowrap' }}>Top results</span>
                    {[5, 10, 15, 20].map(k => (
                      <button
                        key={k}
                        onClick={() => setTopK(k)}
                        style={{
                          padding: '4px 12px', borderRadius: '7px', fontSize: '12px',
                          fontFamily: "'JetBrains Mono', monospace",
                          border: topK === k ? `1px solid ${cfg.colorAlpha}0.45)` : '1px solid rgba(255,255,255,0.08)',
                          background: topK === k ? `${cfg.colorAlpha}0.12)` : 'rgba(255,255,255,0.03)',
                          color: topK === k ? cfg.color : 'rgba(255,255,255,0.3)',
                          cursor: 'pointer', transition: 'all 0.15s',
                        }}
                      >
                        {k}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* DOI / PMID chip mode */}
              {mode !== 'query' && (
                <div>
                  {chips.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
                      <AnimatePresence>
                        {chips.map(chip => (
                          <motion.div
                            key={chip}
                            initial={{ opacity: 0, x: -10, height: 0 }}
                            animate={{ opacity: 1, x: 0, height: 'auto' }}
                            exit={{ opacity: 0, x: -10, height: 0 }}
                            transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.2 }}
                            style={{
                              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              padding: '9px 14px', borderRadius: '9px',
                              background: `${cfg.colorAlpha}0.07)`,
                              border: `1px solid ${cfg.colorAlpha}0.18)`,
                            }}
                          >
                            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '13px', color: 'rgba(255,255,255,0.78)' }}>
                              {chip}
                            </span>
                            <button
                              onClick={() => removeChip(chip)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.22)', padding: '2px', lineHeight: 1, marginLeft: '8px' }}
                              onMouseEnter={e => (e.currentTarget.style.color = '#ff4757')}
                              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.22)')}
                            >
                              <X size={13} />
                            </button>
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      value={chipInput}
                      onChange={e => setChipInput(e.target.value)}
                      onKeyDown={handleChipKey}
                      placeholder={cfg.placeholder}
                      style={{
                        flex: 1, padding: '10px 14px', borderRadius: '10px',
                        background: 'rgba(255,255,255,0.04)',
                        border: '1px solid rgba(255,255,255,0.09)',
                        color: 'rgba(255,255,255,0.85)', fontSize: '13px',
                        fontFamily: "'JetBrains Mono', monospace",
                        outline: 'none', transition: 'border-color 0.15s',
                      }}
                      onFocus={e => (e.target.style.borderColor = `${cfg.colorAlpha}0.5)`)}
                      onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.09)')}
                    />
                    <button
                      onClick={addChips}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '5px',
                        padding: '10px 16px', borderRadius: '10px',
                        background: `${cfg.colorAlpha}0.1)`,
                        border: `1px solid ${cfg.colorAlpha}0.28)`,
                        color: cfg.color, fontSize: '13px', cursor: 'pointer',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = `${cfg.colorAlpha}0.2)`)}
                      onMouseLeave={e => (e.currentTarget.style.background = `${cfg.colorAlpha}0.1)`)}
                    >
                      <Plus size={14} /> Add
                    </button>
                  </div>
                  <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.2)', marginTop: '6px' }}>
                    {cfg.tip}
                  </p>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* ── Action buttons ── */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '40px', flexWrap: 'wrap' }}>
            <button
              onClick={handleScore}
              disabled={loading || !canSubmit}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '12px 28px', borderRadius: '12px',
                background: canSubmit
                  ? `linear-gradient(135deg, ${cfg.color}, ${mode === 'doi' ? '#6d6bff' : mode === 'pmid' ? '#7c3aed' : '#4d88ff'})`
                  : 'rgba(255,255,255,0.05)',
                color: canSubmit ? 'white' : 'rgba(255,255,255,0.2)',
                fontSize: '14px', fontWeight: 600, border: 'none',
                cursor: loading || !canSubmit ? 'not-allowed' : 'pointer',
                boxShadow: canSubmit ? `0 0 28px ${cfg.colorAlpha}0.35)` : 'none',
                transition: 'all 0.2s',
              }}
            >
              {loading
                ? <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} />
                : <Search size={15} />}
              {loading ? 'Scoring…' : mode === 'query'
                ? 'Search & Score'
                : `Score ${chips.length > 0 ? chips.length + ' ' : ''}${MODE_CONFIG[mode].label}${chips.length !== 1 ? 's' : ''}`}
            </button>

            <button
              onClick={handleClear}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '12px 18px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.35)', fontSize: '14px',
                cursor: 'pointer', transition: 'color 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.65)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
            >
              <RotateCcw size={14} /> Clear
            </button>
          </div>

          {/* ── Error ── */}
          <AnimatePresence>
            {error && (
              <motion.div
                key="err"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: '10px',
                  padding: '14px 16px', borderRadius: '12px', marginBottom: '24px',
                  background: 'rgba(255,71,87,0.08)', border: '1px solid rgba(255,71,87,0.25)',
                  color: '#ff4757', fontSize: '13px',
                }}
              >
                <AlertCircle size={15} style={{ flexShrink: 0, marginTop: '1px' }} />
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Loading skeletons ── */}
          <AnimatePresence>
            {loading && (
              <motion.div key="skel" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {Array.from({ length: mode === 'query' ? Math.min(topK, 5) : chips.length }).map((_, i) => (
                  <div key={i} className="ts-skeleton" style={{ height: '168px', borderRadius: '14px' }} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Results ── */}
          <AnimatePresence>
            {results.length > 0 && !loading && (
              <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  marginBottom: '18px', paddingBottom: '14px',
                  borderBottom: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <CheckCircle2 size={15} color="#00e676" />
                    <span style={{ fontSize: '15px', fontWeight: 600, color: 'rgba(255,255,255,0.7)' }}>Results</span>
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace", fontSize: '12px',
                      color: 'rgba(255,255,255,0.25)', padding: '2px 8px',
                      borderRadius: '5px', background: 'rgba(255,255,255,0.04)',
                    }}>
                      {results.length} paper{results.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <button
                    onClick={handleExport}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '5px',
                      padding: '7px 12px', borderRadius: '8px',
                      background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                      color: 'rgba(255,255,255,0.4)', fontSize: '12px', cursor: 'pointer',
                      transition: 'color 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
                  >
                    <Download size={12} /> Export CSV
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {results.map((paper, i) => (
                    <PaperCard key={adaptPaper(paper, i).id} paper={adaptPaper(paper, i) as any} index={i} />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {hasSearched && results.length === 0 && !loading && (
            <div style={{ textAlign: 'center', padding: '60px 0', color: 'rgba(255,255,255,0.2)', fontSize: '14px' }}>
              No papers found for your input.
            </div>
          )}

        </motion.div>
      </div>
    </Layout>
  );
}
