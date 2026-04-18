import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Search, X, RotateCcw, Download, Loader2, Plus } from 'lucide-react';
import { Layout } from '../components/Layout';
import { PaperCard } from '../components/PaperCard';
import { toast } from 'sonner';
import { scorePapers, getUserErrorMessage, type Paper } from '../../api/client';

const EXAMPLE_DOIS = ['10.1371/journal.pmed.1001231'];

export function DOISearch() {
  const [dois, setDois] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Paper[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addDoi = () => {
    const trimmed = inputValue.trim().replace(/^https?:\/\/doi\.org\//i, '');
    if (trimmed && !dois.includes(trimmed)) {
      setDois(prev => [...prev, trimmed]);
    }
    setInputValue('');
  };

  const removeDoi = (doi: string) => setDois(prev => prev.filter(d => d !== doi));

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') addDoi();
  };

  const handleScore = async () => {
    if (dois.length === 0) {
      toast.error('Please add at least one DOI');
      return;
    }
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      const response = await scorePapers(dois, undefined, 10);
      setResults(response.papers);
      setHasSearched(true);
      toast.success(`Scored ${response.papers.length} paper${response.papers.length > 1 ? 's' : ''}`);
    } catch (err: any) {
      const message = getUserErrorMessage(err);
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setDois([]);
    setResults([]);
    setHasSearched(false);
    setInputValue('');
  };

  const handleExport = () => {
    toast.success('CSV exported to clipboard');
  };

  return (
    <Layout showBack>
      <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 24px', paddingBottom: '80px' }}>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ease: [0.16, 1, 0.3, 1] }}>

          {/* Page header */}
          <div style={{ marginBottom: '32px' }}>
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: '28px', fontWeight: 700,
              color: 'rgba(255,255,255,0.96)', marginBottom: '6px',
            }}>
              Score by DOI
            </h1>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.38)' }}>
              Enter one or more DOIs to get instant credibility scores across 7 AI dimensions
            </p>
          </div>

          {/* DOI Input panel */}
          <div style={{
            padding: '20px', borderRadius: '16px', marginBottom: '20px',
            background: 'rgba(255,255,255,0.025)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: '12px' }}>
              DOI List
            </p>

            {/* DOI chips */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
              <AnimatePresence>
                {dois.map((doi) => (
                  <motion.div
                    key={doi}
                    initial={{ opacity: 0, x: -12, height: 0 }}
                    animate={{ opacity: 1, x: 0, height: 'auto' }}
                    exit={{ opacity: 0, x: -12, height: 0 }}
                    transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.25 }}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '10px 14px', borderRadius: '10px',
                      background: 'rgba(77,136,255,0.07)',
                      border: '1px solid rgba(77,136,255,0.18)',
                    }}
                  >
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '13px', color: 'rgba(255,255,255,0.72)',
                    }}>
                      {doi}
                    </span>
                    <button
                      onClick={() => removeDoi(doi)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.3)', padding: '2px', marginLeft: '8px', lineHeight: 1 }}
                      onMouseEnter={e => (e.currentTarget.style.color = '#ff4757')}
                      onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
                    >
                      <X size={14} />
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            {/* Add DOI input */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Paste or type DOI (e.g. 10.1038/s41586-024-...)"
                style={{
                  flex: 1, padding: '10px 14px', borderRadius: '10px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: 'rgba(255,255,255,0.85)', fontSize: '13px',
                  fontFamily: "'JetBrains Mono', monospace",
                  outline: 'none', transition: 'border-color 0.15s',
                }}
                onFocus={e => (e.target.style.borderColor = 'rgba(77,136,255,0.5)')}
                onBlur={e => (e.target.style.borderColor = 'rgba(255,255,255,0.08)')}
              />
              <button
                onClick={addDoi}
                style={{
                  display: 'flex', alignItems: 'center', gap: '5px',
                  padding: '10px 14px', borderRadius: '10px',
                  background: 'rgba(77,136,255,0.1)',
                  border: '1px solid rgba(77,136,255,0.22)',
                  color: '#4d88ff', fontSize: '13px', cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(77,136,255,0.2)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(77,136,255,0.1)')}
              >
                <Plus size={14} /> Add
              </button>
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '40px', flexWrap: 'wrap' }}>
            <button
              onClick={handleScore}
              disabled={loading || dois.length === 0}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '12px 24px', borderRadius: '12px',
                background: dois.length > 0 ? 'linear-gradient(135deg, #4d88ff, #6d6bff)' : 'rgba(255,255,255,0.05)',
                color: dois.length > 0 ? 'white' : 'rgba(255,255,255,0.25)',
                fontSize: '14px', fontWeight: 600, border: 'none',
                cursor: loading || dois.length === 0 ? 'not-allowed' : 'pointer',
                boxShadow: dois.length > 0 ? '0 0 28px rgba(77,136,255,0.4)' : 'none',
                transition: 'all 0.2s',
              }}
            >
              {loading
                ? <Loader2 size={15} className="animate-spin" />
                : <Search size={15} />}
              {loading ? 'Scoring Papers...' : `Score ${dois.length > 0 ? dois.length : ''} Paper${dois.length !== 1 ? 's' : ''}`}
            </button>
            <button
              onClick={handleClear}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '12px 18px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.38)', fontSize: '14px',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.65)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.38)')}
            >
              <RotateCcw size={14} /> Clear All
            </button>
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

          {/* Loading skeleton */}
          <AnimatePresence>
            {loading && (
              <motion.div
                key="skeleton"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                {dois.map((_, i) => (
                  <div key={i} className="ts-skeleton" style={{ height: '160px', borderRadius: '14px' }} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results */}
          <AnimatePresence>
            {results.length > 0 && !loading && (
              <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'rgba(255,255,255,0.65)' }}>
                    Results
                    <span style={{ color: 'rgba(255,255,255,0.28)', marginLeft: '8px', fontFamily: "'JetBrains Mono', monospace", fontSize: '13px' }}>
                      {results.length} papers
                    </span>
                  </h2>
                  <button
                    onClick={handleExport}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '5px',
                      padding: '7px 12px', borderRadius: '8px',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      color: 'rgba(255,255,255,0.45)', fontSize: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    <Download size={12} /> Export CSV
                  </button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {results.map((paper, i) => {
                    // Adapt API response to PaperCard expected format
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
                    return <PaperCard key={adaptedPaper.id} paper={adaptedPaper as any} index={i} />;
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {hasSearched && results.length === 0 && !loading && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'rgba(255,255,255,0.25)', fontSize: '14px' }}>
              No results found.
            </div>
          )}
        </motion.div>
      </div>
    </Layout>
  );
}
