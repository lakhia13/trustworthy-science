# Frontend Status & Next Steps

**Added:** April 18, 2026  
**Stack:** Vite + React 18 + TypeScript + Tailwind CSS + Radix UI  
**Current:** Prototype from Figma design kit  
**Lines of Code:** ~7,800 React component code

---

## ✅ What's Included

### Structure
- ✅ `frontend/src/app/` — React component library (pre-built)
- ✅ `frontend/src/styles/` — Tailwind CSS configuration
- ✅ `frontend/src/main.tsx` — Entry point
- ✅ `vite.config.ts` — Build configuration
- ✅ `package.json` — Dependencies (Radix UI, Tailwind, lucide-react)
- ✅ `index.html` — HTML template
- ✅ `postcss.config.mjs` — CSS pipeline
- ✅ `tailwind.config.ts` — Tailwind customization

### Documentation
- ✅ `FRONTEND_README.md` — Development guide
- ✅ `FIGMA_DESIGN_BRIEF.md` — UI/UX specifications
- ✅ `FRONTEND_INTEGRATION.md` — Backend integration guide
- ✅ `FRONTEND_STATUS.md` — This file

### Updated Project Files
- ✅ `.gitignore` — Frontend build artifacts ignored
- ✅ Root `.env` — Backend API key (K2_API_KEY)

---

## 📋 What Needs to Be Done (Implementation Checklist)

### Phase 1: Setup & Dependencies
- [ ] `cd frontend && pnpm install` — install all dependencies
- [ ] Verify no build errors: `pnpm build`
- [ ] Start dev server: `pnpm dev` — should open on port 5173

### Phase 2: Backend API Integration
- [ ] Create `src/api/client.ts` — Axios-based API client
- [ ] Create `src/types/index.ts` — TypeScript interfaces (Paper, Flag, etc.)
- [ ] Create `src/store/` — Zustand state management (search, results, filters)
- [ ] Wire API calls to backend (`POST /score`, `POST /filter`, `GET /paper/{doi}`)

### Phase 3: Core Pages (5 screens from FIGMA_DESIGN_BRIEF.md)
- [ ] **Page 1: Home/Landing**
  - Components: Hero section, 4 action buttons (Search DOI, Search Query, Bulk Upload, Configure)
  - Route: `/`

- [ ] **Page 2: Search by DOI**
  - Components: Input field (multi-line), Submit button, Results cards
  - Route: `/search/doi`
  - API: POST `/score` with `dois=[]`

- [ ] **Page 3: Search by Query**
  - Components: Query input, Top-K dropdown, Min-Tier filter, Results grouped by tier
  - Route: `/search/query`
  - API: POST `/score` with `query=string`

- [ ] **Page 4: Paper Detail**
  - Components: Score card, Per-dimension bar chart, Flags section (hard/soft/quality)
  - Route: `/paper/:doi`
  - API: GET `/paper/{doi}`

- [ ] **Page 5: Before/After RAG Comparison**
  - Components: Two-column layout, Papers icon grid, LLM answers side-by-side
  - Route: `/rag-comparison`
  - API: POST `/filter` twice (unfiltered + filtered)

### Phase 4: Reusable Components
- [ ] `ScoreCard.tsx` — Score/tier badge with animated bar
- [ ] `FlagBadge.tsx` — Hard/soft/quality flag with icon
- [ ] `ResultCard.tsx` — Paper result card (title, score, top flags)
- [ ] `DimensionBar.tsx` — Per-dimension horizontal bar chart
- [ ] `LoadingSpinner.tsx` — Loading indicator
- [ ] `Toast.tsx` — Notifications (success/error/info)

### Phase 5: Styling & Responsiveness
- [ ] Verify Tailwind colors are set (trusted=green, caution=amber, untrusted=red)
- [ ] Mobile responsive: hamburger menu, stacked cards (<768px)
- [ ] Tablet layout: single column (768–1024px)
- [ ] Desktop layout: full layout (1280px+)

### Phase 6: Testing & Polish
- [ ] Integration tests: frontend ↔ backend API
- [ ] E2E tests: Cypress or Playwright
- [ ] Accessibility audit: keyboard nav, screen readers, color contrast
- [ ] Performance: bundle size, load time

### Phase 7: Deployment
- [ ] Deploy to Vercel (recommended) or Netlify
- [ ] Backend deployed separately (Docker/Cloud Run/Heroku)
- [ ] Environment variables configured (VITE_API_URL)
- [ ] CORS headers verified

---

## 🚀 Quick Start (Right Now)

```bash
# Terminal 1: Backend
source .venv/bin/activate
pytest tests/ -v                # Verify backend works

# Terminal 2: Frontend
cd frontend
pnpm install
pnpm dev

# Terminal 3: Browser
# Open http://localhost:5173
```

---

## 🎯 Priority Order

For the **hackathon submission tomorrow (8 PM)**, focus on:

1. **Home page** (Landing) — showcase the tool
2. **Search by DOI** — let judges score real papers
3. **Paper Detail** — show rich credibility breakdown
4. **RAG Comparison** (if time) — the "wow" factor

Skip for now:
- Bulk CSV upload
- Settings/config UI
- Advanced filters
- User accounts

---

## 📦 Dependencies Already Installed

Core:
- `react@18.3.1`
- `react-dom@18.3.1`
- `vite@6.3.5`
- `typescript@5`

UI/Styling:
- `@mui/material` — Material Design components
- `tailwindcss@4.1` — Utility-first CSS
- `@radix-ui/*` — Unstyled, accessible components (Accordion, Dialog, etc.)
- `lucide-react` — Icon library (check, x, warning, etc.)

Utilities:
- `react-hook-form` — Form handling
- `recharts` — Data visualization
- `react-router` — Client-side routing
- `axios` — HTTP client
- `motion` — Animations (Framer Motion)
- `sonner` — Toast notifications
- `date-fns` — Date utilities

---

## 📁 File Organization

Suggested component structure:

```
src/
├── app/
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   ├── Search/
│   │   │   ├── SearchDOI.tsx
│   │   │   └── SearchQuery.tsx
│   │   ├── Results/
│   │   │   ├── ResultCard.tsx
│   │   │   └── ResultGrid.tsx
│   │   ├── Details/
│   │   │   ├── ScoreCard.tsx
│   │   │   ├── FlagBadge.tsx
│   │   │   └── DimensionChart.tsx
│   │   └── Common/
│   │       ├── LoadingSpinner.tsx
│   │       └── Toast.tsx
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── SearchByDOI.tsx
│   │   ├── SearchByQuery.tsx
│   │   ├── PaperDetail.tsx
│   │   └── RAGComparison.tsx
│   ├── api/
│   │   └── client.ts
│   ├── store/
│   │   ├── searchStore.ts
│   │   └── resultsStore.ts
│   ├── types/
│   │   └── index.ts
│   └── styles/
│       └── globals.css
├── main.tsx
└── App.tsx
```

---

## 🔗 API Endpoints (Backend)

Make sure backend has these implemented:

```
POST /score
  Request: { dois?: string[], query?: string, top_k?: int }
  Response: { papers: Paper[] }

POST /filter
  Request: { query: string, top_k: int, min_tier: "Trusted" | "Caution" | "Untrusted" }
  Response: { papers: Paper[] }

GET /paper/{doi}
  Response: Paper
```

Where `Paper`:
```typescript
{
  doi: string,
  title: string,
  year?: number,
  venue?: string,
  score: number,
  tier: "Trusted" | "Caution" | "Untrusted",
  summary: string,
  hard_flags: Flag[],
  soft_flags: Flag[],
  quality_signals: Flag[],
  coverage: "full_text" | "abstract_only" | "metadata_only"
}
```

---

## 📚 Resources

- [FIGMA Design Brief](./FIGMA_DESIGN_BRIEF.md) — Full UI/UX specs
- [Frontend README](./frontend/FRONTEND_README.md) — Dev guide
- [Integration Guide](./FRONTEND_INTEGRATION.md) — Backend wiring
- [Vite Docs](https://vitejs.dev/)
- [Tailwind Docs](https://tailwindcss.com/)
- [Radix UI Docs](https://radix-ui.com/)

---

## ✨ Next Immediate Action

```bash
cd frontend
pnpm install
pnpm dev
```

Then build the Home page component.

---

**Good luck! The frontend skeleton is ready. Build fast, ship tomorrow at 8 PM. 🚀**
