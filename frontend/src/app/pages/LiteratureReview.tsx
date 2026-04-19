/**
 * Literature Review — Graph RAG page.
 *
 * 3-panel layout:
 *   Left  — seed the graph (add papers by query or DOI)
 *   Centre — live knowledge graph visualization
 *   Right — query the graph, get LLM answer grounded in trusted papers
 */

import { useState, useEffect, useRef, useCallback, Fragment } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Plus, Search, BookOpen, Send, Loader2,
  CheckCircle, XCircle, AlertTriangle, Network,
  ChevronDown, ChevronUp, Trash2, FileDown,
} from 'lucide-react';
import { useNavigate } from 'react-router';
import { Layout } from '../components/Layout';
import { GraphViz } from '../components/GraphViz';
import { toast } from 'sonner';
import { exportReport } from '../utils/exportReport';
import {
  startReviewSession,
  addPapersToSession,
  getSessionGraph,
  querySessionGraph,
  getUserErrorMessage,
  type GraphNode,
  type GraphEdge,
  type PaperSummary,
} from '../../api/client';

// ─── Tier helpers ────────────────────────────────────────────────────────────

const TIER_COLOR: Record<string, string> = {
  Trusted: '#00e676',
  Caution: '#ffd166',
  Untrusted: '#ff4757',
};

const TIER_ICON: Record<string, string> = {
  Trusted: '✅',
  Caution: '⚠️',
  Untrusted: '❌',
};

function TierPill({ tier }: { tier: string }) {
  const color = TIER_COLOR[tier] || '#aaa';
  return (
    <span style={{
      fontSize: '10px', fontWeight: 700, padding: '2px 8px',
      borderRadius: '5px', fontFamily: "'JetBrains Mono', monospace",
      background: `${color}18`, border: `1px solid ${color}44`, color,
    }}>
      {tier}
    </span>
  );
}

// ─── Small paper row for the sidebar list ───────────────────────────────────

function PaperPill({ paper, type }: { paper: PaperSummary; type: 'added' | 'excluded' }) {
  const navigate = useNavigate();
  const color = type === 'added' ? TIER_COLOR[paper.tier] || '#00e676' : '#ff4757';
  return (
    <div
      onClick={() => paper.doi && navigate(`/paper/${encodeURIComponent(paper.doi)}?from=review`)}
      style={{
        padding: '8px 10px', borderRadius: '8px', cursor: 'pointer',
        background: type === 'added' ? `${color}09` : 'rgba(255,71,87,0.05)',
        border: `1px solid ${color}22`,
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.background = `${color}16`)}
      onMouseLeave={e => (e.currentTarget.style.background = type === 'added' ? `${color}09` : 'rgba(255,71,87,0.05)')}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', marginBottom: '2px' }}>
        <span style={{ fontSize: '10px', color, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
          {type === 'added' ? `${paper.score}` : '—'}
        </span>
        <TierPill tier={paper.tier} />
      </div>
      <p style={{ fontSize: '11px', color: type === 'added' ? 'rgba(255,255,255,0.65)' : 'rgba(255,71,87,0.6)', lineHeight: 1.35, margin: 0 }}>
        {paper.title?.length > 70 ? paper.title.slice(0, 68) + '…' : paper.title || paper.doi}
      </p>
    </div>
  );
}

// ─── Answer card ─────────────────────────────────────────────────────────────

function AnswerCard({
  answer,
  papersUsed,
  tookSeconds,
  highlightedDois,
  onHighlight,
}: {
  answer: string;
  papersUsed: PaperSummary[];
  tookSeconds: number;
  highlightedDois: string[];
  onHighlight: (dois: string[]) => void;
}) {
  const [showSources, setShowSources] = useState(true);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        borderRadius: '14px', overflow: 'hidden',
        border: '1px solid rgba(0,230,118,0.18)',
        background: 'rgba(0,230,118,0.04)',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '12px 14px',
        borderBottom: '1px solid rgba(0,230,118,0.1)',
        background: 'rgba(0,230,118,0.06)',
      }}>
        <CheckCircle size={14} color="#00e676" />
        <span style={{ fontSize: '12px', fontWeight: 700, color: '#00e676' }}>
          Graph RAG Answer
        </span>
        <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.28)', marginLeft: 'auto', fontFamily: "'JetBrains Mono', monospace" }}>
          {tookSeconds.toFixed(1)}s · {papersUsed.length} papers
        </span>
      </div>

      {/* Answer text */}
      <div style={{ padding: '14px' }}>
        <p style={{
          fontSize: '13px', color: 'rgba(255,255,255,0.82)',
          lineHeight: 1.65, whiteSpace: 'pre-wrap', margin: 0,
        }}>
          {answer}
        </p>
      </div>

      {/* Sources */}
      {papersUsed.length > 0 && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <button
            onClick={() => setShowSources(s => !s)}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 14px', background: 'none', border: 'none',
              cursor: 'pointer', color: 'rgba(255,255,255,0.4)', fontSize: '11px', fontWeight: 600,
              letterSpacing: '0.06em', textTransform: 'uppercase',
            }}
          >
            Sources ({papersUsed.length})
            {showSources ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          <AnimatePresence>
            {showSources && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                style={{ overflow: 'hidden' }}
              >
                <div style={{ padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {papersUsed.map(p => (
                    <div
                      key={p.doi}
                      onMouseEnter={() => onHighlight([p.doi])}
                      onMouseLeave={() => onHighlight([])}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '6px 10px', borderRadius: '7px', cursor: 'pointer',
                        background: highlightedDois.includes(p.doi)
                          ? 'rgba(0,230,118,0.1)'
                          : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${highlightedDois.includes(p.doi) ? 'rgba(0,230,118,0.25)' : 'rgba(255,255,255,0.05)'}`,
                        transition: 'background 0.15s',
                      }}
                    >
                      <span style={{ fontSize: '11px', fontWeight: 700, color: TIER_COLOR[p.tier] || '#aaa', fontFamily: "'JetBrains Mono', monospace" }}>
                        {p.score}
                      </span>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.55)', flex: 1 }}>
                        {p.title?.length > 55 ? p.title.slice(0, 53) + '…' : p.title || p.doi}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function LiteratureReview() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);

  // Seeding state
  const [seedInput, setSeedInput] = useState('');
  const [seedMode, setSeedMode] = useState<'query' | 'doi'>('query');
  const [addingPapers, setAddingPapers] = useState(false);
  const [addedPapers, setAddedPapers] = useState<PaperSummary[]>([]);
  const [excludedPapers, setExcludedPapers] = useState<PaperSummary[]>([]);

  // Graph state
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [graphStats, setGraphStats] = useState<Record<string, number>>({});
  const [highlightedDois, setHighlightedDois] = useState<string[]>([]);

  // Query state
  const [question, setQuestion] = useState('');
  const [querying, setQuerying] = useState(false);
  const [answers, setAnswers] = useState<Array<{
    question: string;
    answer: string;
    papersUsed: PaperSummary[];
    tookSeconds: number;
  }>>([]);

  const [pendingSeed, setPendingSeed] = useState(false);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [graphWidth, setGraphWidth] = useState(600);

  // Measure graph container width
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        setGraphWidth(entry.contentRect.width);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Start a session on mount
  useEffect(() => {
    startReviewSession()
      .then(res => {
        setSessionId(res.session_id);
        setSessionLoading(false);
        // Check if QuerySearch sent us DOIs to auto-seed
        const pending = sessionStorage.getItem('ts_review_seed_dois');
        if (pending) {
          try {
            sessionStorage.removeItem('ts_review_seed_dois');
            const dois: string[] = JSON.parse(pending);
            if (dois.length > 0) {
              setSeedInput(dois.join('\n'));
              setSeedMode('doi');
              setPendingSeed(true);
            }
          } catch {}
        }
      })
      .catch(err => {
        toast.error('Could not start session: ' + getUserErrorMessage(err));
        setSessionLoading(false);
      });
  }, []);

  // Auto-add papers seeded from QuerySearch
  useEffect(() => {
    if (sessionId && pendingSeed && seedInput.trim()) {
      setPendingSeed(false);
      handleAddPapers();
    }
  }, [sessionId, pendingSeed]);

  // Refresh graph from backend
  const refreshGraph = useCallback(async (sid: string) => {
    try {
      const g = await getSessionGraph(sid);
      setGraphNodes(g.nodes);
      setGraphEdges(g.edges);
      setGraphStats(g.stats);
    } catch {
      // silent — graph viz is optional
    }
  }, []);

  // ── Add papers ──────────────────────────────────────────────────────────
  const handleAddPapers = async () => {
    if (!sessionId || !seedInput.trim()) return;
    setAddingPapers(true);

    try {
      const dois = seedMode === 'doi'
        ? seedInput.split(/[\n,]/).map(s => s.trim()).filter(Boolean)
        : undefined;
      const query = seedMode === 'query' ? seedInput.trim() : undefined;

      const result = await addPapersToSession(sessionId, dois, query, 10);

      setAddedPapers(prev => [...result.added, ...prev]);
      setExcludedPapers(prev => [...result.excluded, ...prev]);

      toast.success(
        `✅ ${result.added.length} added to graph · ❌ ${result.excluded.length} excluded`
      );

      setSeedInput('');
      await refreshGraph(sessionId);
    } catch (err: any) {
      toast.error(getUserErrorMessage(err));
    } finally {
      setAddingPapers(false);
    }
  };

  // ── Query the graph ──────────────────────────────────────────────────────
  const handleQuery = async () => {
    if (!sessionId || !question.trim() || graphNodes.length === 0) return;
    setQuerying(true);

    try {
      const result = await querySessionGraph(sessionId, question.trim(), 5);

      setAnswers(prev => [{
        question: question.trim(),
        answer: result.answer,
        papersUsed: result.papers_used,
        tookSeconds: result.took_seconds,
      }, ...prev]);

      // Highlight the papers used in answer
      setHighlightedDois(result.papers_used.map(p => p.doi));
      setQuestion('');
    } catch (err: any) {
      toast.error(getUserErrorMessage(err));
    } finally {
      setQuerying(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleQuery();
  };

  const handleExport = () => {
    exportReport({ addedPapers, excludedPapers, graphStats, answers });
  };

  if (sessionLoading) {
    return (
      <Layout showBack>
        <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '16px' }}>
          <Loader2 size={36} style={{ color: '#4d88ff', animation: 'spin 1s linear infinite' }} />
          <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '14px' }}>Initializing session…</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout showBack>
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '28px 24px 80px' }}>

        {/* ── Page header ─────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ marginBottom: '24px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(77,136,255,0.18), rgba(109,107,255,0.12))',
              border: '1px solid rgba(77,136,255,0.22)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Network size={18} color="#4d88ff" />
            </div>
            <div>
              <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: '22px', fontWeight: 700, color: 'rgba(255,255,255,0.96)', margin: 0 }}>
                Literature Review
              </h1>
              <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.32)', margin: 0 }}>
                Credibility-filtered knowledge graph · Only Trusted &amp; Caution papers enter
              </p>
            </div>
          </div>

          {/* Step indicator */}
          <div style={{
            display: 'flex', alignItems: 'center',
            marginTop: '14px', marginBottom: '4px', padding: '10px 16px', borderRadius: '12px',
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
          }}>
            {[
              { n: 1, label: 'Seed the graph',      done: addedPapers.length > 0 },
              { n: 2, label: 'Explore connections', done: graphNodes.length > 1 },
              { n: 3, label: 'Ask the literature',  done: answers.length > 0 },
            ].map((step, i) => (
              <Fragment key={step.n}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 12px' }}>
                  <div style={{
                    width: '22px', height: '22px', borderRadius: '50%',
                    fontSize: '11px', fontWeight: 700, flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: step.done ? '#00e676' : 'rgba(255,255,255,0.07)',
                    color: step.done ? '#06080f' : 'rgba(255,255,255,0.35)',
                    border: step.done ? 'none' : '1px solid rgba(255,255,255,0.1)',
                    transition: 'all 0.3s',
                  }}>
                    {step.done ? '✓' : step.n}
                  </div>
                  <span style={{
                    fontSize: '12px', whiteSpace: 'nowrap',
                    fontWeight: step.done ? 600 : 400,
                    color: step.done ? 'rgba(255,255,255,0.75)' : 'rgba(255,255,255,0.28)',
                    transition: 'color 0.3s',
                  }}>
                    {step.label}
                  </span>
                </div>
                {i < 2 && <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)' }} />}
              </Fragment>
            ))}
          </div>

          {/* Stats bar */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '12px', alignItems: 'center' }}>
            {[
              { label: 'In Graph', value: graphStats.total_papers ?? 0, color: '#4d88ff' },
              { label: 'Trusted', value: graphStats.trusted ?? 0, color: '#00e676' },
              { label: 'Caution', value: graphStats.caution ?? 0, color: '#ffd166' },
              { label: 'Connections', value: graphStats.total_edges ?? 0, color: 'rgba(255,255,255,0.4)' },
              { label: 'Excluded', value: excludedPapers.length, color: '#ff4757' },
            ].map(s => (
              <div key={s.label} style={{
                padding: '6px 14px', borderRadius: '8px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.07)',
                display: 'flex', alignItems: 'center', gap: '8px',
              }}>
                <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '15px', fontWeight: 700, color: s.color }}>
                  {s.value}
                </span>
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.32)' }}>{s.label}</span>
              </div>
            ))}
            {answers.length > 0 && (
              <button
                onClick={handleExport}
                style={{
                  marginLeft: 'auto',
                  display: 'flex', alignItems: 'center', gap: '7px',
                  padding: '8px 16px', borderRadius: '10px',
                  background: 'rgba(77,136,255,0.1)',
                  border: '1px solid rgba(77,136,255,0.25)',
                  color: '#4d88ff', fontSize: '12px', fontWeight: 600,
                  cursor: 'pointer', transition: 'all 0.2s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(77,136,255,0.2)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(77,136,255,0.1)';
                }}
              >
                <FileDown size={13} /> Export PDF Report
              </button>
            )}
          </div>
        </motion.div>

        {/* ── 3-panel grid ─────────────────────────────────────────────────── */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '280px 1fr 320px',
          gap: '16px',
          alignItems: 'start',
        }}>

          {/* ═══════════════════════════════════════ LEFT: Seed the graph ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

            {/* Input card */}
            <div style={{
              padding: '16px', borderRadius: '14px',
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.07)',
            }}>
              <p style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: '6px' }}>
                Seed the Graph
              </p>
              <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.22)', marginBottom: '10px', lineHeight: 1.5 }}>
                Only Trusted &amp; Caution papers enter the graph — Untrusted are structurally excluded and can never reach the AI.
              </p>

              {/* Mode toggle */}
              <div style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                {(['query', 'doi'] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => setSeedMode(mode)}
                    style={{
                      flex: 1, padding: '6px 0', borderRadius: '7px', fontSize: '11px', fontWeight: 600,
                      cursor: 'pointer', border: 'none', transition: 'background 0.15s',
                      background: seedMode === mode
                        ? 'rgba(77,136,255,0.22)'
                        : 'rgba(255,255,255,0.04)',
                      color: seedMode === mode ? '#4d88ff' : 'rgba(255,255,255,0.35)',
                    }}
                  >
                    {mode === 'query' ? '🔍 Query' : '📄 DOI'}
                  </button>
                ))}
              </div>

              <textarea
                value={seedInput}
                onChange={e => setSeedInput(e.target.value)}
                placeholder={
                  seedMode === 'query'
                    ? 'e.g. PCSK9 inhibitors cardiovascular outcomes'
                    : 'Paste DOIs (one per line)'
                }
                rows={4}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  padding: '10px', borderRadius: '8px', resize: 'vertical',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.09)',
                  color: 'rgba(255,255,255,0.82)', fontSize: '12px', lineHeight: 1.5,
                  outline: 'none', fontFamily: 'inherit',
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && e.metaKey) handleAddPapers();
                }}
              />

              <button
                onClick={handleAddPapers}
                disabled={addingPapers || !seedInput.trim() || !sessionId}
                style={{
                  marginTop: '10px', width: '100%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                  padding: '10px', borderRadius: '9px',
                  background: addingPapers || !seedInput.trim()
                    ? 'rgba(77,136,255,0.12)'
                    : 'linear-gradient(135deg, #4d88ff, #6d6bff)',
                  color: addingPapers || !seedInput.trim() ? 'rgba(255,255,255,0.3)' : 'white',
                  fontSize: '12px', fontWeight: 600, border: 'none', cursor: addingPapers ? 'wait' : 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                {addingPapers
                  ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Scoring &amp; adding…</>
                  : <><Plus size={13} /> Add to Graph</>
                }
              </button>
            </div>

            {/* Added papers */}
            {addedPapers.length > 0 && (
              <div style={{
                borderRadius: '12px',
                border: '1px solid rgba(0,230,118,0.14)',
                overflow: 'hidden',
              }}>
                <div style={{
                  padding: '10px 12px',
                  background: 'rgba(0,230,118,0.06)',
                  borderBottom: '1px solid rgba(0,230,118,0.1)',
                  display: 'flex', alignItems: 'center', gap: '7px',
                }}>
                  <CheckCircle size={12} color="#00e676" />
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#00e676' }}>
                    In Graph ({addedPapers.length})
                  </span>
                </div>
                <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '5px', maxHeight: '280px', overflowY: 'auto' }}>
                  {addedPapers.map((p, i) => (
                    <PaperPill key={p.doi + i} paper={p} type="added" />
                  ))}
                </div>
              </div>
            )}

            {/* Excluded papers */}
            {excludedPapers.length > 0 && (
              <div style={{
                borderRadius: '12px',
                border: '1px solid rgba(255,71,87,0.14)',
                overflow: 'hidden',
              }}>
                <div style={{
                  padding: '10px 12px',
                  background: 'rgba(255,71,87,0.05)',
                  borderBottom: '1px solid rgba(255,71,87,0.1)',
                  display: 'flex', alignItems: 'center', gap: '7px',
                }}>
                  <XCircle size={12} color="#ff4757" />
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#ff4757' }}>
                    Excluded ({excludedPapers.length})
                  </span>
                </div>
                <div style={{ padding: '8px', display: 'flex', flexDirection: 'column', gap: '5px', maxHeight: '180px', overflowY: 'auto' }}>
                  {excludedPapers.map((p, i) => (
                    <PaperPill key={p.doi + i} paper={p} type="excluded" />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ═══════════════════════════════════ CENTRE: Graph Visualization ═══ */}
          <div ref={graphContainerRef}>
            <GraphViz
              nodes={graphNodes}
              edges={graphEdges}
              highlightedDois={highlightedDois}
              onNodeClick={node => {
                if (node.id) window.open(`/paper/${encodeURIComponent(node.id)}`, '_blank');
              }}
              width={graphWidth || 600}
              height={520}
            />

            {/* Legend */}
            {graphNodes.length > 0 && (
              <div style={{
                marginTop: '10px', padding: '10px 14px', borderRadius: '10px',
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.05)',
                display: 'flex', alignItems: 'center', gap: '18px', flexWrap: 'wrap',
              }}>
                {[
                  { color: '#00e676', label: 'Trusted node' },
                  { color: '#ffd166', label: 'Caution node' },
                  { color: 'rgba(77,136,255,0.7)', label: 'Cites →' },
                  { color: 'rgba(255,255,255,0.2)', label: 'Shares topic' },
                ].map(l => (
                  <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: l.color }} />
                    <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)' }}>{l.label}</span>
                  </div>
                ))}
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.2)', marginLeft: 'auto' }}>
                  Click node to open paper · Drag to explore
                </span>
              </div>
            )}
          </div>

          {/* ═══════════════════════════════════════ RIGHT: Query panel ═══ */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

            {/* Query input */}
            <div style={{
              padding: '16px', borderRadius: '14px',
              background: 'rgba(255,255,255,0.025)',
              border: '1px solid rgba(255,255,255,0.07)',
            }}>
              <p style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: '10px' }}>
                Ask the Graph
              </p>

              {graphNodes.length === 0 ? (
                <div style={{
                  padding: '20px', borderRadius: '10px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px dashed rgba(255,255,255,0.07)',
                  textAlign: 'center',
                }}>
                  <BookOpen size={22} style={{ color: 'rgba(255,255,255,0.15)', marginBottom: '8px' }} />
                  <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.25)', margin: 0, lineHeight: 1.5 }}>
                    Add papers to the graph first, then ask research questions here.
                  </p>
                </div>
              ) : (
                <>
                  <textarea
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="e.g. What is the RR for major cardiovascular events?"
                    rows={3}
                    style={{
                      width: '100%', boxSizing: 'border-box',
                      padding: '10px', borderRadius: '8px', resize: 'vertical',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.09)',
                      color: 'rgba(255,255,255,0.82)', fontSize: '12px', lineHeight: 1.5,
                      outline: 'none', fontFamily: 'inherit',
                    }}
                  />
                  <p style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', margin: '4px 0 8px', textAlign: 'right' }}>
                    ⌘↵ to send
                  </p>
                  <button
                    onClick={handleQuery}
                    disabled={querying || !question.trim()}
                    style={{
                      width: '100%',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '7px',
                      padding: '10px', borderRadius: '9px',
                      background: querying || !question.trim()
                        ? 'rgba(0,230,118,0.08)'
                        : 'linear-gradient(135deg, rgba(0,230,118,0.2), rgba(77,136,255,0.15))',
                      border: `1px solid ${querying || !question.trim() ? 'rgba(0,230,118,0.1)' : 'rgba(0,230,118,0.3)'}`,
                      color: querying || !question.trim() ? 'rgba(255,255,255,0.25)' : '#00e676',
                      fontSize: '12px', fontWeight: 600, cursor: querying ? 'wait' : 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
                    {querying
                      ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Querying graph…</>
                      : <><Send size={13} /> Ask Trusted Literature</>
                    }
                  </button>
                </>
              )}
            </div>

            {/* Answers */}
            <AnimatePresence>
              {answers.map((a, i) => (
                <AnswerCard
                  key={i}
                  answer={a.answer}
                  papersUsed={a.papersUsed}
                  tookSeconds={a.tookSeconds}
                  highlightedDois={highlightedDois}
                  onHighlight={setHighlightedDois}
                />
              ))}
            </AnimatePresence>

            {answers.length === 0 && graphNodes.length > 0 && (
              <div style={{
                padding: '20px', borderRadius: '12px',
                background: 'rgba(77,136,255,0.04)',
                border: '1px dashed rgba(77,136,255,0.12)',
                textAlign: 'center',
              }}>
                <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.25)', margin: 0, lineHeight: 1.6 }}>
                  {graphNodes.length} trusted paper{graphNodes.length !== 1 ? 's' : ''} ready.<br />
                  Ask a research question to get an LLM answer grounded only in your credible graph.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
