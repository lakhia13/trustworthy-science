# Trustworthy Science — Frontend

A modern React + TypeScript UI for the Trustworthy Science credibility assessment tool.

**Stack:** Vite + React 18 + TypeScript + Tailwind CSS + Radix UI  
**Status:** Development  
**Design:** Based on `/FIGMA_DESIGN_BRIEF.md`

---

## Quick Start

### Prerequisites
- Node.js 18+ (or use `fnm install 18`)
- pnpm (or npm/yarn)

### Installation

```bash
cd frontend
pnpm install
```

### Development

```bash
pnpm dev
```

Open http://localhost:5173 in your browser.

### Build for Production

```bash
pnpm build
pnpm preview  # test the build locally
```

---

## Project Structure

```
frontend/
├── src/
│   ├── components/        # Reusable UI components
│   │   ├── Layout/
│   │   ├── Search/
│   │   ├── Results/
│   │   ├── Details/
│   │   └── Common/
│   ├── pages/             # Page-level containers
│   │   ├── Home.tsx
│   │   ├── ScoreByDOI.tsx
│   │   ├── SearchByQuery.tsx
│   │   ├── PaperDetail.tsx
│   │   └── RAGComparison.tsx
│   ├── hooks/             # Custom React hooks
│   ├── store/             # Zustand state management
│   ├── types/             # TypeScript type definitions
│   ├── api/               # API client & calls to backend
│   ├── utils/             # Utility functions
│   ├── styles/            # Global CSS (Tailwind + custom)
│   ├── App.tsx
│   └── main.tsx
├── public/                # Static assets
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── FRONTEND_README.md     # This file
```

---

## Key Components (Planned)

### Layout
- `Header.tsx` — top navigation bar (logo, search, settings)
- `Sidebar.tsx` — optional left sidebar (search history, filters)
- `Footer.tsx` — bottom footer with links

### Pages
- **Home** — landing page with 4 action buttons
- **ScoreByDOI** — input DOIs, display results
- **SearchByQuery** — natural-language query search with filters
- **PaperDetail** — comprehensive credibility report (per-dimension scores, flags, evidence)
- **RAGComparison** — before/after filter comparison

### Common Components
- `ScoreCard.tsx` — displays score, tier, title, flags
- `FlagBadge.tsx` — styled flag code + message
- `DimensionBar.tsx` — horizontal bar chart (per-dimension scores)
- `LoadingSpinner.tsx` — animated loader
- `Toast.tsx` — notifications (success, error, info)

---

## API Integration

### Backend URL
Configured in `src/api/client.ts`:
```typescript
const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

Set via `.env.local`:
```
VITE_API_URL=http://localhost:8000
```

### Endpoints Used
- `POST /score` — score papers (TruthFilter.score_papers)
- `POST /filter` — filter for RAG (TruthFilter.filter_for_rag)
- `GET /paper/:doi` — fetch single paper detail (TruthFilter.score_single)

---

## State Management (Zustand)

Example store (`src/store/searchStore.ts`):
```typescript
export const useSearchStore = create((set) => ({
  query: "",
  topK: 10,
  minTier: "Caution",
  setQuery: (q) => set({ query: q }),
  // ...
}));
```

---

## Styling

**Tailwind CSS** for utility-first styling.  
**Custom colors** in `tailwind.config.ts`:
```javascript
colors: {
  trusted: "#10a456",
  caution: "#f5a623",
  untrusted: "#d32f2f",
}
```

**Global styles** in `src/styles/global.css` (Tailwind directives + custom CSS).

---

## Type Definitions

Key types in `src/types/index.ts`:
```typescript
interface Paper {
  doi: string;
  title: string;
  year?: number;
  venue?: string;
  score: number;
  tier: "Trusted" | "Caution" | "Untrusted";
  summary: string;
  hard_flags: Flag[];
  soft_flags: Flag[];
  quality_signals: Flag[];
}

interface Flag {
  code: string;
  message: string;
  evidence?: EvidenceQuote[];
}
```

---

## Development Workflow

1. **Component-first:** Build isolated components in Storybook (optional) or develop in place
2. **API mocking:** Use `msw` (Mock Service Worker) for API testing during development
3. **Testing:** Unit tests with Vitest + React Testing Library
4. **Linting:** ESLint + Prettier

---

## Environment Variables

Create `.env.local`:
```
VITE_API_URL=http://localhost:8000
VITE_LOG_LEVEL=debug
```

---

## Responsive Design

- **Desktop:** 1280px+ (full UI)
- **Tablet:** 768px–1023px (single column, stacked cards)
- **Mobile:** <768px (hamburger menu, full-width cards)

---

## Performance Tips

- Lazy-load pages with React Router's `lazy()` + `Suspense`
- Memoize expensive components with `React.memo()`
- Virtualize long lists with `react-window` (if needed)
- Use `Vite`'s dynamic imports for code splitting

---

## Accessibility

- Semantic HTML (`<button>`, `<nav>`, `<main>`)
- ARIA labels on interactive elements
- Keyboard navigation (Tab, Enter, Escape)
- Color contrast ≥ 4.5:1
- Screen reader testing

---

## Deployment

### Vercel (Recommended)
```bash
vercel
```

### Docker
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install
COPY . .
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "preview"]
```

### Manual
```bash
pnpm build
# Upload `dist/` folder to your static host
```

---

## Troubleshooting

### Port 5173 already in use
```bash
pnpm dev -- --port 3000
```

### Module not found
```bash
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### Tailwind styles not applying
Make sure `tailwind.config.ts` includes your template paths:
```js
content: ["./src/**/*.{js,ts,jsx,tsx}"]
```

---

## Next Steps

1. Install dependencies: `pnpm install`
2. Start dev server: `pnpm dev`
3. Implement Home page (landing)
4. Build ScoreByDOI search
5. Build SearchByQuery with filters
6. Build PaperDetail page
7. Build RAGComparison page
8. Connect to backend API
9. Add tests
10. Deploy to Vercel

---

## Design Reference

See `/FIGMA_DESIGN_BRIEF.md` for:
- Wireframes for all 5 screens
- Color palette & typography
- Interactive flows & microinteractions
- Mobile responsiveness guidelines
