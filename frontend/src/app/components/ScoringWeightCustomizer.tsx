/**
 * ScoringWeightCustomizer — Modal for per-request scoring weight overrides.
 * Renders 5 sliders that adjust penalties/bonuses relative to the server defaults.
 */

import { useState } from 'react';
import { motion } from 'motion/react';
import { X, RotateCcw, SlidersHorizontal } from 'lucide-react';
import type { ScoringWeights } from '../../api/client';

interface SliderConfig {
  key: keyof ScoringWeights;
  label: string;
  description: string;
  min: number;
  max: number;
  step: number;
  default: number;
  unit: string;
  color: string;
}

const SLIDERS: SliderConfig[] = [
  {
    key: 'retraction_cap',
    label: 'Retraction Cap',
    description: 'Max score if paper is retracted',
    min: 5, max: 50, step: 1, default: 25,
    unit: 'pts', color: '#ff4757',
  },
  {
    key: 'no_data_deposit_penalty',
    label: 'No Data Penalty',
    description: 'Penalty when no data repository found',
    min: 0, max: 15, step: 1, default: 3,
    unit: 'pts', color: '#ffd166',
  },
  {
    key: 'open_data_bonus',
    label: 'Open Data Bonus',
    description: 'Bonus for papers with open data',
    min: 1, max: 15, step: 1, default: 6,
    unit: 'pts', color: '#00e676',
  },
  {
    key: 'replicated_bonus',
    label: 'Replicated Bonus',
    description: 'Bonus for independently replicated studies',
    min: 1, max: 20, step: 1, default: 10,
    unit: 'pts', color: '#06b6d4',
  },
  {
    key: 'methods_nudge_pct',
    label: 'Methods Nudge %',
    description: 'Weight of LLM methodology critique',
    min: 0, max: 100, step: 5, default: 15,
    unit: '%', color: '#a78bfa',
  },
];

const DEFAULTS: ScoringWeights = Object.fromEntries(
  SLIDERS.map(s => [s.key, s.default])
) as ScoringWeights;

interface ScoringWeightCustomizerProps {
  onApply: (weights: ScoringWeights) => void;
  onCancel: () => void;
  initialWeights?: ScoringWeights;
}

export function ScoringWeightCustomizer({ onApply, onCancel, initialWeights }: ScoringWeightCustomizerProps) {
  const [values, setValues] = useState<ScoringWeights>(initialWeights ?? { ...DEFAULTS });

  const set = (key: keyof ScoringWeights, val: number) =>
    setValues(prev => ({ ...prev, [key]: val }));

  const reset = () => setValues({ ...DEFAULTS });

  const isDirty = SLIDERS.some(s => values[s.key] !== s.default);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: 'fixed', inset: 0, zIndex: 300,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
        padding: '24px',
      }}
      onClick={onCancel}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: '480px',
          borderRadius: '20px',
          background: 'rgba(10,12,28,0.98)',
          border: '1px solid rgba(255,255,255,0.1)',
          boxShadow: '0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(124,58,237,0.2)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Top gradient line */}
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: '1px', background: 'linear-gradient(90deg, transparent, #7c3aed, #06b6d4, transparent)' }} />

        {/* Header */}
        <div style={{
          padding: '20px 24px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: 32, height: 32, borderRadius: '9px',
              background: 'rgba(124,58,237,0.15)',
              border: '1px solid rgba(124,58,237,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <SlidersHorizontal size={15} color="#a78bfa" />
            </div>
            <div>
              <p style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: '15px', fontWeight: 600, color: 'rgba(255,255,255,0.9)', margin: 0 }}>
                Scoring Weights
              </p>
              <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', margin: 0 }}>
                Override defaults for this request
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {isDirty && (
              <button
                onClick={reset}
                style={{
                  display: 'flex', alignItems: 'center', gap: '5px',
                  padding: '5px 10px', borderRadius: '7px',
                  fontSize: '11px', color: 'rgba(255,255,255,0.35)',
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.7)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.35)'; }}
              >
                <RotateCcw size={11} /> Reset
              </button>
            )}
            <button
              onClick={onCancel}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.25)', padding: '4px' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.25)')}
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Sliders */}
        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {SLIDERS.map(({ key, label, description, min, max, step, default: def, unit, color }) => {
            const val = values[key] ?? def;
            const pct = ((val - min) / (max - min)) * 100;
            const changed = val !== def;
            return (
              <div key={key}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div>
                    <span style={{ fontSize: '13px', fontWeight: 500, color: 'rgba(255,255,255,0.8)' }}>
                      {label}
                    </span>
                    <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', margin: '1px 0 0' }}>
                      {description}
                    </p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {changed && (
                      <span style={{
                        fontSize: '10px', color: 'rgba(255,255,255,0.25)',
                        fontFamily: "'JetBrains Mono', monospace",
                        textDecoration: 'line-through',
                      }}>
                        {def}
                      </span>
                    )}
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '13px', fontWeight: 700, color,
                    }}>
                      {val}{unit}
                    </span>
                  </div>
                </div>

                {/* Custom styled range input */}
                <div style={{ position: 'relative', height: '6px' }}>
                  <div style={{
                    position: 'absolute', inset: 0,
                    borderRadius: '3px', background: 'rgba(255,255,255,0.07)',
                  }} />
                  <div style={{
                    position: 'absolute', left: 0, top: 0, bottom: 0,
                    width: `${pct}%`, borderRadius: '3px',
                    background: `linear-gradient(90deg, ${color}66, ${color})`,
                    transition: 'width 0.1s',
                  }} />
                  <input
                    type="range"
                    min={min} max={max} step={step}
                    value={val}
                    onChange={e => set(key, parseFloat(e.target.value))}
                    style={{
                      position: 'absolute', inset: 0,
                      width: '100%', height: '100%',
                      opacity: 0, cursor: 'pointer', margin: 0,
                    }}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
                  <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono', monospace" }}>{min}</span>
                  <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono', monospace" }}>{max}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid rgba(255,255,255,0.07)',
          display: 'flex', gap: '10px',
        }}>
          <button
            onClick={onCancel}
            style={{
              flex: 1, padding: '10px', borderRadius: '10px',
              fontSize: '13px', fontWeight: 500,
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)',
              color: 'rgba(255,255,255,0.45)', cursor: 'pointer', transition: 'all 0.15s',
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
            Cancel
          </button>
          <button
            onClick={() => onApply(isDirty ? values : {})}
            style={{
              flex: 2, padding: '10px', borderRadius: '10px',
              fontSize: '13px', fontWeight: 600,
              background: isDirty
                ? 'linear-gradient(135deg, #7c3aed, #4d88ff)'
                : 'rgba(124,58,237,0.15)',
              border: `1px solid ${isDirty ? 'transparent' : 'rgba(124,58,237,0.3)'}`,
              color: isDirty ? 'white' : '#a78bfa', cursor: 'pointer',
              transition: 'all 0.2s',
              boxShadow: isDirty ? '0 0 24px rgba(124,58,237,0.3)' : 'none',
            }}
          >
            {isDirty ? 'Apply Custom Weights' : 'Use Defaults'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
