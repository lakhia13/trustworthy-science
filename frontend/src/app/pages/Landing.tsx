import { motion } from 'motion/react';
import { useNavigate } from 'react-router';
import { Search, FileSearch, Upload, GitCompare, ChevronRight, Clock, Zap, Shield, BarChart3 } from 'lucide-react';
import { Layout } from '../components/Layout';
import { RECENT_SEARCHES } from '../data/mockData';

const FEATURES = [
  {
    icon: Search,
    title: 'Score by DOI',
    description: 'Paste one or more DOIs to get credibility scores, flags, and per-dimension breakdown in seconds.',
    color: '#4d88ff',
    to: '/doi',
  },
  {
    icon: FileSearch,
    title: 'Search by Query',
    description: 'Ask a research question — we retrieve papers from PubMed & bioRxiv and score them automatically.',
    color: '#a78bfa',
    to: '/query',
  },
  {
    icon: Upload,
    title: 'Bulk Upload',
    description: 'Upload a CSV of up to 500 papers. Download a filtered, scored dataset instantly.',
    color: '#00e676',
    to: '/doi',
  },
  {
    icon: GitCompare,
    title: 'RAG Comparison',
    description: 'See exactly how Truth Filter improves your AI pipeline output — side-by-side.',
    color: '#ffd166',
    to: '/rag',
  },
];

const STATS = [
  { value: '2.4M+', label: 'Papers Scored' },
  { value: '98.2%', label: 'Detection Accuracy' },
  { value: '<2s',   label: 'Per Paper' },
  { value: '7',     label: 'AI Dimensions' },
];

const HOW = [
  { icon: Search,    title: 'Retrieve', desc: 'Fetch paper metadata, full-text, and citation graph' },
  { icon: Zap,       title: 'Analyze',  desc: '7 AI agents score statistical integrity, reproducibility & more' },
  { icon: Shield,    title: 'Classify', desc: 'Assign Trusted / Caution / Untrusted with evidence' },
  { icon: BarChart3, title: 'Explain',  desc: 'Full breakdown with flags, signals, and verdict' },
];

export function Landing() {
  const navigate = useNavigate();

  return (
    <Layout>
      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 24px', paddingBottom: '80px' }}>

        {/* ── Hero ── */}
        <div style={{ textAlign: 'center', paddingTop: '64px', paddingBottom: '56px' }}>
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '32px' }}
          >
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '8px',
              padding: '6px 14px', borderRadius: '20px',
              background: 'rgba(0,230,118,0.08)',
              border: '1px solid rgba(0,230,118,0.22)',
              color: '#00e676', fontSize: '12px', fontWeight: 600,
            }}>
              <span
                className="ts-pulse-dot"
                style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#00e676', display: 'inline-block' }}
              />
              AI Credibility Engine · Live
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: 'clamp(36px, 6.5vw, 72px)',
              lineHeight: 1.05, marginBottom: '22px',
            }}
          >
            <span style={{
              background: 'linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.85) 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              Filter Bad Science
            </span>
            <br />
            <span style={{
              background: 'linear-gradient(135deg, #4d88ff 0%, #a78bfa 60%, #4d88ff 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>
              Before It Corrupts Your AI.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18 }}
            style={{
              fontSize: '18px', color: 'rgba(255,255,255,0.45)',
              maxWidth: '540px', margin: '0 auto 44px', lineHeight: 1.65,
            }}
          >
            AI-powered credibility scoring across 7 dimensions — statistical integrity, reproducibility, citation patterns, and more. Know in seconds: Trusted, Caution, or Untrusted.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.26 }}
            style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}
          >
            <button
              onClick={() => navigate('/doi')}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '13px 26px', borderRadius: '12px',
                background: 'linear-gradient(135deg, #4d88ff 0%, #6d6bff 100%)',
                color: 'white', fontSize: '14px', fontWeight: 600,
                border: 'none', cursor: 'pointer',
                boxShadow: '0 0 36px rgba(77,136,255,0.45)',
                transition: 'box-shadow 0.2s, transform 0.15s',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = '0 0 52px rgba(77,136,255,0.65)';
                (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = '0 0 36px rgba(77,136,255,0.45)';
                (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
              }}
            >
              <Search size={15} /> Score a Paper Now
            </button>
            <button
              onClick={() => navigate('/query')}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '13px 26px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'rgba(255,255,255,0.8)', fontSize: '14px', fontWeight: 500,
                cursor: 'pointer', transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.1)';
                (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)';
                (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
              }}
            >
              Search Literature
            </button>
          </motion.div>
        </div>

        {/* ── Stats bar ── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="grid grid-cols-2 md:grid-cols-4"
          style={{
            gap: '1px',
            background: 'rgba(255,255,255,0.05)',
            borderRadius: '16px', overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.07)',
            marginBottom: '56px',
          }}
        >
          {STATS.map(({ value, label }) => (
            <div key={label} style={{ textAlign: 'center', padding: '22px 16px', background: 'rgba(6,8,15,0.8)' }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '28px', fontWeight: 700,
                color: '#4d88ff', marginBottom: '4px',
              }}>
                {value}
              </div>
              <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.38)' }}>{label}</div>
            </div>
          ))}
        </motion.div>

        {/* ── Feature cards ── */}
        <div
          className="grid grid-cols-1 md:grid-cols-2"
          style={{ gap: '16px', marginBottom: '48px' }}
        >
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i + 0.3, ease: [0.16, 1, 0.3, 1] }}
              whileHover={{ scale: 1.02, y: -3 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => navigate(f.to)}
              style={{
                padding: '24px', borderRadius: '16px',
                background: `linear-gradient(135deg, ${f.color}10 0%, rgba(255,255,255,0.02) 100%)`,
                border: '1px solid rgba(255,255,255,0.07)',
                cursor: 'pointer', position: 'relative', overflow: 'hidden',
              }}
            >
              <div style={{
                position: 'absolute', top: 0, left: '20%', right: '20%', height: '1px',
                background: `linear-gradient(90deg, transparent, ${f.color}55, transparent)`,
              }} />
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                <div style={{
                  width: '46px', height: '46px', borderRadius: '12px', flexShrink: 0,
                  background: `${f.color}15`, border: `1px solid ${f.color}28`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: `0 0 22px ${f.color}18`,
                }}>
                  <f.icon size={20} color={f.color} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '7px' }}>
                    <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'rgba(255,255,255,0.95)' }}>{f.title}</h3>
                    <ChevronRight size={15} style={{ color: 'rgba(255,255,255,0.2)' }} />
                  </div>
                  <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.42)', lineHeight: 1.55 }}>{f.description}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* ── How it works ── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          style={{ marginBottom: '48px' }}
        >
          <h2 style={{
            textAlign: 'center',
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: '20px', fontWeight: 600,
            color: 'rgba(255,255,255,0.5)',
            marginBottom: '24px', letterSpacing: '0.02em',
          }}>
            How it works
          </h2>
          <div
            className="grid grid-cols-2 md:grid-cols-4"
            style={{ gap: '12px' }}
          >
            {HOW.map((step, i) => (
              <div key={step.title} style={{
                padding: '20px 16px', borderRadius: '12px', textAlign: 'center',
                background: 'rgba(255,255,255,0.025)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  background: 'rgba(77,136,255,0.12)',
                  border: '1px solid rgba(77,136,255,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 12px',
                }}>
                  <step.icon size={17} color="#4d88ff" />
                </div>
                <div style={{
                  fontSize: '11px', fontWeight: 700, color: 'rgba(77,136,255,0.8)',
                  letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px',
                }}>
                  {String(i + 1).padStart(2, '0')} {step.title}
                </div>
                <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.36)', lineHeight: 1.5 }}>{step.desc}</p>
              </div>
            ))}
          </div>
        </motion.div>

        {/* ── Recent Searches ── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Clock size={13} style={{ color: 'rgba(255,255,255,0.3)' }} />
            <span style={{
              fontSize: '12px', color: 'rgba(255,255,255,0.3)',
              fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
            }}>
              Recent Searches
            </span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {RECENT_SEARCHES.map(s => (
              <div
                key={s.id}
                onClick={() => navigate('/query')}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '14px 18px', borderRadius: '12px',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.1)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.025)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.06)';
                }}
              >
                <div>
                  <span style={{ fontSize: '14px', color: 'rgba(255,255,255,0.72)' }}>{s.query}</span>
                  <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.28)', marginLeft: '10px' }}>
                    {s.paperCount} papers
                  </span>
                </div>
                <ChevronRight size={14} style={{ color: 'rgba(255,255,255,0.2)' }} />
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </Layout>
  );
}
