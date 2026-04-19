import { ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { Home, Search, FileText, Settings, ArrowLeft, FlaskConical, GitCompare, BookOpen } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
  showBack?: boolean;
}

const NAV_LINKS = [
  { to: '/doi',    label: 'DOI Search',        icon: Search },
  { to: '/query',  label: 'Query',             icon: FileText },
  { to: '/review', label: 'Literature Review', icon: BookOpen },
  { to: '/rag',    label: 'RAG Compare',       icon: GitCompare },
];

const MOBILE_NAV = [
  { to: '/',       label: 'Home',     icon: Home },
  { to: '/doi',    label: 'DOI',      icon: Search },
  { to: '/query',  label: 'Query',    icon: FileText },
  { to: '/review', label: 'Review',   icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function Layout({ children, showBack }: LayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#06080f', color: 'rgba(255,255,255,0.9)', position: 'relative' }}>
      {/* Background gradient orbs */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden', zIndex: 0 }}>
        <div style={{
          position: 'absolute', top: '-15%', left: '-10%',
          width: '700px', height: '700px',
          background: 'radial-gradient(circle, rgba(77,136,255,0.07) 0%, transparent 65%)',
          filter: 'blur(80px)',
        }} />
        <div style={{
          position: 'absolute', bottom: '-20%', right: '-10%',
          width: '600px', height: '600px',
          background: 'radial-gradient(circle, rgba(167,139,250,0.06) 0%, transparent 65%)',
          filter: 'blur(80px)',
        }} />
        <div style={{
          position: 'absolute', top: '40%', right: '20%',
          width: '400px', height: '400px',
          background: 'radial-gradient(circle, rgba(0,230,118,0.03) 0%, transparent 70%)',
          filter: 'blur(60px)',
        }} />
      </div>

      {/* Grid overlay */}
      <div className="ts-grid-bg" style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0, opacity: 0.6 }} />

      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: 'rgba(6,8,15,0.85)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
      }}>
        <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 24px', height: '60px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px' }}>
          {/* Left */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {showBack && (
              <button
                onClick={() => navigate(-1)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  color: 'rgba(255,255,255,0.4)', fontSize: '13px',
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '6px 8px', borderRadius: '8px',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.85)')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
              >
                <ArrowLeft size={15} />
                Back
              </button>
            )}
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '10px', textDecoration: 'none' }}>
              <div style={{
                width: 34, height: 34,
                background: 'linear-gradient(135deg, #4d88ff 0%, #a78bfa 100%)',
                borderRadius: '10px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 20px rgba(77,136,255,0.35)',
              }}>
                <FlaskConical size={17} color="white" />
              </div>
              <span style={{
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
                fontSize: '15px',
                background: 'linear-gradient(135deg, #ffffff 0%, rgba(255,255,255,0.75) 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}>
                Trustworthy Science
              </span>
            </Link>
          </div>

          {/* Center desktop nav */}
          <nav style={{ display: 'flex', alignItems: 'center', gap: '4px' }} className="hidden md:flex">
            {NAV_LINKS.map(({ to, label, icon: Icon }) => {
              const active = location.pathname === to;
              return (
                <Link
                  key={to}
                  to={to}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    padding: '6px 12px', borderRadius: '8px',
                    fontSize: '13px', textDecoration: 'none',
                    color: active ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.4)',
                    background: active ? 'rgba(255,255,255,0.08)' : 'transparent',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={e => {
                    if (!active) {
                      (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.8)';
                      (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (!active) {
                      (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.4)';
                      (e.currentTarget as HTMLElement).style.background = 'transparent';
                    }
                  }}
                >
                  <Icon size={14} />
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* Right */}
          <Link
            to="/settings"
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 12px', borderRadius: '8px',
              fontSize: '13px', textDecoration: 'none',
              color: location.pathname === '/settings' ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.4)',
              background: location.pathname === '/settings' ? 'rgba(255,255,255,0.08)' : 'transparent',
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.8)';
              (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.color = location.pathname === '/settings' ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.4)';
              (e.currentTarget as HTMLElement).style.background = location.pathname === '/settings' ? 'rgba(255,255,255,0.08)' : 'transparent';
            }}
          >
            <Settings size={14} />
            <span className="hidden md:inline">Settings</span>
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main style={{ position: 'relative', zIndex: 10 }}>
        {children}
      </main>

      {/* Mobile bottom nav */}
      <nav
        className="md:hidden"
        style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50,
          background: 'rgba(6,8,15,0.96)',
          borderTop: '1px solid rgba(255,255,255,0.07)',
          backdropFilter: 'blur(20px)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-around',
          height: '60px',
        }}
      >
        {MOBILE_NAV.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px',
                padding: '8px 12px', textDecoration: 'none',
                color: active ? '#4d88ff' : 'rgba(255,255,255,0.3)',
                transition: 'color 0.15s',
              }}
            >
              <Icon size={19} />
              <span style={{ fontSize: '10px', fontWeight: 500 }}>{label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
