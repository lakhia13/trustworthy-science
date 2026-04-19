import { useState } from 'react';
import { motion } from 'motion/react';
import { Eye, Copy, ExternalLink } from 'lucide-react';
import { useNavigate } from 'react-router';
import { TIER_CONFIG, type Paper } from '../data/mockData';
import { TierBadge } from './TierBadge';
import { toast } from 'sonner';
import { copyToClipboard } from '../utils/clipboard';

interface PaperCardProps {
  paper: Paper;
  index?: number;
  selected?: boolean;
  onSelect?: (id: string) => void;
  showCheckbox?: boolean;
}

export function PaperCard({ paper, index, selected, onSelect, showCheckbox }: PaperCardProps) {
  const [hovered, setHovered] = useState(false);
  const navigate = useNavigate();
  const cfg = TIER_CONFIG[(paper.tier.toLowerCase() as keyof typeof TIER_CONFIG)] ?? TIER_CONFIG['caution'];

  const stopAndCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const text = `@article{doi:${paper.doi},\n  title={${paper.title}},\n  author={${paper.authors}},\n  journal={${paper.venue}},\n  year={${paper.year}}\n}`;
    copyToClipboard(text);
    toast.success('BibTeX copied to clipboard');
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay: (index ?? 0) * 0.06, ease: [0.16, 1, 0.3, 1] }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      onClick={() => navigate(`/paper/${encodeURIComponent(paper.id)}?from=results`)}
      style={{
        position: 'relative',
        padding: '20px',
        borderRadius: '14px',
        background: hovered ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.025)',
        borderTop: `1px solid ${hovered ? cfg.border : 'rgba(255,255,255,0.07)'}`,
        borderRight: `1px solid ${hovered ? cfg.border : 'rgba(255,255,255,0.07)'}`,
        borderBottom: `1px solid ${hovered ? cfg.border : 'rgba(255,255,255,0.07)'}`,
        borderLeft: `3px solid ${cfg.color}`,
        cursor: 'pointer',
        transition: 'background 0.2s, border-color 0.2s, box-shadow 0.2s',
        boxShadow: hovered
          ? `0 0 32px ${cfg.glow}, 0 6px 30px rgba(0,0,0,0.35)`
          : '0 2px 10px rgba(0,0,0,0.2)',
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {index !== undefined && (
            <span style={{
              fontSize: '26px', fontWeight: 700, lineHeight: 1, minWidth: '36px',
              color: 'rgba(255,255,255,0.08)',
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {String(index + 1).padStart(2, '0')}
            </span>
          )}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' }}>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '20px', fontWeight: 700,
                color: cfg.color,
              }}>
                {paper.score}
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.25)', fontWeight: 400 }}>/100</span>
              </span>
              <TierBadge tier={paper.tier} size="sm" />
            </div>
            {/* Mini progress bar */}
            <div style={{ width: '110px', height: '3px', borderRadius: '2px', background: 'rgba(255,255,255,0.07)', overflow: 'hidden' }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${paper.score}%` }}
                transition={{ duration: 0.65, delay: 0.2 + (index ?? 0) * 0.06 }}
                style={{ height: '100%', background: cfg.color, borderRadius: '2px' }}
              />
            </div>
          </div>
        </div>
        {showCheckbox && (
          <input
            type="checkbox"
            checked={selected}
            onChange={e => { e.stopPropagation(); onSelect?.(paper.id); }}
            onClick={e => e.stopPropagation()}
            style={{ width: '16px', height: '16px', accentColor: '#4d88ff', cursor: 'pointer', flexShrink: 0, marginTop: '2px' }}
          />
        )}
      </div>

      {/* Title */}
      <p style={{
        fontSize: '14px', fontWeight: 500,
        color: 'rgba(255,255,255,0.88)',
        marginBottom: '6px', lineHeight: 1.45,
        overflow: 'hidden',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
      }}>
        {paper.title}
      </p>

      {/* Venue + DOI */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
        <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', fontStyle: 'italic' }}>
          {paper.venue}, {paper.year}
        </span>
        <span style={{
          fontSize: '11px',
          fontFamily: "'JetBrains Mono', monospace",
          color: 'rgba(255,255,255,0.22)',
          background: 'rgba(255,255,255,0.03)',
          padding: '1px 6px', borderRadius: '4px',
        }}>
          {paper.doi}
        </span>
      </div>

      {/* Flag chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
        {paper.hardFlags.map(flag => (
          <span key={flag} style={{
            fontSize: '10px', fontWeight: 700,
            fontFamily: "'JetBrains Mono', monospace",
            padding: '2px 7px', borderRadius: '4px',
            background: 'rgba(255,71,87,0.12)',
            border: '1px solid rgba(255,71,87,0.28)',
            color: '#ff4757',
            letterSpacing: '0.04em',
          }}>
            ❌ {flag}
          </span>
        ))}
        {paper.softFlags.slice(0, 2).map(f => (
          <span key={f.code} style={{
            fontSize: '10px', fontWeight: 600,
            fontFamily: "'JetBrains Mono', monospace",
            padding: '2px 7px', borderRadius: '4px',
            background: 'rgba(255,209,102,0.08)',
            border: '1px solid rgba(255,209,102,0.2)',
            color: '#ffd166',
            letterSpacing: '0.04em',
          }}>
            ⚠ {f.code}
          </span>
        ))}
        {paper.qualitySignals.slice(0, 1).map(s => (
          <span key={s.code} style={{
            fontSize: '10px', fontWeight: 600,
            fontFamily: "'JetBrains Mono', monospace",
            padding: '2px 7px', borderRadius: '4px',
            background: 'rgba(0,230,118,0.07)',
            border: '1px solid rgba(0,230,118,0.18)',
            color: '#00e676',
            letterSpacing: '0.04em',
          }}>
            ✓ {s.code}
          </span>
        ))}
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '8px' }} onClick={e => e.stopPropagation()}>
        <button
          onClick={() => navigate(`/paper/${encodeURIComponent(paper.id)}?from=results`)}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            padding: '6px 12px', borderRadius: '8px',
            fontSize: '12px', fontWeight: 500,
            background: 'rgba(77,136,255,0.12)',
            border: '1px solid rgba(77,136,255,0.28)',
            color: '#4d88ff', cursor: 'pointer',
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(77,136,255,0.22)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(77,136,255,0.12)')}
        >
          <Eye size={12} /> View Details
        </button>
        <button
          onClick={stopAndCopy}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            padding: '6px 12px', borderRadius: '8px',
            fontSize: '12px', fontWeight: 500,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.09)',
            color: 'rgba(255,255,255,0.45)', cursor: 'pointer',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.45)';
          }}
        >
          <Copy size={12} /> Copy BibTeX
        </button>
        <a
          href={`https://doi.org/${paper.doi}`}
          target="_blank"
          rel="noopener noreferrer"
          onClick={e => e.stopPropagation()}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px',
            padding: '6px 10px', borderRadius: '8px',
            fontSize: '12px',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.07)',
            color: 'rgba(255,255,255,0.3)',
            textDecoration: 'none',
            transition: 'all 0.15s',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.6)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.3)';
          }}
        >
          <ExternalLink size={12} />
        </a>
      </div>
    </motion.div>
  );
}