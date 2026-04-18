import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, Filter, Download, GitCompare, Loader2, Network } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router';
import { Layout } from '../components/Layout';
import { PaperCard } from '../components/PaperCard';
import { Tier } from '../data/mockData';
import { toast } from 'sonner';
import { filterForRAG, getUserErrorMessage, type Paper } from '../../api/client';

type TopK = '5' | '10' | '20' | '50';
type MinTier = 'any' | 'caution' | 'trusted';

const TIER_ORDER: Tier[] = ['trusted', 'caution', 'untrusted'];
const TIER_LABELS: Record<Tier, string> = { trusted: 'Trusted', caution: 'Caution', untrusted: 'Untrusted' };
const TIER_ICONS: Record<Tier, string> = { trusted: '✅', caution: '⚠️', untrusted: '❌' };
const TIER_COLORS: Record<Tier, string> = { trusted: '#00e676', caution: '#ffd166', untrusted: '#ff4757' };

const EXAMPLE_QUERIES = [
  'GLP-1 receptor agonists in metabolic disease',
  'PCSK9 inhibitors cardiovascular outcomes',
  'CRISPR off-target effects stem cells',
];

const SelectStyle: React.CSSProperties = {
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '9px',
  padding: '7px 10px',
  color: 'rgba(255,255,255,0.72)',
  fontSize: '13px',
  outline: 'none',
  cursor: 'pointer',
};

export function QuerySearch() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState<TopK>('20');
  const [minTier, setMinTier] = useState<MinTier>('any');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Paper[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Pre-fill query from landing page recent search click
  useEffect(() => {
    if ((location.state as any)?.prefill) {
      setQuery((location.state as any).prefill);
    }
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error('Please enter a search query');
      return;
    }
    setLoading(true);
    setError(null);
    setResults([]);
    setSelected(new Set());
    try {
      const tierMap = { any: 'Untrusted', caution: 'Caution', trusted: 'Trusted' } as const;
      const response = await filterForRAG(query, parseInt(topK), tierMap[minTier]);
      setResults(response.papers);
      setHasSearched(true);
      toast.success(`Found ${response.papers.length} papers for scoring`);
      // Save to search history for landing page
      try {
        const entry = { id: Date.now().toString(), query: query.trim(), paperCount: response.papers.length, date: new Date().toISOString().slice(0, 10) };
        const existing = JSON.parse(localStorage.getItem('ts_search_history') || '[]');
        const deduped = [entry, ...existing.filter((e: any) => e.query !== query.trim())].slice(0, 5);
        localStorage.setItem('ts_search_history', JSON.stringify(deduped));
      } catch {}
    } catch (err: any) {
      const message = getUserErrorMessage(err);
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  // Results are already filtered by the API, but we need to group by tier for display
  const groupedResults = TIER_ORDER.map(tier => {
    const tierLowercase = tier as 'trusted' | 'caution' | 'untrusted';
    return {
      tier,
      papers: results.filter(p => p.tier?.toLowerCase?.() === tierLowercase || p.tier === tier),
    };
  }).filter(g => g.papers.length > 0);

  const toggleSelect = (id: string) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
  };

  const handleSendToReview = () => {
    const selectedDois = results
      .filter(p => selected.has(p.doi || ''))
      .map(p => p.doi)
      .filter(Boolean) as string[];
    sessionStorage.setItem('ts_review_seed_dois', JSON.stringify(selectedDois));
    navigate('/review');
  };

  return (
    <Layout showBack>
      <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 24px', paddingBottom: '80px' }}>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ease: [0.16, 1, 0.3, 1] }}>

          {/* Header */}
          <div style={{ marginBottom: '32px' }}>
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: '28px', fontWeight: 700,
              color: 'rgba(255,255,255,0.96)', marginBottom: '6px',
            }}>
              Search Literature
            </h1>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.38)' }}>
              Retrieve and score papers from PubMed &amp; bioRxiv in real-time
            </p>
          </div>

          {/* Search input */}
          <div style={{ position: 'relative', marginBottom: '16px' }}>
            <Search size={17} style={{
              position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)',
              color: 'rgba(255,255,255,0.28)',
            }} />
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="e.g. GLP-1 receptor agonists in metabolic disease..."
              style={{
                width: '100%', padding: '14px 16px 14px 46px',
                borderRadius: '14px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.9)', fontSize: '15px',
                outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s',
                boxSizing: 'border-box',
              }}
              onFocus={e => {
                e.target.style.borderColor = 'rgba(77,136,255,0.5)';
                e.target.style.boxShadow = '0 0 0 2px rgba(77,136,255,0.12)';
              }}
              onBlur={e => {
                e.target.style.borderColor = 'rgba(255,255,255,0.1)';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Example queries */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '18px' }}>
            {EXAMPLE_QUERIES.map(q => (
              <button
                key={q}
                onClick={() => setQuery(q)}
                style={{
                  padding: '4px 10px', borderRadius: '6px', fontSize: '11px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.7)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.15)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.08)';
                }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Filters row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', marginBottom: '20px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'rgba(255,255,255,0.3)' }}>
              <Filter size={13} /> Filters
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'rgba(255,255,255,0.38)', fontWeight: 500 }}>Top-K:</label>
              <select value={topK} onChange={e => setTopK(e.target.value as TopK)} style={SelectStyle}>
                {['5', '10', '20', '50'].map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'rgba(255,255,255,0.38)', fontWeight: 500 }}>Min Tier:</label>
              <select value={minTier} onChange={e => setMinTier(e.target.value as MinTier)} style={SelectStyle}>
                <option value="any">Any</option>
                <option value="caution">Caution+</option>
                <option value="trusted">Trusted Only</option>
              </select>
            </div>
          </div>

          {/* Search button */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '40px' }}>
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim()}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '12px 26px', borderRadius: '12px',
                background: query.trim() ? 'linear-gradient(135deg, #4d88ff, #6d6bff)' : 'rgba(255,255,255,0.05)',
                color: query.trim() ? 'white' : 'rgba(255,255,255,0.25)',
                fontSize: '14px', fontWeight: 600, border: 'none',
                cursor: loading || !query.trim() ? 'not-allowed' : 'pointer',
                boxShadow: query.trim() ? '0 0 28px rgba(77,136,255,0.4)' : 'none',
              }}
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
              {loading ? 'Searching & Scoring...' : 'Search Papers'}
            </button>
            {hasSearched && (
              <button
                onClick={() => navigate('/rag')}
                style={{
                  display: 'flex', alignItems: 'center', gap: '7px',
                  padding: '12px 18px', borderRadius: '12px',
                  background: 'rgba(255,209,102,0.1)',
                  border: '1px solid rgba(255,209,102,0.22)',
                  color: '#ffd166', fontSize: '14px',
                  cursor: 'pointer',
                }}
              >
                <GitCompare size={14} /> RAG Compare
              </button>
            )}
          </div>

          {/* Error message */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              style={{
                padding: '12px 16px',
                borderRadius: '12px',
                background: 'rgba(255, 71, 87, 0.1)',
                border: '1px solid rgba(255, 71, 87, 0.3)',
                color: '#ff4757',
                fontSize: '14px',
                marginBottom: '20px',
              }}
            >
              {error}
            </motion.div>
          )}

          {/* Loading state */}
          <AnimatePresence>
            {loading && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '64px 0', gap: '20px' }}
              >
                <div style={{
                  width: '52px', height: '52px', borderRadius: '50%',
                  border: '2px solid rgba(77,136,255,0.12)',
                  borderTop: '2px solid #4d88ff',
                }} className="ts-spinner" />
                <div style={{ textAlign: 'center' }}>
                  <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '14px', marginBottom: '4px' }}>
                    Retrieving papers and running credibility analysis...
                  </p>
                  <p style={{ color: 'rgba(255,255,255,0.25)', fontSize: '12px' }}>
                    7 AI agents running in parallel
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results */}
          <AnimatePresence>
            {hasSearched && !loading && (
              <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                {/* Summary bar */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
                  <div>
                    <span style={{ fontSize: '15px', fontWeight: 600, color: 'rgba(255,255,255,0.65)' }}>
                      {results.length} qualifying papers
                    </span>
                    {selected.size > 0 && (
                      <span style={{ fontSize: '13px', color: '#4d88ff', marginLeft: '10px' }}>
                        · {selected.size} selected
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => toast.success('Full report downloaded')}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '5px',
                      padding: '7px 12px', borderRadius: '8px',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      color: 'rgba(255,255,255,0.4)', fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    <Download size={12} /> Download Report
                  </button>
                </div>

                {/* Tier groups */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                  {groupedResults.map(({ tier, papers }) => (
                    <div key={tier}>
                      {/* Section header */}
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '8px',
                        marginBottom: '14px', paddingBottom: '10px',
                        borderBottom: `1px solid ${TIER_COLORS[tier]}20`,
                      }}>
                        <span style={{ fontSize: '16px' }}>{TIER_ICONS[tier]}</span>
                        <span style={{
                          fontSize: '12px', fontWeight: 700,
                          color: TIER_COLORS[tier],
                          letterSpacing: '0.07em', textTransform: 'uppercase',
                        }}>
                          {TIER_LABELS[tier]}
                        </span>
                        <span style={{
                          fontSize: '12px', color: 'rgba(255,255,255,0.28)',
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          ({papers.length})
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {papers.map((paper, i) => {
                          const adaptedPaper = {
                            ...paper,
                            id: paper.doi || `paper-${i}`,
                            tier: paper.tier?.toLowerCase() as any || 'untrusted',
                            hardFlags: Array.isArray(paper.hard_flags) ? paper.hard_flags : [],
                            softFlags: Array.isArray(paper.soft_flags) ? paper.soft_flags : [],
                            qualitySignals: Array.isArray(paper.quality_signals) ? paper.quality_signals : [],
                            authors: paper.authors?.join(', ') || '',
                            score: paper.score || paper.composite_score || 0,
                          };
                          return (
                            <PaperCard
                              key={adaptedPaper.id}
                              paper={adaptedPaper as any}
                              index={i}
                              selected={selected.has(adaptedPaper.id)}
                              onSelect={toggleSelect}
                              showCheckbox
                            />
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>

                {results.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '64px 0' }}>
                    <p style={{ color: 'rgba(255,255,255,0.28)', fontSize: '14px', marginBottom: '8px' }}>
                      No papers match the current filter.
                    </p>
                    <p style={{ color: 'rgba(255,255,255,0.18)', fontSize: '12px' }}>
                      Try lowering the minimum tier to &ldquo;Any&rdquo;.
                    </p>
                  </div>
                )}

                {/* Sticky "Add to Knowledge Graph" bar */}
                {selected.size > 0 && (
                  <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      position: 'sticky', bottom: '72px',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '12px 18px', borderRadius: '14px', marginTop: '20px',
                      background: 'rgba(0,230,118,0.08)',
                      border: '1px solid rgba(0,230,118,0.25)',
                      backdropFilter: 'blur(12px)',
                    }}
                  >
                    <span style={{ fontSize: '13px', color: '#00e676', fontWeight: 600 }}>
                      {selected.size} paper{selected.size !== 1 ? 's' : ''} selected
                    </span>
                    <button
                      onClick={handleSendToReview}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '7px',
                        padding: '9px 16px', borderRadius: '9px',
                        background: 'linear-gradient(135deg, rgba(0,230,118,0.2), rgba(77,136,255,0.15))',
                        border: '1px solid rgba(0,230,118,0.3)', color: '#00e676',
                        fontSize: '12px', fontWeight: 600, cursor: 'pointer',
                      }}
                    >
                      <Network size={14} /> Add to Knowledge Graph
                    </button>
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </Layout>
  );
}
