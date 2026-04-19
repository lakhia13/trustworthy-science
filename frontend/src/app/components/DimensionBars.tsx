import { useState } from 'react';
import { motion } from 'motion/react';
import type { Dimensions } from '../data/mockData';

interface DimensionBarsProps {
  dimensions: Dimensions;
}

const LABELS: { key: keyof Dimensions; label: string; hint: string }[] = [
  { key: 'retraction', label: 'Retraction Status',    hint: 'Whether the paper has been retracted or expression-of-concerned' },
  { key: 'statistics', label: 'Statistical Integrity', hint: 'P-hacking checks, effect sizes, power analysis, and CI quality' },
  { key: 'reproducibility', label: 'Reproducibility',   hint: 'Open data, open code availability, preregistration status' },
  { key: 'citations',  label: 'Citation Network',     hint: 'Institutional diversity of citing authors and journals' },
  { key: 'methodology', label: 'Methodology Quality',  hint: 'LLM-based critique of study design, blinding, and controls' },
  { key: 'venue',      label: 'Publication Venue',    hint: 'Journal reputation, DOAJ index, impact factor, peer review' },
];

function getColor(score: number) {
  if (score >= 70) return '#00e676';
  if (score >= 45) return '#ffd166';
  return '#ff4757';
}

export function DimensionBars({ dimensions }: DimensionBarsProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {LABELS.map(({ key, label, hint }, i) => {
        const val = dimensions[key];
        const color = getColor(val);
        const isHov = hovered === key;
        return (
          <div
            key={key}
            onMouseEnter={() => setHovered(key)}
            onMouseLeave={() => setHovered(null)}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '13px', color: isHov ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.65)', fontWeight: 500, transition: 'color 0.15s' }}>
                {label}
              </span>
              <span style={{
                fontSize: '12px',
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 600,
                color,
              }}>
                {val}%
              </span>
            </div>
            <div style={{
              height: '6px', borderRadius: '3px',
              background: 'rgba(255,255,255,0.05)',
              overflow: 'hidden',
            }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${val}%` }}
                transition={{ duration: 0.65, delay: i * 0.07, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  height: '100%', borderRadius: '3px',
                  background: `linear-gradient(90deg, ${color}88 0%, ${color} 100%)`,
                  boxShadow: isHov ? `0 0 10px ${color}66` : 'none',
                  transition: 'box-shadow 0.2s',
                }}
              />
            </div>
            {isHov && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)', marginTop: '5px' }}
              >
                {hint}
              </motion.p>
            )}
          </div>
        );
      })}
    </div>
  );
}
