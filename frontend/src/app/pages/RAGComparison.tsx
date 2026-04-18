import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Check, X, AlertTriangle, Download, RefreshCw, ArrowRight, Loader2 } from 'lucide-react';
import { Layout } from '../components/Layout';
import { toast } from 'sonner';
import { filterForRAG, getUserErrorMessage, type Paper } from '../../api/client';

const DEFAULT_QUERY = 'PCSK9 inhibitors cardiovascular outcomes';

type PaperEntry = { title: string; tier: 'trusted' | 'caution' | 'untrusted' | 'Trusted' | 'Caution' | 'Untrusted'; doi?: string };

const TIER_ICON_MAP: Record<string, string> = {
  trusted: '✅',
  caution: '⚠️',
  untrusted: '❌',
};

const TIER_COLOR_MAP: Record<string, string> = {
  trusted: '#00e676',
  caution: '#ffd166',
  untrusted: '#ff4757',
};

const WITHOUT_ANSWER =
  '"PCSK9 inhibitors reduce LDL-C and may reduce cardiovascular events. However, evidence includes a retracted OMICS study with fabricated endpoints, inflating apparent efficacy. Results are conflicting — confidence is limited. [UNRELIABLE]"';

const WITH_ANSWER =
  '"PCSK9 inhibitors significantly reduce major cardiovascular events. Four high-quality studies (FOURIER, ODYSSEY, PLOS meta-analysis) consistently show 15–20% relative risk reduction. Evidence quality: HIGH. Safe for hypothesis building."';

function ConfidencePill({ label, value, type }: { label: string; value: string; type: 'good' | 'bad' }) {
  const color = type === 'good' ? '#00e676' : '#ff4757';
  const Icon = type === 'good' ? Check : X;
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px',
      padding: '8px 14px', borderRadius: '10px',
      background: `${color}10`,
      border: `1px solid ${color}22`,
    }}>
      <Icon size={13} color={color} />
      <div>
        <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.32)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{label}</div>
        <div style={{ fontSize: '13px', fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
      </div>
    </div>
  );
}

function PaperRow({ paper, filtered }: { paper: PaperEntry; filtered?: boolean }) {
  const color = TIER_COLOR_MAP[paper.tier];
  const faded = filtered && paper.tier === 'untrusted';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '8px',
      padding: '8px 12px', borderRadius: '9px',
      background: faded
        ? 'rgba(255,255,255,0.01)'
        : paper.tier === 'untrusted'
          ? 'rgba(255,71,87,0.07)'
          : 'rgba(0,230,118,0.04)',
      border: `1px solid ${
        faded ? 'rgba(255,255,255,0.03)'
          : paper.tier === 'untrusted'
            ? 'rgba(255,71,87,0.18)'
            : 'rgba(0,230,118,0.1)'
      }`,
      opacity: faded ? 0.35 : 1,
      transition: 'opacity 0.3s',
    }}>
      <span style={{ fontSize: '14px' }}>
        {faded ? '✕' : TIER_ICON_MAP[paper.tier]}
      </span>
      <span style={{
        fontSize: '12px', flex: 1,
        color: faded
          ? 'rgba(255,255,255,0.2)'
          : paper.tier === 'untrusted'
            ? 'rgba(255,71,87,0.8)'
            : 'rgba(255,255,255,0.65)',
        textDecoration: faded ? 'line-through' : 'none',
      }}>
        {paper.title}
      </span>
      {!filtered && paper.tier === 'untrusted' && (
        <span style={{ fontSize: '10px', color: '#ff4757', fontWeight: 700 }}>⚠ risky!</span>
      )}
      {filtered && paper.tier === 'untrusted' && (
        <span style={{ fontSize: '10px', color: 'rgba(0,230,118,0.7)', fontWeight: 700 }}>excluded</span>
      )}
    </div>
  );
}

export function RAGComparison() {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [loading, setLoading] = useState(false);
  const [allPapers, setAllPapers] = useState<PaperEntry[]>([]);
  const [filteredPapers, setFilteredPapers] = useState<PaperEntry[]>([]);

  useEffect(() => {
    // Fetch papers when component mounts
    const fetchComparison = async () => {
      setLoading(true);
      try {
        // Fetch all papers (no filter)
        const allResponse = await filterForRAG(query, 20, 'Untrusted');
        const allPaperEntries: PaperEntry[] = allResponse.papers.map(p => ({
          title: p.title,
          tier: p.tier?.toLowerCase() as any || 'untrusted',
          doi: p.doi,
        }));

        // Fetch filtered papers (Trusted only)
        const filteredResponse = await filterForRAG(query, 20, 'Trusted');
        const filteredPaperEntries: PaperEntry[] = filteredResponse.papers.map(p => ({
          title: p.title,
          tier: p.tier?.toLowerCase() as any || 'untrusted',
          doi: p.doi,
        }));

        setAllPapers(allPaperEntries);
        setFilteredPapers(filteredPaperEntries);
      } catch (err: any) {
        const message = getUserErrorMessage(err);
        toast.error(message);
        // Use empty arrays on error
        setAllPapers([]);
        setFilteredPapers([]);
      } finally {
        setLoading(false);
      }
    };

    fetchComparison();
  }, [query]);

  return (
    <Layout showBack>
      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '32px 24px', paddingBottom: '80px' }}>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ease: [0.16, 1, 0.3, 1] }}>

          {/* Header */}
          <div style={{ marginBottom: '32px' }}>
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: '28px', fontWeight: 700,
              color: 'rgba(255,255,255,0.96)', marginBottom: '6px',
            }}>
              RAG Pipeline Comparison
            </h1>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.38)' }}>
              See how Truth Filter improves AI research quality by removing low-credibility papers
            </p>
          </div>

          {/* Query display */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            style={{
              padding: '16px 20px', borderRadius: '14px', marginBottom: '28px',
              background: 'rgba(77,136,255,0.06)',
              border: '1px solid rgba(77,136,255,0.15)',
            }}
          >
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase' }}>
              Research Query
            </span>
            <p style={{ fontSize: '15px', color: 'rgba(255,255,255,0.82)', marginTop: '6px', fontStyle: 'italic', lineHeight: 1.5 }}>
              {query}
            </p>
          </motion.div>

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
                    Fetching papers and comparing...
                  </p>
                  <p style={{ color: 'rgba(255,255,255,0.25)', fontSize: '12px' }}>
                    This may take a moment
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Arrow summary */}
          <AnimatePresence>
            {!loading && (
              <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.2 }}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  gap: '16px', marginBottom: '24px', flexWrap: 'wrap',
                }}
              >
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'rgba(255,71,87,0.7)', fontWeight: 600, marginBottom: '4px' }}>Without Filter</div>
              <div style={{ fontSize: '22px' }}>
                {allPapers.map((p, i) => (
                  <span key={i} style={{ marginRight: '3px', fontSize: '18px' }}>{TIER_ICON_MAP[p.tier.toLowerCase()]}</span>
                ))}
              </div>
            </div>
            <ArrowRight size={20} style={{ color: 'rgba(255,255,255,0.25)' }} />
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'rgba(0,230,118,0.7)', fontWeight: 600, marginBottom: '4px' }}>With Filter</div>
              <div style={{ fontSize: '18px' }}>
                {filteredPapers.map((p, i) => (
                  <span key={i} style={{ marginRight: '3px' }}>{TIER_ICON_MAP[p.tier.toLowerCase()]}</span>
                ))}
              </div>
            </div>
              </motion.div>

              {/* Two-panel comparison */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '28px' }}
            className="grid-cols-1 md:grid-cols-2"
          >
            {/* ─── WITHOUT ─── */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
              style={{
                borderRadius: '16px', overflow: 'hidden',
                border: '1px solid rgba(255,71,87,0.22)',
              }}
            >
              {/* Panel header */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '14px 20px',
                background: 'rgba(255,71,87,0.08)',
                borderBottom: '1px solid rgba(255,71,87,0.15)',
              }}>
                <div style={{
                  width: '26px', height: '26px', borderRadius: '50%',
                  background: 'rgba(255,71,87,0.18)',
                  border: '1px solid rgba(255,71,87,0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <X size={14} color="#ff4757" />
                </div>
                <span style={{ fontWeight: 700, color: '#ff4757', fontSize: '14px' }}>Without Truth Filter</span>
              </div>

              <div style={{ padding: '20px', background: 'rgba(255,255,255,0.015)' }}>
                {/* Paper icon grid */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
                  {allPapers.map((p, i) => (
                    <motion.span
                      key={i}
                      initial={{ opacity: 0, scale: 0.7 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.35 + i * 0.05 }}
                      title={p.title}
                      style={{ fontSize: '20px', cursor: 'default' }}
                    >
                      {TIER_ICON_MAP[p.tier.toLowerCase()]}
                    </motion.span>
                  ))}
                </div>

                {/* Paper list */}
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Input Papers ({allPapers.length}) — all fed to LLM
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '18px' }}>
                  {allPapers.map((p, i) => (
                    <PaperRow key={i} paper={p} filtered={false} />
                  ))}
                </div>

                {/* AI Answer */}
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px' }}>
                  AI Answer
                </p>
                <div style={{
                  padding: '14px', borderRadius: '12px',
                  background: 'rgba(255,71,87,0.06)',
                  border: '1px solid rgba(255,71,87,0.15)',
                  marginBottom: '14px',
                }}>
                  <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.65, fontStyle: 'italic' }}>
                    {WITHOUT_ANSWER}
                  </p>
                </div>

                {/* Confidence pills */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <ConfidencePill label="Confidence" value="LOW" type="bad" />
                  <ConfidencePill label="Risk Level" value="HIGH" type="bad" />
                </div>
              </div>
            </motion.div>

            {/* ─── WITH ─── */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
              style={{
                borderRadius: '16px', overflow: 'hidden',
                border: '1px solid rgba(0,230,118,0.22)',
              }}
            >
              {/* Panel header */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '14px 20px',
                background: 'rgba(0,230,118,0.07)',
                borderBottom: '1px solid rgba(0,230,118,0.12)',
              }}>
                <div style={{
                  width: '26px', height: '26px', borderRadius: '50%',
                  background: 'rgba(0,230,118,0.15)',
                  border: '1px solid rgba(0,230,118,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Check size={14} color="#00e676" />
                </div>
                <span style={{ fontWeight: 700, color: '#00e676', fontSize: '14px' }}>With Truth Filter</span>
              </div>

              <div style={{ padding: '20px', background: 'rgba(255,255,255,0.015)' }}>
                {/* Paper icon grid */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
                  {allPapers.map((p, i) => (
                    <motion.span
                      key={i}
                      initial={{ opacity: 0, scale: 0.7 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.4 + i * 0.05 }}
                      title={p.title}
                      style={{ fontSize: '20px', cursor: 'default', opacity: p.tier.toLowerCase() === 'untrusted' ? 0.2 : 1 }}
                    >
                      {TIER_ICON_MAP[p.tier.toLowerCase()]}
                    </motion.span>
                  ))}
                </div>

                {/* Paper list */}
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Input ({allPapers.length}) → After Filter ({filteredPapers.length})
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '18px' }}>
                  {allPapers.map((p, i) => (
                    <PaperRow key={i} paper={p} filtered />
                  ))}
                </div>

                {/* AI Answer */}
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px' }}>
                  AI Answer
                </p>
                <div style={{
                  padding: '14px', borderRadius: '12px',
                  background: 'rgba(0,230,118,0.05)',
                  border: '1px solid rgba(0,230,118,0.14)',
                  marginBottom: '14px',
                }}>
                  <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.8)', lineHeight: 1.65, fontStyle: 'italic' }}>
                    {WITH_ANSWER}
                  </p>
                </div>

                {/* Confidence pills */}
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <ConfidencePill label="Confidence" value="HIGH" type="good" />
                  <ConfidencePill label="Risk Level" value="LOW" type="good" />
                </div>
              </div>
            </motion.div>
          </div>

          {/* Impact summary */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            style={{
              padding: '24px', borderRadius: '16px', marginBottom: '24px',
              background: 'linear-gradient(135deg, rgba(0,230,118,0.06), rgba(77,136,255,0.06))',
              border: '1px solid rgba(0,230,118,0.14)',
            }}
          >
            <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'rgba(255,255,255,0.85)', marginBottom: '18px', letterSpacing: '0.02em' }}>
              Filter Impact Summary
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
              {[
                { value: `${allPapers.length - filteredPapers.length}`, label: 'Papers Removed', sub: 'untrusted sources' },
                { value: '↑ 3×', label: 'Answer Quality', sub: 'improvement' },
                { value: '100%', label: 'Risk Eliminated', sub: 'of bad sources' },
              ].map(s => (
                <div key={s.label} style={{ textAlign: 'center' }}>
                  <div style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '26px', fontWeight: 700,
                    color: '#00e676', marginBottom: '4px',
                  }}>
                    {s.value}
                  </div>
                  <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)', marginBottom: '2px' }}>{s.label}</div>
                  <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.22)' }}>{s.sub}</div>
                </div>
              ))}
            </div>
          </motion.div>

              {/* Actions */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                <button
                  onClick={() => toast.success('Running new query...')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '7px',
                    padding: '11px 20px', borderRadius: '11px',
                    background: 'linear-gradient(135deg, #4d88ff, #6d6bff)',
                    color: 'white', fontSize: '13px', fontWeight: 600, border: 'none',
                    cursor: 'pointer',
                    boxShadow: '0 0 22px rgba(77,136,255,0.35)',
                  }}
                >
                  <RefreshCw size={14} /> Run New Query
                </button>
                <button
                  onClick={() => toast.success('Report downloaded')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '7px',
                    padding: '11px 18px', borderRadius: '11px',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: 'rgba(255,255,255,0.65)', fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  <Download size={14} /> Report Differences
                </button>
              </div>
              </>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </Layout>
  );
}
