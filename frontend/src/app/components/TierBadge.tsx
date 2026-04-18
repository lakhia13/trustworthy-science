import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { Tier, TIER_CONFIG } from '../data/mockData';

interface TierBadgeProps {
  tier: Tier;
  size?: 'sm' | 'md' | 'lg';
}

const ICONS = {
  trusted: CheckCircle,
  caution: AlertTriangle,
  untrusted: XCircle,
};

const SIZES = {
  sm:  { icon: 11, font: '10px', px: '7px',  py: '3px',  gap: '4px',  radius: '5px' },
  md:  { icon: 13, font: '12px', px: '9px',  py: '4px',  gap: '5px',  radius: '6px' },
  lg:  { icon: 15, font: '13px', px: '11px', py: '6px',  gap: '6px',  radius: '8px' },
};

export function TierBadge({ tier, size = 'md' }: TierBadgeProps) {
  const cfg = TIER_CONFIG[tier];
  const Icon = ICONS[tier];
  const s = SIZES[size];

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: s.gap,
      padding: `${s.py} ${s.px}`,
      borderRadius: s.radius,
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      color: cfg.color,
      fontSize: s.font,
      fontWeight: 600,
      letterSpacing: '0.03em',
      boxShadow: `0 0 14px ${cfg.glow}`,
      whiteSpace: 'nowrap',
    }}>
      <Icon size={s.icon} />
      {cfg.label}
    </span>
  );
}
