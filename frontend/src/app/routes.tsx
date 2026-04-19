import { createBrowserRouter, useNavigate } from 'react-router';
import { Landing } from './pages/Landing';
import { DOISearch } from './pages/DOISearch';
import { PaperDetail } from './pages/PaperDetail';
import { DeepResearch } from './pages/DeepResearch';
import { PaperReview } from './pages/PaperReview';
import { Settings } from './pages/Settings';

function NotFound() {
  const navigate = useNavigate();
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      background: '#06080f', gap: '16px',
    }}>
      <p style={{
        fontSize: '72px',
        fontFamily: "'JetBrains Mono', monospace",
        color: 'rgba(255,255,255,0.06)',
        lineHeight: 1,
      }}>404</p>
      <p style={{ fontSize: '16px', color: 'rgba(255,255,255,0.4)' }}>Page not found</p>
      <button
        onClick={() => navigate('/')}
        style={{
          padding: '10px 20px', borderRadius: '10px',
          background: 'rgba(77,136,255,0.12)',
          border: '1px solid rgba(77,136,255,0.28)',
          color: '#4d88ff', cursor: 'pointer', fontSize: '14px',
        }}
      >
        Go Home
      </button>
    </div>
  );
}

export const router = createBrowserRouter([
  { path: '/', Component: Landing },
  { path: '/doi', Component: DOISearch },
  { path: '/paper', Component: PaperDetail },
  { path: '/paper-review', Component: PaperReview },
  { path: '/deep-research', Component: DeepResearch },
  { path: '/settings', Component: Settings },
  { path: '*', Component: NotFound },
]);
