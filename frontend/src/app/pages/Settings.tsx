import { useState } from 'react';
import { motion } from 'motion/react';
import { Save, RotateCcw } from 'lucide-react';
import { Layout } from '../components/Layout';
import { toast } from 'sonner';

const STORAGE_KEY = 'ts_settings_v1';

interface Weight {
  key: string;
  label: string;
  desc: string;
  value: number;
  min: number;
  max: number;
  step: number;
  color: string;
}

const DEFAULT_WEIGHTS: Weight[] = [
  { key: 'retraction_penalty', label: 'Retraction Penalty', desc: 'Points deducted if retracted or flagged by editors.', value: -30, min: -50, max: -10, step: 5, color: '#ff4757' },
  { key: 'p_hack_penalty', label: 'P-Hacking Penalty', desc: 'Points deducted when suspicious p-value clustering detected.', value: -8, min: -20, max: -1, step: 1, color: '#ff4757' },
  { key: 'no_data_penalty', label: 'Missing Data Deposit', desc: 'Points deducted when no public data repository is linked.', value: -3, min: -10, max: -1, step: 1, color: '#ffd166' },
  { key: 'industry_funding', label: 'Industry Funding Flag', desc: 'Points deducted for undisclosed commercial funding.', value: -4, min: -10, max: 0, step: 1, color: '#ffd166' },
  { key: 'open_data_bonus', label: 'Open Data Bonus', desc: 'Points added when public data repository is confirmed.', value: 6, min: 1, max: 15, step: 1, color: '#00e676' },
  { key: 'open_code_bonus', label: 'Open Code Bonus', desc: 'Points added when full analysis code is publicly available.', value: 4, min: 1, max: 12, step: 1, color: '#00e676' },
  { key: 'preregistered_bonus', label: 'Preregistration Bonus', desc: 'Points added when study was preregistered in PROSPERO/OSF.', value: 4, min: 1, max: 10, step: 1, color: '#00e676' },
  { key: 'diverse_citations', label: 'Diverse Citations Bonus', desc: 'Points added when citing institutions are highly diverse.', value: 4, min: 1, max: 10, step: 1, color: '#4d88ff' },
];

const TIER_THRESHOLDS = [
  { key: 'trusted_min', label: 'Trusted Threshold', desc: 'Minimum score to be classified as Trusted.', value: 70, color: '#00e676' },
  { key: 'caution_min', label: 'Caution Threshold', desc: 'Minimum score to be classified as Caution (below = Untrusted).', value: 45, color: '#ffd166' },
];

function WeightRow({ w, onChange }: { w: Weight; onChange: (key: string, v: number) => void }) {
  return (
    <div style={{
      padding: '16px 20px', borderRadius: '12px',
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div>
          <p style={{ fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.82)', marginBottom: '2px' }}>{w.label}</p>
          <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.32)' }}>{w.desc}</p>
        </div>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '15px', fontWeight: 700, color: w.color,
          minWidth: '40px', textAlign: 'right',
        }}>
          {w.value > 0 ? '+' : ''}{w.value}
        </span>
      </div>
      <input
        type="range"
        min={w.min} max={w.max} step={w.step}
        value={w.value}
        onChange={e => onChange(w.key, parseInt(e.target.value))}
        style={{
          width: '100%', accentColor: w.color, cursor: 'pointer',
          height: '4px',
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
        <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono', monospace" }}>{w.min}</span>
        <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono', monospace" }}>{w.max}</span>
      </div>
    </div>
  );
}

function SectionLabel({ title }: { title: string }) {
  return (
    <p style={{
      fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.3)',
      letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '12px', marginTop: '8px',
    }}>
      {title}
    </p>
  );
}

export function Settings() {
  const [weights, setWeights] = useState<Weight[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) { const p = JSON.parse(saved); if (p.weights) return p.weights; }
    } catch {}
    return DEFAULT_WEIGHTS;
  });
  const [thresholds, setThresholds] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) { const p = JSON.parse(saved); if (p.thresholds) return p.thresholds; }
    } catch {}
    return TIER_THRESHOLDS;
  });
  const [defaultTopK, setDefaultTopK] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) { const p = JSON.parse(saved); if (p.defaultTopK) return p.defaultTopK; }
    } catch {}
    return '10';
  });
  const [defaultTier, setDefaultTier] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) { const p = JSON.parse(saved); if (p.defaultTier) return p.defaultTier; }
    } catch {}
    return 'any';
  });
  const [saved, setSaved] = useState(false);

  const changeWeight = (key: string, v: number) =>
    setWeights(ws => ws.map(w => w.key === key ? { ...w, value: v } : w));

  const changeThreshold = (key: string, v: number) =>
    setThresholds(ts => ts.map(t => t.key === key ? { ...t, value: v } : t));

  const handleSave = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ weights, thresholds, defaultTopK, defaultTier }));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    toast.success('Settings saved');
  };

  const handleReset = () => {
    localStorage.removeItem(STORAGE_KEY);
    setWeights(DEFAULT_WEIGHTS);
    setThresholds(TIER_THRESHOLDS);
    setDefaultTopK('10');
    setDefaultTier('any');
    toast.success('Settings reset to defaults');
  };

  const selectStyle: React.CSSProperties = {
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '9px', padding: '8px 12px',
    color: 'rgba(255,255,255,0.75)', fontSize: '13px',
    outline: 'none', cursor: 'pointer', width: '100%',
  };

  return (
    <Layout showBack>
      <div style={{ maxWidth: '700px', margin: '0 auto', padding: '32px 24px', paddingBottom: '80px' }}>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ease: [0.16, 1, 0.3, 1] }}>

          <div style={{ marginBottom: '32px' }}>
            <h1 style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: '28px', fontWeight: 700,
              color: 'rgba(255,255,255,0.96)', marginBottom: '6px',
            }}>
              Settings
            </h1>
            <p style={{ fontSize: '14px', color: 'rgba(255,255,255,0.38)' }}>
              Customize scoring weights, thresholds, and search defaults
            </p>
          </div>

          {/* Scoring weights */}
          <div style={{
            padding: '24px', borderRadius: '16px', marginBottom: '20px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.07)',
          }}>
            <SectionLabel title="Scoring Weights — Penalties" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '24px' }}>
              {weights.filter(w => w.value <= 0).map(w => (
                <WeightRow key={w.key} w={w} onChange={changeWeight} />
              ))}
            </div>

            <SectionLabel title="Scoring Weights — Bonuses" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {weights.filter(w => w.value > 0).map(w => (
                <WeightRow key={w.key} w={w} onChange={changeWeight} />
              ))}
            </div>
          </div>

          {/* Tier thresholds */}
          <div style={{
            padding: '24px', borderRadius: '16px', marginBottom: '20px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.07)',
          }}>
            <SectionLabel title="Tier Classification Thresholds" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {thresholds.map(t => (
                <div key={t.key} style={{
                  padding: '16px 20px', borderRadius: '12px',
                  background: 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <div>
                      <p style={{ fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.82)', marginBottom: '2px' }}>{t.label}</p>
                      <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.32)' }}>{t.desc}</p>
                    </div>
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '16px', fontWeight: 700, color: t.color,
                    }}>
                      {t.value}/100
                    </span>
                  </div>
                  <input
                    type="range" min={0} max={100} step={5}
                    value={t.value}
                    onChange={e => changeThreshold(t.key, parseInt(e.target.value))}
                    style={{ width: '100%', accentColor: t.color, cursor: 'pointer' }}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Search defaults */}
          <div style={{
            padding: '24px', borderRadius: '16px', marginBottom: '28px',
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.07)',
          }}>
            <SectionLabel title="Search Defaults" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <label style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                  Default Top-K
                </label>
                <select value={defaultTopK} onChange={e => setDefaultTopK(e.target.value)} style={selectStyle}>
                  {['5', '10', '20', '50'].map(k => <option key={k} value={k}>{k} papers</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                  Default Min Tier
                </label>
                <select value={defaultTier} onChange={e => setDefaultTier(e.target.value)} style={selectStyle}>
                  <option value="any">Any</option>
                  <option value="caution">Caution+</option>
                  <option value="trusted">Trusted Only</option>
                </select>
              </div>
            </div>
          </div>

          {/* Save / Reset */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              onClick={handleSave}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '12px 24px', borderRadius: '12px',
                background: 'linear-gradient(135deg, #4d88ff, #6d6bff)',
                color: 'white', fontSize: '14px', fontWeight: 600, border: 'none',
                cursor: 'pointer', boxShadow: '0 0 24px rgba(77,136,255,0.4)',
              }}
            >
              <Save size={15} /> Save Settings
            </button>
            {saved && (
              <span style={{ fontSize: '13px', color: '#00e676', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                ✓ Saved
              </span>
            )}
            <button
              onClick={handleReset}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '12px 18px', borderRadius: '12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.5)', fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              <RotateCcw size={14} /> Reset Defaults
            </button>
          </div>
        </motion.div>
      </div>
    </Layout>
  );
}
