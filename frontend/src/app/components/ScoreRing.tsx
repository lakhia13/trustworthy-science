import { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { Tier, TIER_CONFIG } from '../data/mockData';

interface ScoreRingProps {
  score: number;
  tier: Tier;
  size?: number;
}

export function ScoreRing({ score, tier, size = 150 }: ScoreRingProps) {
  const cfg = TIER_CONFIG[tier];
  const [displayed, setDisplayed] = useState(0);

  const strokeW = size > 120 ? 10 : 8;
  const radius = (size - strokeW * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashoffset = circumference * (1 - score / 100);

  useEffect(() => {
    let frame: number;
    const start = performance.now();
    const duration = 900;
    const step = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplayed(Math.round(eased * score));
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const cx = size / 2;
  const cy = size / 2;

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      {/* Glow halo */}
      <div style={{
        position: 'absolute',
        inset: strokeW + 4,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${cfg.glow} 0%, transparent 72%)`,
        filter: 'blur(12px)',
      }} />

      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)', display: 'block' }}>
        {/* Track */}
        <circle
          cx={cx} cy={cy} r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeW}
        />
        {/* Progress arc */}
        <motion.circle
          cx={cx} cy={cy} r={radius}
          fill="none"
          stroke={cfg.color}
          strokeWidth={strokeW}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashoffset }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          style={{ filter: `drop-shadow(0 0 6px ${cfg.color})` }}
        />
      </svg>

      {/* Center label */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: size > 120 ? '34px' : '22px',
          fontWeight: 700,
          color: cfg.color,
          lineHeight: 1,
          textShadow: `0 0 24px ${cfg.color}80`,
        }}>
          {displayed}
        </span>
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.28)', marginTop: '2px' }}>
          / 100
        </span>
      </div>
    </div>
  );
}
