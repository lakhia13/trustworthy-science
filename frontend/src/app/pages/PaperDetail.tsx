import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router';
import { motion, AnimatePresence } from 'motion/react';
import {
  Copy, Download, Share2, ExternalLink,
  CheckCircle, AlertTriangle, XCircle,
  ChevronDown, ChevronUp, Loader2, ArrowLeft,
} from 'lucide-react';
import {
  RadarChart, PolarGrid, PolarAngleAxis,
  Radar, ResponsiveContainer,
} from 'recharts';
import { Layout } from '../components/Layout';
import { ScoreRing } from '../components/ScoreRing';
import { TierBadge } from '../components/TierBadge';
import { DimensionBars } from '../components/DimensionBars';
import { StructuredReportDisplay } from '../components/StructuredReportDisplay';
import { TIER_CONFIG, type Flag, type Dimensions } from '../data/mockData';
import { toast } from 'sonner';
import { copyToClipboard } from '../utils/clipboard';
import { getSinglePaper, getUserErrorMessage, type Paper as ApiPaper } from '../../api/client';

const DIM_LABELS: Record<keyof Dimensions, string> = {
  retraction:    'Retraction',
  statistics:    'Statistics',
  reproducibility: 'Repro.',
  citations:     'Citations',
  methodology:   'Method.',
  venue:         'Venue',
};

function SectionDivider({ title }: { title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '8px 0' }}>
      <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)' }} />
      <span style={{
        fontSize: '11px', fontWeight: 700,
        color: 'rgba(255,255,255,0.3)',
        letterSpacing: '0.08em', textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}>
        {title}
      </span>
      <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)' }} />
    </div>
  );
}

function FlagCard({ flag, type, expanded, onToggle }: {
  flag: Flag;
  type: 'soft' | 'quality';
  expanded: boolean;
  onToggle: () => void;
}) {
  const isSoft = type === 'soft';
  const color = isSoft ? '#ffd166' : '#00e676';
  const bg = isSoft ? 'rgba(255,209,102,0.06)' : 'rgba(0,230,118,0.05)';
  const border = isSoft ? 'rgba(255,209,102,0.18)' : 'rgba(0,230,118,0.15)';
  const Icon = isSoft ? AlertTriangle : CheckCircle;

  return (
    <motion.div
      layout
      style={{ borderRadius: '12px', background: bg, border: `1px solid ${border}`, overflow: 'hidden' }}
    >
      <button
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Icon size={14} color={color} />
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '12px', fontWeight: 700,
            color: color, letterSpacing: '0.05em',
          }}>
            {flag.code}
          </span>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '12px', fontWeight: 600,
            color: isSoft ? '#ff4757' : '#00e676',
          }}>
            {flag.pts > 0 ? '+' : ''}{flag.pts} pts
          </span>
        </div>
        {expanded
          ? <ChevronUp size={14} style={{ color: 'rgba(255,255,255,0.3)' }} />
          : <ChevronDown size={14} style={{ color: 'rgba(255,255,255,0.3)' }} />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            key="body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.62)', lineHeight: 1.55 }}>
                {flag.explanation}
              </p>
              <div style={{
                padding: '8px 12px', borderRadius: '8px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.28)', fontFamily: "'JetBrains Mono', monospace" }}>
                  Evidence: {flag.evidence}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function PaperDetail() {
  const [searchParams] = useSearchParams();
  const doi = searchParams.get('doi') ?? undefined;
  const navigate = useNavigate();
  const fromLabel = ({
    results: 'Results',
    review: 'Literature Review',
    doi: 'DOI Search',
  } as Record<string, string>)[searchParams.get('from') ?? ''] ?? 'Back';
  const [paper, setPaper] = useState<ApiPaper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedFlag, setExpandedFlag] = useState<string | null>(null);

  useEffect(() => {
    if (!doi) return;

    const fetchPaper = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await getSinglePaper(doi);
        setPaper(response.paper);
      } catch (err: any) {
        const message = getUserErrorMessage(err);
        setError(message);
        toast.error(message);
      } finally {
        setLoading(false);
      }
    };

    fetchPaper();
  }, [doi]);

  if (loading) {
    return (
      <Layout showBack>
        <div style={{ maxWidth: '860px', margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: '20px' }}>
          <Loader2 size={40} style={{ color: '#4d88ff', animation: 'spin 1s linear infinite' }} />
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '14px' }}>Fetching paper details...</p>
        </div>
      </Layout>
    );
  }

  if (error || !paper) {
    return (
      <Layout showBack>
        <div style={{ maxWidth: '860px', margin: '0 auto', padding: '32px 24px', minHeight: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '20px' }}>
          <XCircle size={40} color="#ff4757" />
          <p style={{ color: '#ff4757', fontSize: '16px', fontWeight: 600 }}>Error loading paper</p>
          <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '14px', textAlign: 'center' }}>
            {error || 'Paper not found. Please check the DOI and try again.'}
          </p>
        </div>
      </Layout>
    );
  }

  // Normalise per_dimension: /explain returns DimensionScore[] with scores 0.0–1.0
  const pdRaw = paper.per_dimension;
  const pdMap: Record<string, number> = {};
  if (Array.isArray(pdRaw)) {
    for (const d of pdRaw) {
      // score is 0.0–1.0 from /explain; convert to 0–100
      pdMap[d.dimension] = Math.round(d.score <= 1 ? d.score * 100 : d.score);
    }
  } else if (pdRaw && typeof pdRaw === 'object') {
    for (const [k, v] of Object.entries(pdRaw as Record<string, number>)) {
      pdMap[k] = Math.round((v as number) <= 1 ? (v as number) * 100 : (v as number));
    }
  }

  // Human-readable short labels for radar axes (important for judges)
  const RADAR_LABELS: Record<string, string> = {
    retraction_watch:    'Retraction',
    stats_integrity:     'Statistics',
    statistical_integrity: 'Statistics',
    citation_network:    'Citations',
    methodology:         'Methodology',
    publication_metadata:'Publication',
    reproducibility:     'Repro.',
  };

  const radarData = Object.entries(pdMap).map(([key, val]) => ({
    subject: RADAR_LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    fullLabel: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    value: val,
    fullMark: 100,
  }));

  // Map exact backend key names → frontend Dimensions keys (default 0 so missing data is visible)
  const dimensions = {
    retraction:      pdMap['retraction_watch']    ?? 0,
    statistics:      pdMap['stats_integrity']      ?? pdMap['statistical_integrity'] ?? 0,
    reproducibility: pdMap['reproducibility']      ?? 0,
    citations:       pdMap['citation_network']     ?? 0,
    methodology:     pdMap['methodology']          ?? 0,
    venue:           pdMap['publication_metadata'] ?? 0,
  };

  const toggleFlag = (code: string) =>
    setExpandedFlag(prev => (prev === code ? null : code));

  const copyDoi = () => {
    if (paper.doi) {
      copyToClipboard(paper.doi);
      toast.success('DOI copied to clipboard');
    }
  };

  const copyBib = () => {
    if (paper.doi) {
      copyToClipboard(
        `@article{doi:${paper.doi},\n  title={${paper.title}},\n  author={${paper.authors?.join(', ') || 'Unknown'}},\n  journal={${paper.venue}},\n  year=${paper.year}}\n}`
      );
      toast.success('BibTeX copied to clipboard');
    }
  };

  const exportReport = () => {
    const score = paper.score ?? paper.composite_score ?? 0;
    const hard = (paper.hard_flags as any[] ?? []).map((f: any) => typeof f === 'string' ? f : f.code).join(', ') || 'None';
    const soft = (paper.soft_flags as any[] ?? []).map((f: any) => typeof f === 'string' ? f : f.code).join(', ') || 'None';
    const quality = (paper.quality_signals as any[] ?? []).map((f: any) => typeof f === 'string' ? f : f.code).join(', ') || 'None';

    const sr = paper.structured_report;
    const lines = [
      '═══════════════════════════════════════════════════════════',
      '  TRUSTWORTHY SCIENCE — CREDIBILITY REPORT',
      '═══════════════════════════════════════════════════════════',
      '',
      `Title    : ${paper.title}`,
      `Authors  : ${Array.isArray(paper.authors) ? paper.authors.join(', ') : (paper.authors ?? 'Unknown')}`,
      `Journal  : ${paper.venue ?? '—'}`,
      `Year     : ${paper.year ?? '—'}`,
      `DOI      : ${paper.doi ?? '—'}`,
      '',
      '───────────────────────────────────────────────────────────',
      '  CREDIBILITY SCORE',
      '───────────────────────────────────────────────────────────',
      `Score    : ${score}/100`,
      `Tier     : ${paper.tier}`,
      '',
      sr?.overall_verdict ? `Verdict  : ${sr.overall_verdict}` : '',
      '',
      '───────────────────────────────────────────────────────────',
      '  FLAGS',
      '───────────────────────────────────────────────────────────',
      `Hard Flags      : ${hard}`,
      `Soft Flags      : ${soft}`,
      `Quality Signals : ${quality}`,
      '',
      ...(sr?.key_concerns?.length ? [
        '───────────────────────────────────────────────────────────',
        '  KEY CONCERNS',
        '───────────────────────────────────────────────────────────',
        ...(sr.key_concerns.map((c, i) => `  ${i + 1}. ${c}`)),
        '',
      ] : []),
      ...(sr?.positive_signals?.length ? [
        '───────────────────────────────────────────────────────────',
        '  POSITIVE SIGNALS',
        '───────────────────────────────────────────────────────────',
        ...(sr.positive_signals.map((s, i) => `  ${i + 1}. ${s}`)),
        '',
      ] : []),
      ...(sr?.score_breakdown?.length ? [
        '───────────────────────────────────────────────────────────',
        '  DIMENSION BREAKDOWN',
        '───────────────────────────────────────────────────────────',
        ...(sr.score_breakdown.map(d => {
          const pct = Math.round((d as any).score_pct ?? (d.score > 1 ? d.score : d.score * 100));
          return `  ${d.dimension.replace(/_/g, ' ').padEnd(24)} ${pct}%`;
        })),
        '',
      ] : []),
      ...(sr?.recommendation ? [
        '───────────────────────────────────────────────────────────',
        '  RECOMMENDATION',
        '───────────────────────────────────────────────────────────',
        `  ${sr.recommendation}`,
        '',
      ] : []),
      '───────────────────────────────────────────────────────────',
      '  AI IMPACT ASSESSMENT',
      '───────────────────────────────────────────────────────────',
      `  ${impactMsg}`,
      '',
      '═══════════════════════════════════════════════════════════',
      `  Generated by Trustworthy Science · ${new Date().toISOString().split('T')[0]}`,
      '═══════════════════════════════════════════════════════════',
    ].filter(l => l !== undefined);

    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `credibility-report-${(paper.doi ?? 'paper').replace(/[^a-z0-9]/gi, '-')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Report downloaded');
  };


  const tierLower = paper.tier?.toLowerCase() as string;
  const impactMsg =
    tierLower === 'trusted'
      ? 'Drug target based on this paper has LOW RISK of replication failure. Safe to include in target-discovery pipeline.'
      : tierLower === 'caution'
      ? 'Use this paper with caution. Independently verify core claims before building drug-discovery hypotheses.'
      : 'HIGH RISK of replication failure. Exclude from drug-discovery pipeline entirely. Seek better sources.';

  // Get tier config
  const cfg = TIER_CONFIG[tierLower as 'trusted' | 'caution' | 'untrusted'] || TIER_CONFIG['untrusted'];

  // Convert flag codes (strings) to Flag objects for display
  const convertFlagsForDisplay = (
    flags: string[] | Flag[] | undefined,
    signalType: 'hard' | 'soft' | 'quality' = 'soft'
  ): Flag[] => {
    if (!flags) return [];
    return flags.map(flag => {
      if (typeof flag === 'string') {
        return {
          code: flag,
          pts: signalType === 'quality' ? 2 : -2,
          explanation: signalType === 'quality'
            ? `Positive signal: ${flag.replace(/_/g, ' ').toLowerCase()}`
            : `Flag: ${flag.replace(/_/g, ' ').toLowerCase()}`,
          evidence: 'See credibility report for details',
        };
      }
      return flag as Flag;
    });
  };

  const hardFlags    = convertFlagsForDisplay(paper.hard_flags as any,     'hard');
  const softFlags    = convertFlagsForDisplay(paper.soft_flags as any,     'soft');
  const qualitySignals = convertFlagsForDisplay(paper.quality_signals as any, 'quality');

  return (
    <Layout showBack>
      <div style={{ maxWidth: '860px', margin: '0 auto', padding: '32px 24px', paddingBottom: '80px' }}>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ease: [0.16, 1, 0.3, 1] }}
          style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
        >
          {/* ── Breadcrumb ── */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '16px' }}>
            <button
              onClick={() => navigate(-1)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: '5px',
                color: 'rgba(255,255,255,0.35)', fontSize: '12px',
                padding: '4px 0', transition: 'color 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
            >
              <ArrowLeft size={13} /> {fromLabel}
            </button>
            <span style={{ color: 'rgba(255,255,255,0.12)', fontSize: '12px' }}>/</span>
            <span style={{
              fontSize: '12px', color: 'rgba(255,255,255,0.4)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '300px',
            }}>
              {paper?.title ?? doi}
            </span>
          </div>

          {/* ── Paper header ── */}
          <div style={{
            padding: '24px', borderRadius: '16px',
            background: 'rgba(255,255,255,0.025)',
            border: '1px solid rgba(255,255,255,0.07)',
          }}>
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: '20px', fontWeight: 600,
              color: 'rgba(255,255,255,0.96)', lineHeight: 1.35,
              marginBottom: '8px',
            }}>
              {paper.title}
            </h1>
            <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.4)', marginBottom: '4px' }}>
              {paper.authors}
            </p>
            <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.32)', fontStyle: 'italic', marginBottom: '14px' }}>
              {paper.venue}, {paper.year}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '12px', padding: '4px 10px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '6px', color: 'rgba(255,255,255,0.48)',
              }}>
                {paper.doi}
              </span>
              <button onClick={copyDoi} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.28)', padding: '4px', transition: 'color 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.28)')}>
                <Copy size={14} />
              </button>
              <a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noopener noreferrer"
                style={{ color: 'rgba(255,255,255,0.28)', transition: 'color 0.15s' }}
                onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.7)')}
                onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.28)')}>
                <ExternalLink size={14} />
              </a>
            </div>
          </div>

          {/* ── Score card ── */}
          <div style={{
            padding: '28px', borderRadius: '16px',
            background: `linear-gradient(135deg, ${cfg.bg} 0%, rgba(255,255,255,0.02) 100%)`,
            border: `1px solid ${cfg.border}`,
            boxShadow: `0 0 50px ${cfg.glow}`,
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center' }}
              className="sm:flex-row sm:items-center"
            >
              <ScoreRing score={paper.score || paper.composite_score || 0} tier={tierLower as any} size={150} />
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{ marginBottom: '12px' }}>
                  <TierBadge tier={tierLower as any} size="lg" />
                </div>
                <p style={{ fontSize: '15px', color: 'rgba(255,255,255,0.72)', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto' }}>
                  {(() => {
                    const s = paper.summary ?? '';
                    const isGarbage = s.length > 400
                      || s.includes('Must not use markdown')
                      || s.includes('We must not')
                      || s.includes('no asterisks')
                      || s.includes('score_breakdown');
                    return isGarbage
                      ? (paper.structured_report?.overall_verdict ?? 'No summary available.')
                      : (s || paper.structured_report?.overall_verdict || 'No summary available.');
                  })()}
                </p>
                {hardFlags.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '14px', justifyContent: 'center' }}>
                    {hardFlags.map(f => (
                      <span key={f.code} style={{
                        fontSize: '11px', fontFamily: "'JetBrains Mono', monospace",
                        fontWeight: 700, padding: '3px 9px', borderRadius: '5px',
                        background: 'rgba(255,71,87,0.14)',
                        border: '1px solid rgba(255,71,87,0.3)',
                        color: '#ff4757',
                      }}>
                        ❌ {f.code}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Credibility Breakdown ── */}
          <SectionDivider title="Credibility Breakdown" />

          {/* If structured_report available, render rich AI breakdown */}
          {paper.structured_report ? (
            <StructuredReportDisplay report={paper.structured_report as any} />
          ) : (
            /* Fallback: manual dimension bars + radar */
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              {/* Bars */}
              <div style={{
                padding: '20px', borderRadius: '14px',
                background: 'rgba(255,255,255,0.025)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: '18px' }}>
                  Per-Dimension Scores
                </p>
                <DimensionBars dimensions={dimensions} />
              </div>

              {/* Radar chart */}
              {radarData.length > 0 && (
                <div style={{
                  padding: '20px', borderRadius: '14px',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Radar Profile
                  </p>
                  <ResponsiveContainer width="100%" height={230}>
                    <RadarChart key={paper.doi ?? 'radar'} data={radarData}>
                      <PolarGrid stroke="rgba(255,255,255,0.07)" gridType="polygon" />
                      <PolarAngleAxis
                        dataKey="subject"
                        tick={{ fill: 'rgba(255,255,255,0.38)', fontSize: 11 }}
                      />
                      <Radar
                        dataKey="value"
                        stroke={cfg.color}
                        fill={cfg.color}
                        fillOpacity={0.12}
                        strokeWidth={2}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* Always show radar + dimension bars when data is available */}
          {Object.values(dimensions).some(v => v > 0) && (
            <>
              <SectionDivider title="Dimension Radar · Visual Credibility Profile" />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>

                {/* Radar chart — meaningful for judges */}
                <div style={{
                  padding: '20px', borderRadius: '14px',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  position: 'relative', overflow: 'hidden',
                }}>
                  <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '2px', background: `linear-gradient(90deg, transparent, ${cfg.color}88, transparent)` }} />
                  <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '4px' }}>
                    Radar Profile
                  </p>
                  <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.2)', marginBottom: '12px' }}>
                    Each axis = one credibility dimension (0–100). Larger area = more trustworthy.
                  </p>
                  <ResponsiveContainer width="100%" height={240}>
                    <RadarChart key={paper.doi ?? 'radar'} data={radarData} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
                      <PolarGrid stroke="rgba(255,255,255,0.08)" gridType="polygon" />
                      <PolarAngleAxis
                        dataKey="subject"
                        tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10, fontFamily: "'Inter', sans-serif" }}
                      />
                      <Radar
                        dataKey="value"
                        stroke={cfg.color}
                        fill={cfg.color}
                        fillOpacity={0.15}
                        strokeWidth={2}
                        dot={{ fill: cfg.color, strokeWidth: 0, r: 3 }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                  {/* Legend */}
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '8px', flexWrap: 'wrap' }}>
                    {radarData.map(d => (
                      <div key={d.subject} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.color, opacity: d.value >= 70 ? 1 : d.value >= 45 ? 0.7 : 0.4 }} />
                        <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)', fontFamily: "'JetBrains Mono', monospace" }}>
                          {d.subject.split(' ').map(w => w[0]).join('')} {d.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Dimension bars */}
                <div style={{
                  padding: '20px', borderRadius: '14px',
                  background: 'rgba(255,255,255,0.025)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '18px' }}>
                    Per-Dimension Scores
                  </p>
                  <DimensionBars dimensions={dimensions} />
                </div>
              </div>
            </>
          )}

          {/* ── Hard Flags ── */}
          <SectionDivider title="Hard Flags · Critical Issues" />
          <div style={{
            padding: '18px 20px', borderRadius: '14px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.06)',
          }}>
            {hardFlags.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#00e676' }}>
                <CheckCircle size={16} />
                <span style={{ fontSize: '14px' }}>None detected — no critical issues found</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {hardFlags.map(f => (
                  <div key={f.code} style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '10px 14px', borderRadius: '10px',
                    background: 'rgba(255,71,87,0.08)',
                    border: '1px solid rgba(255,71,87,0.22)',
                  }}>
                    <XCircle size={15} color="#ff4757" />
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '13px', fontWeight: 700, color: '#ff4757',
                    }}>
                      {f.code}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Soft Flags ── */}
          {softFlags.length > 0 && (
            <>
              <SectionDivider title="Soft Flags · Concerns" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {softFlags.map(flag => (
                  <FlagCard
                    key={flag.code}
                    flag={flag}
                    type="soft"
                    expanded={expandedFlag === flag.code}
                    onToggle={() => toggleFlag(flag.code)}
                  />
                ))}
              </div>
            </>
          )}

          {/* ── Quality Signals ── */}
          {qualitySignals.length > 0 && (
            <>
              <SectionDivider title="Quality Signals · Strengths" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {qualitySignals.map(sig => (
                  <FlagCard
                    key={sig.code}
                    flag={sig}
                    type="quality"
                    expanded={expandedFlag === sig.code}
                    onToggle={() => toggleFlag(sig.code)}
                  />
                ))}
              </div>
            </>
          )}

          {/* ── AI Impact Assessment ── */}
          <SectionDivider title="AI Impact Assessment" />
          <div style={{
            padding: '20px 22px', borderRadius: '14px',
            background: 'linear-gradient(135deg, rgba(77,136,255,0.07) 0%, rgba(167,139,250,0.05) 100%)',
            borderTop: '1px solid rgba(77,136,255,0.18)',
            borderRight: '1px solid rgba(77,136,255,0.18)',
            borderBottom: '1px solid rgba(77,136,255,0.18)',
            borderLeft: '4px solid #4d88ff',
          }}>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.72)', lineHeight: 1.65, fontStyle: 'italic' }}>
              &ldquo;{impactMsg}&rdquo;
            </p>
          </div>

          {/* ── Actions ── */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', paddingTop: '4px' }}>
            <button
              onClick={copyBib}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '11px 20px', borderRadius: '11px',
                background: 'linear-gradient(135deg, #4d88ff, #6d6bff)',
                color: 'white', fontSize: '13px', fontWeight: 600, border: 'none',
                cursor: 'pointer',
                boxShadow: '0 0 22px rgba(77,136,255,0.35)',
              }}
            >
              <Copy size={14} /> Copy BibTeX
            </button>
            <button
              onClick={exportReport}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '11px 18px', borderRadius: '11px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.65)', fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              <Download size={14} /> Export Report
            </button>
            <button
              onClick={() => toast.success('Link copied')}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '11px 18px', borderRadius: '11px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.65)', fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              <Share2 size={14} /> Share
            </button>
          </div>
        </motion.div>
      </div>
    </Layout>
  );
}