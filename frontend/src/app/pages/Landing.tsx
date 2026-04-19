import { motion } from 'motion/react';
import { useNavigate } from 'react-router';
import {
  Search, Telescope, ChevronRight,
  Shield, BarChart3, Zap, BookOpen,
  CheckCircle2, AlertTriangle, XCircle,
} from 'lucide-react';
import { Layout } from '../components/Layout';

const FEATURES = [
  {
    icon: Search,
    title: 'Score by DOI',
    description:
      'Paste one or more DOIs to get credibility scores, hard/soft flags, and a full per-dimension breakdown in seconds.',
    color: '#4d88ff',
    to: '/doi',
    cta: 'Score a Paper',
  },
  {
    icon: Telescope,
    title: 'Deep Research',
    description:
      'Enter a research question — the AI generates MeSH-validated PubMed queries, retrieves papers, scores every one, and synthesises a citation-grounded literature review.',
    color: '#a78bfa',
    to: '/deep-research',
    cta: 'Run Deep Research',
  },
];

const STATS = [
  { value: '9',     label: 'AI Agents' },
  { value: '6',     label: 'Credibility Dimensions' },
  { value: '<5s',   label: 'Per Paper' },
  { value: '3-tier', label: 'Verdict System' },
];

const HOW = [
  { icon: Search,    step: '01', title: 'Retrieve',  desc: 'Fetch metadata, full-text & citation graph from PubMed / bioRxiv / Crossref' },
  { icon: Zap,       step: '02', title: 'Analyse',   desc: '9 AI agents score statistical integrity, reproducibility, methodology & more' },
  { icon: Shield,    step: '03', title: 'Classify',  desc: 'Assign Trusted / Caution / Untrusted with evidence-backed rationale' },
  { icon: BarChart3, step: '04', title: 'Explain',   desc: 'Full breakdown: dimension bars, radar chart, flags, and AI verdict' },
];

const DIMENSIONS = [
  { label: 'Statistical Integrity',  color: '#06b6d4', desc: 'p-value clustering, effect size reporting, multiple comparisons' },
  { label: 'Reproducibility',        color: '#7c3aed', desc: 'Open data/code, replication attempts, pre-registration' },
  { label: 'Methodology',            color: '#4d88ff', desc: 'Study design, blinding, sample size, bias risk' },
  { label: 'Citation Network',       color: '#a78bfa', desc: 'Self-citation rate, retraction links, citation manipulation' },
  { label: 'Publication Metadata',   color: '#ffd166', desc: 'Journal quality, peer-review status, predatory venue detection' },
  { label: 'Retraction Watch',       color: '#00e676', desc: 'Live check against retraction databases and correction notices' },
];

const TIERS = [
  { tier: 'Trusted',   color: '#00e676', bg: 'rgba(0,230,118,0.06)',  border: 'rgba(0,230,118,0.2)',  icon: CheckCircle2, desc: 'Score ≥ 70. Safe to cite and build on.' },
  { tier: 'Caution',   color: '#ffd166', bg: 'rgba(255,209,102,0.06)', border: 'rgba(255,209,102,0.2)', icon: AlertTriangle, desc: 'Score 45–69. Verify core claims independently.' },
  { tier: 'Untrusted', color: '#ff4757', bg: 'rgba(255,71,87,0.06)',  border: 'rgba(255,71,87,0.2)',  icon: XCircle,      desc: 'Score < 45. High replication-failure risk.' },
];

export function Landing() {
  const navigate = useNavigate();

  return (
    <Layout>
      {/* Background orbs */}
      <div style={{ position: 'fixed', top: '-15%', right: '-10%', width: '700px', height: '700px', background: 'radial-gradient(circle, rgba(77,136,255,0.07) 0%, transparent 65%)', filter: 'blur(100px)', pointerEvents: 'none', zIndex: 0 }} />
      <div style={{ position: 'fixed', bottom: '-10%', left: '-8%', width: '600px', height: '600px', background: 'radial-gradient(circle, rgba(124,58,237,0.06) 0%, transparent 65%)', filter: 'blur(90px)', pointerEvents: 'none', zIndex: 0 }} />

      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 24px 100px', position: 'relative', zIndex: 10 }}>

        {/* ── Hero ── */}
        <div style={{ textAlign: 'center', paddingTop: '72px', paddingBottom: '60px' }}>

          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginBottom: '28px' }}
          >
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: '8px',
              padding: '6px 14px', borderRadius: '20px',
              background: 'rgba(0,230,118,0.08)', border: '1px solid rgba(0,230,118,0.22)',
              color: '#00e676', fontSize: '12px', fontWeight: 600,
            }}>
              <span className="ts-pulse-dot" style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#00e676', display: 'inline-block' }} />
              AI Credibility Engine · Live
            </span>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 'clamp(34px, 6vw, 68px)', lineHeight: 1.06, marginBottom: '20px' }}
          >
            <span style={{ background: 'linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.85) 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Filter Bad Science
            </span>
            <br />
            <span style={{ background: 'linear-gradient(135deg, #4d88ff 0%, #a78bfa 55%, #4d88ff 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Before It Affects Your Research.
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18 }}
            style={{ fontSize: '17px', color: 'rgba(255,255,255,0.42)', maxWidth: '520px', margin: '0 auto 40px', lineHeight: 1.7 }}
          >
            Score any paper across 6 credibility dimensions in seconds. Run autonomous deep research that retrieves, scores, and synthesises literature — powered by 9 AI agents.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
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
                boxShadow: '0 0 36px rgba(77,136,255,0.4)',
                transition: 'box-shadow 0.2s, transform 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 0 52px rgba(77,136,255,0.65)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 0 36px rgba(77,136,255,0.4)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}
            >
              <Search size={15} /> Score a Paper
            </button>
            <button
              onClick={() => navigate('/deep-research')}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '13px 26px', borderRadius: '12px',
                background: 'rgba(124,58,237,0.12)', border: '1px solid rgba(124,58,237,0.32)',
                color: '#a78bfa', fontSize: '14px', fontWeight: 600,
                cursor: 'pointer', transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(124,58,237,0.22)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(124,58,237,0.12)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}
            >
              <Telescope size={15} /> Deep Research
            </button>
          </motion.div>
        </div>

        {/* ── Stats bar ── */}
        <div
          data-aos="fade-up"
          data-aos-delay="100"
          style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '1px', background: 'rgba(255,255,255,0.05)',
            borderRadius: '16px', overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.07)', marginBottom: '64px',
          }}
        >
          {STATS.map(({ value, label }) => (
            <div key={label} style={{ textAlign: 'center', padding: '22px 16px', background: 'rgba(6,8,15,0.85)' }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '26px', fontWeight: 700, color: '#4d88ff', marginBottom: '4px' }}>{value}</div>
              <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>{label}</div>
            </div>
          ))}
        </div>

        {/* ── Feature cards ── */}
        <div style={{ marginBottom: '64px' }}>
          <h2 data-aos="fade-up" style={{ textAlign: 'center', fontFamily: "'Space Grotesk', sans-serif", fontSize: '22px', fontWeight: 700, color: 'rgba(255,255,255,0.9)', marginBottom: '6px' }}>
            Two powerful tools
          </h2>
          <p data-aos="fade-up" data-aos-delay="80" style={{ textAlign: 'center', fontSize: '13px', color: 'rgba(255,255,255,0.3)', marginBottom: '28px' }}>
            Score individual papers or synthesise entire literature — your choice.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                data-aos="fade-up"
                data-aos-delay={String(i * 100)}
                whileHover={{ scale: 1.015, y: -3 }}
                whileTap={{ scale: 0.99 }}
                onClick={() => navigate(f.to)}
                style={{
                  padding: '28px', borderRadius: '18px',
                  background: `linear-gradient(135deg, ${f.color}0e 0%, rgba(255,255,255,0.02) 100%)`,
                  border: `1px solid ${f.color}22`,
                  cursor: 'pointer', position: 'relative', overflow: 'hidden',
                  transition: 'border-color 0.2s',
                }}
                onMouseEnter={e => ((e.currentTarget as HTMLElement).style.borderColor = `${f.color}44`)}
                onMouseLeave={e => ((e.currentTarget as HTMLElement).style.borderColor = `${f.color}22`)}
              >
                {/* Top accent line */}
                <div style={{ position: 'absolute', top: 0, left: '15%', right: '15%', height: '1px', background: `linear-gradient(90deg, transparent, ${f.color}66, transparent)` }} />

                <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '16px' }}>
                  <div style={{
                    width: '50px', height: '50px', borderRadius: '14px', flexShrink: 0,
                    background: `${f.color}14`, border: `1px solid ${f.color}30`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: `0 0 24px ${f.color}18`,
                  }}>
                    <f.icon size={22} color={f.color} />
                  </div>
                  <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'rgba(255,255,255,0.95)', fontFamily: "'Space Grotesk', sans-serif" }}>
                    {f.title}
                  </h3>
                </div>

                <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.45)', lineHeight: 1.65, marginBottom: '20px' }}>
                  {f.description}
                </p>

                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  fontSize: '13px', fontWeight: 600, color: f.color,
                }}>
                  {f.cta} <ChevronRight size={14} />
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* ── How it works ── */}
        <div style={{ marginBottom: '64px' }}>
          <h2 data-aos="fade-up" style={{ textAlign: 'center', fontFamily: "'Space Grotesk', sans-serif", fontSize: '22px', fontWeight: 700, color: 'rgba(255,255,255,0.9)', marginBottom: '6px' }}>
            How it works
          </h2>
          <p data-aos="fade-up" data-aos-delay="80" style={{ textAlign: 'center', fontSize: '13px', color: 'rgba(255,255,255,0.3)', marginBottom: '28px' }}>
            A LangGraph multi-agent pipeline runs in four sequential phases.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            {HOW.map((step, i) => (
              <div
                key={step.title}
                data-aos="fade-up"
                data-aos-delay={String(i * 100)}
                style={{
                  padding: '22px 18px', borderRadius: '14px', textAlign: 'center',
                  background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.06)',
                  position: 'relative', overflow: 'hidden',
                }}
              >
                <div style={{ position: 'absolute', top: 0, left: '20%', right: '20%', height: '1px', background: 'linear-gradient(90deg, transparent, rgba(77,136,255,0.4), transparent)' }} />
                <div style={{
                  width: '40px', height: '40px', borderRadius: '11px',
                  background: 'rgba(77,136,255,0.1)', border: '1px solid rgba(77,136,255,0.22)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px',
                }}>
                  <step.icon size={18} color="#4d88ff" />
                </div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', fontWeight: 700, color: 'rgba(77,136,255,0.7)', letterSpacing: '0.1em', marginBottom: '5px' }}>
                  {step.step} · {step.title.toUpperCase()}
                </div>
                <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.38)', lineHeight: 1.55 }}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Credibility Dimensions ── */}
        <div style={{ marginBottom: '64px' }}>
          <h2 data-aos="fade-up" style={{ textAlign: 'center', fontFamily: "'Space Grotesk', sans-serif", fontSize: '22px', fontWeight: 700, color: 'rgba(255,255,255,0.9)', marginBottom: '6px' }}>
            6 Credibility Dimensions
          </h2>
          <p data-aos="fade-up" data-aos-delay="80" style={{ textAlign: 'center', fontSize: '13px', color: 'rgba(255,255,255,0.3)', marginBottom: '28px' }}>
            Every paper is scored across six independent dimensions by specialised AI agents.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
            {DIMENSIONS.map((d, i) => (
              <div
                key={d.label}
                data-aos="fade-up"
                data-aos-delay={String((i % 3) * 80)}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: '12px',
                  padding: '14px 16px', borderRadius: '12px',
                  background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <div style={{ width: '3px', height: '36px', borderRadius: '2px', background: d.color, flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <p style={{ fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.82)', marginBottom: '3px' }}>{d.label}</p>
                  <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.32)', lineHeight: 1.5 }}>{d.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Verdict Tiers ── */}
        <div style={{ marginBottom: '48px' }}>
          <h2 data-aos="fade-up" style={{ textAlign: 'center', fontFamily: "'Space Grotesk', sans-serif", fontSize: '22px', fontWeight: 700, color: 'rgba(255,255,255,0.9)', marginBottom: '6px' }}>
            Three-tier Verdict
          </h2>
          <p data-aos="fade-up" data-aos-delay="80" style={{ textAlign: 'center', fontSize: '13px', color: 'rgba(255,255,255,0.3)', marginBottom: '28px' }}>
            Every scored paper receives a clear, actionable verdict.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            {TIERS.map((t, i) => (
              <div
                key={t.tier}
                data-aos="zoom-in"
                data-aos-delay={String(i * 100)}
                style={{
                  padding: '20px', borderRadius: '14px',
                  background: t.bg, border: `1px solid ${t.border}`,
                  display: 'flex', alignItems: 'flex-start', gap: '12px',
                }}
              >
                <t.icon size={20} color={t.color} style={{ flexShrink: 0, marginTop: '1px' }} />
                <div>
                  <p style={{ fontSize: '14px', fontWeight: 700, color: t.color, marginBottom: '4px', fontFamily: "'Space Grotesk', sans-serif" }}>{t.tier}</p>
                  <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.45)', lineHeight: 1.5 }}>{t.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── CTA bottom ── */}
        <div
          data-aos="fade-up"
          style={{
            textAlign: 'center', padding: '48px 32px', borderRadius: '20px',
            background: 'linear-gradient(135deg, rgba(77,136,255,0.07) 0%, rgba(124,58,237,0.07) 100%)',
            border: '1px solid rgba(77,136,255,0.16)',
            position: 'relative', overflow: 'hidden',
          }}
        >
          <div style={{ position: 'absolute', top: 0, left: '25%', right: '25%', height: '1px', background: 'linear-gradient(90deg, transparent, rgba(77,136,255,0.5), rgba(124,58,237,0.5), transparent)' }} />
          <BookOpen size={32} color="rgba(167,139,250,0.5)" style={{ marginBottom: '16px' }} />
          <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: '24px', fontWeight: 700, color: 'rgba(255,255,255,0.92)', marginBottom: '10px' }}>
            Ready to trust your research?
          </h2>
          <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.38)', marginBottom: '28px', maxWidth: '400px', margin: '0 auto 28px', lineHeight: 1.6 }}>
            Score a single paper by DOI or launch an autonomous deep research session — no setup required.
          </p>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={() => navigate('/doi')}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '12px 24px', borderRadius: '11px',
                background: 'linear-gradient(135deg, #4d88ff 0%, #6d6bff 100%)',
                color: 'white', fontSize: '14px', fontWeight: 600,
                border: 'none', cursor: 'pointer',
                boxShadow: '0 0 28px rgba(77,136,255,0.35)',
                transition: 'box-shadow 0.2s, transform 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 0 44px rgba(77,136,255,0.6)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = '0 0 28px rgba(77,136,255,0.35)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}
            >
              <Search size={14} /> Score by DOI
            </button>
            <button
              onClick={() => navigate('/deep-research')}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '12px 24px', borderRadius: '11px',
                background: 'rgba(124,58,237,0.12)', border: '1px solid rgba(124,58,237,0.32)',
                color: '#a78bfa', fontSize: '14px', fontWeight: 600,
                cursor: 'pointer', transition: 'background 0.15s, transform 0.15s',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(124,58,237,0.22)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(124,58,237,0.12)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}
            >
              <Telescope size={14} /> Deep Research
            </button>
          </div>
        </div>

      </div>
    </Layout>
  );
}
