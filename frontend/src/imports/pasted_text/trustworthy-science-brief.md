# Trustworthy Science — Frontend Design Brief for Figma

**Project:** Trustworthy Science UI Prototype  
**Purpose:** Design a user interface for a scientific credibility assessment tool  
**Audience:** Drug-discovery researchers, literature review teams, RAG pipeline operators  
**Deliverable:** Interactive Figma prototype (mobile responsive + desktop)

---

## 1. Project Overview

Trustworthy Science is an AI-powered tool that evaluates the credibility of scientific papers on a scale of 0–100 and assigns them to three tiers: **Trusted** (green), **Caution** (yellow), **Untrusted** (red).

The tool analyzes papers across multiple dimensions:
- Statistical integrity (p-hacking, effect sizes)
- Reproducibility (open data, code, preregistration)
- Citation patterns (self-citation, diversity)
- Venue reputation (predatory journals, DOAJ index)
- Methodology quality (LLM-based critique)
- Conflict of interest (industry funding disclosure)
- Replication status (verified replication or failed attempts)

**Key use case:** Researchers use this tool to filter literature before feeding it to AI systems (RAG pipelines) or before building drug-discovery hypotheses.

---

## 2. User Personas & Use Cases

### Persona 1: **Researcher (Solo)**
- **Goal:** Quickly assess credibility of 2–3 specific papers by DOI
- **Behavior:** Looks up papers, reads score/summary, decides "cite with caution" or "exclude"
- **Pain point:** Wants to see red flags immediately without scrolling

### Persona 2: **Literature Review Team**
- **Goal:** Filter 50–100 papers from a PubMed search; keep only high-quality ones
- **Behavior:** Runs a bulk search, sorts by tier, downloads a list of "safe" papers
- **Pain point:** Needs fast visual scanning; doesn't want to open 100 detail pages

### Persona 3: **RAG Pipeline Operator**
- **Goal:** Feed only Trusted/Caution papers to an LLM for drug discovery
- **Behavior:** Runs a query ("PCSK9 inhibitors"), applies min-tier filter, exports list
- **Pain point:** Needs API integration; wants to see before/after filtering comparison

---

## 3. Core Screens & Wireframes

### Screen 1: **Landing / Home**
**Purpose:** Entry point; choice of search method

**Layout (Desktop):**
```
┌─────────────────────────────────────────────┐
│  [Logo] Trustworthy Science                 │
│                                             │
│  "Filter bad science before it corrupts     │
│   your AI or drug hypothesis."              │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  [Search by DOI]  [Search by Query]  │   │
│  │  [Bulk Upload CSV] [Configure]       │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  Recent searches:                           │
│  • CRISPR off-target effects (3 papers)    │
│  • GLP-1 receptor agonists (12 papers)     │
│                                             │
└─────────────────────────────────────────────┘
```

**Interactive Elements:**
- 4 large buttons (each with icon + label)
- Clickable recent search cards (shows title + paper count)
- Settings icon (top-right) → configure min-tier, scoring weights

**Color Scheme:**
- Background: light gray (`#f5f7fa`)
- Button background: `#007acc` (Trust blue)
- Text: dark gray (`#1a1a1a`)

---

### Screen 2: **Search by DOI**
**Purpose:** User enters one or more DOIs; tool scores and displays results

**Layout (Desktop):**
```
┌─────────────────────────────────────────────┐
│ < Back    [Trustworthy Science]   [Settings]│
├─────────────────────────────────────────────┤
│                                             │
│  Score by DOI                               │
│  ┌──────────────────────────────────┐       │
│  │ 10.1038/s41586-020-2748-1       │ ✕     │
│  │ 10.1126/science.1127349          │ ✕     │
│  │ [Paste or type DOI...]           │       │
│  └──────────────────────────────────┘       │
│                                             │
│  [Score Papers]  [Clear All]                │
│                                             │
├─────────────────────────────────────────────┤
│  Results (2 papers)                         │
│  ┌─────────────────────────────────────┐    │
│  │ #1  Score: 78/100  [Trusted] ✅     │    │
│  │ Marine ω-3 Fatty Acids...           │    │
│  │ NEJM 2019 | Hard flags: none        │    │
│  │ [View Details] [Copy BibTeX]        │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ #2  Score: 25/100  [Untrusted] ❌   │    │
│  │ COVID-19 Breakthrough Findings...    │    │
│  │ OMICS Journal 2021 | Hard: RETRACTED│    │
│  │ [View Details]                      │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  [Export CSV]  [Add to Bibliography]       │
│                                             │
└─────────────────────────────────────────────┘
```

**Key Elements:**
- Input field: accepts 1+ DOIs (each line a new DOI)
- Result cards (repeating):
  - Ranking number (large, dim)
  - Score badge: `78/100` in Verdana, color-coded by tier
  - Tier label + icon (Trusted=green checkmark, Caution=yellow triangle, Untrusted=red X)
  - Paper title (truncated, overflow → "...")
  - Venue / year (dim gray text)
  - Top 2–3 flags (codes like `RETRACTED`, `NO_DATA_DEPOSIT`)
  - Action buttons: "View Details", "Copy BibTeX"

**Interactions:**
- Hover over result card → slight shadow, cursor pointer
- Click "View Details" → navigate to **Screen 4: Paper Detail**
- Click "Score Papers" → show loading spinner, then populate results
- Tier color should match: Trusted=`#10a456` (green), Caution=`#f5a623` (amber), Untrusted=`#d32f2f` (red)

---

### Screen 3: **Search by Query**
**Purpose:** User types a research question; tool retrieves papers from PubMed/bioRxiv, scores them, optionally applies tier filter

**Layout (Desktop):**
```
┌─────────────────────────────────────────────┐
│ < Back    [Trustworthy Science]   [Settings]│
├─────────────────────────────────────────────┤
│                                             │
│  Search for Papers                          │
│                                             │
│  ┌──────────────────────────────────┐       │
│  │ "What is the evidence that..."   │       │
│  │ [Search box - placeholder text]  │       │
│  └──────────────────────────────────┘       │
│                                             │
│  ┌───────────────────┐ ┌──────────────────┐ │
│  │ Top-K: [10    ▼] │ │ Min Tier: [Any ▼]│ │
│  │ (results to show) │ │ (Trusted/Caution)│ │
│  └───────────────────┘ └──────────────────┘ │
│                                             │
│  [Search]  [Advanced Options]               │
│                                             │
├─────────────────────────────────────────────┤
│                                             │
│  Results (8 qualifying papers)              │
│                                             │
│  ✅ TRUSTED (3)                             │
│  ┌─────────────────────────────────────┐    │
│  │ #1  78/100  GLP-1 receptor...       │    │
│  │ PLOS Medicine 2023 | Open data ✓    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ⚠️  CAUTION (5)                            │
│  ┌─────────────────────────────────────┐    │
│  │ #2  62/100  GLP-1 in Diabetes...    │    │
│  │ Journal XYZ 2022 | Verify claims    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ❌ UNTRUSTED (2)                           │
│  ┌─────────────────────────────────────┐    │
│  │ #3  18/100  GLP-1 Miracle Cure...   │    │
│  │ OMICS 2021 | PREDATORY_VENUE        │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  [Add Selected to Bibliography]             │
│  [Download Full Report]                     │
│                                             │
└─────────────────────────────────────────────┘
```

**Key Elements:**
- Search input: large, centered, with example placeholder
- Two dropdown filters: Top-K (5, 10, 20, 50) and Min Tier (Any, Caution, Trusted)
- Results grouped by tier (color-coded section headers)
- Each result: same card as Screen 2
- Actions: download full report (CSV), add selected papers to bibliography

**Interactions:**
- Dropdown changes → re-filter results in real-time (no refetch needed)
- Checkbox on each card → select/deselect for bulk actions
- "Download Full Report" → export CSV with all scoring details, flags, evidence

---

### Screen 4: **Paper Detail (Full Credibility Report)**
**Purpose:** Show comprehensive score breakdown, flags, quality signals, evidence quotes

**Layout (Desktop):**
```
┌─────────────────────────────────────────────┐
│ < Back    [Trustworthy Science]   [Settings]│
├─────────────────────────────────────────────┤
│                                             │
│  Marine ω-3 Fatty Acids and Prevention...   │
│  New England Journal of Medicine, 2019      │
│  DOI: 10.1056/NEJMoa1811403                 │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │  Score: 78/100                         │ │
│  │  ████████████████░░░░ Tier: Trusted ✅ │ │
│  │                                        │ │
│  │  Safe to include in drug-discovery     │ │
│  │  hypothesis. Key findings are robust. │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  ───────────────────────────────────────── │
│  Credibility Breakdown                      │
│  ───────────────────────────────────────── │
│                                             │
│  Per-Dimension Scores:                      │
│  ┌────────────────────────────────────────┐ │
│  │ Retraction Status     ██████████ 100%  │ │
│  │ Statistical Integrity ████████░░  85%  │ │
│  │ Reproducibility       ████████░░  80%  │ │
│  │ Citation Network      ██████████  95%  │ │
│  │ Methodology Quality   ███████░░░  70%  │ │
│  │ Publication Metadata  ████████░░  85%  │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  ───────────────────────────────────────── │
│  Hard Flags (Critical Issues)                │
│  ───────────────────────────────────────── │
│  [None detected] ✅                          │
│                                             │
│  ───────────────────────────────────────── │
│  Soft Flags (Concerns)                       │
│  ───────────────────────────────────────── │
│  🔴 VENUE_NOT_IN_DOAJ (- 2 pts)             │
│     Journal is paywalled, not in DOAJ.      │
│     Evidence: ISSN 0028-4793               │
│                                             │
│  🔴 NO_PREREGISTRATION (- 1 pt)             │
│     No ClinicalTrials.gov registration ID   │
│     found.                                   │
│                                             │
│  ───────────────────────────────────────── │
│  Quality Signals (Strengths)                 │
│  ───────────────────────────────────────── │
│  ✅ DIVERSE_CITATIONS (+ 4 pts)             │
│     >50% institutional diversity among      │
│     citing papers.                          │
│     Evidence: OpenAlex diversity score 0.64 │
│                                             │
│  ✅ COI_DISCLOSED (+ 2 pts)                 │
│     Conflict of interest statement present. │
│                                             │
│  ───────────────────────────────────────── │
│  Regeneron Impact Assessment                │
│  ───────────────────────────────────────── │
│  "Drug target based on this paper has       │
│   LOW RISK of replication failure. Safe to  │
│   include in target-discovery pipeline."    │
│                                             │
│  [Copy BibTeX] [Export Report] [Share]      │
│                                             │
└─────────────────────────────────────────────┘
```

**Key Elements:**
- **Header section:**
  - Paper title (large, bold)
  - Venue + year (dim)
  - DOI (clickable, copy-to-clipboard icon)
  
- **Score card (prominent):**
  - Large score number (78/100)
  - Animated progress bar (fills left-to-right, color-coded by tier)
  - Tier badge + icon
  - Plain-English verdict ("Safe to include…", "Verify key claims…", etc.)

- **Per-dimension radar or bar chart:**
  - 6 bars (one per agent: retraction, stats, reproducibility, citation, methodology, venue)
  - Each bar: label + percentage + colored fill
  - Hoverable: show tooltip with brief explanation

- **Flags section (3 parts: hard, soft, quality):**
  - Each flag: code (bold), explanation, evidence quote
  - Hard flags: red (❌)
  - Soft flags: yellow (⚠️)
  - Quality signals: green (✅)

- **Regeneron impact line:** callout box explaining practical implications

---

### Screen 5: **Before/After RAG Comparison**
**Purpose:** Show how Truth Filter improves AI research quality by removing bad papers before LLM sees them

**Layout (Desktop - Side-by-side panels):**
```
┌──────────────────────────────────────────────────────┐
│ < Back    [Trustworthy Science]   [Settings]         │
├──────────────────────────────────────────────────────┤
│                                                      │
│  RAG Pipeline Comparison                             │
│  Query: "What is the evidence that PCSK9 inhibitors │
│          reduce cardiovascular events?"              │
│                                                      │
├─────────────────────────┬────────────────────────────┤
│  ❌ WITHOUT Filter      │  ✅ WITH Truth Filter      │
├─────────────────────────┼────────────────────────────┤
│                         │                            │
│  Input Papers: 10       │  Input Papers: 10          │
│  ┌─────────────────┐    │  ┌─────────────────┐       │
│  │ ✅ ✅ ⚠️  ⚠️  ❌  ❌  │  │ ✅ ✅ ⚠️  ⚠️  ❌  ❌  │
│  │ 6 trusted/caution│  │ 6 trusted/caution│
│  │ 4 untrusted     │  │ 4 untrusted     │
│  └─────────────────┘    │  └─────────────────┘       │
│                         │                            │
│  [Papers fed to LLM] ✗  │  [Papers fed to LLM] ✓    │
│  6 included             │  6 included                │
│                         │                            │
│  ┌─────────────────┐    │  ┌─────────────────┐       │
│  │ Includes:       │    │  │ Includes:       │       │
│  │ • Good PLOS     │    │  │ • Good PLOS     │       │
│  │ • NEJM trial    │    │  │ • NEJM trial    │       │
│  │ • Retracted*    │    │  │ • Predatory*    │       │
│  │ • Predatory*    │    │  │ * excluded!     │       │
│  │ * risky!        │    │  └─────────────────┘       │
│  └─────────────────┘    │                            │
│                         │                            │
│  AI Answer (risky):     │  AI Answer (safe):         │
│  ┌─────────────────┐    │  ┌─────────────────┐       │
│  │ "PCSK9 inhibit- │    │  │ "PCSK9 inhibit- │       │
│  │ ors reduce CV   │    │  │ ors reduce CV   │       │
│  │ events based on │    │  │ events based on │       │
│  │ conflicting     │    │  │ 6 high-quality  │       │
│  │ evidence that   │    │  │ trials (NEJM,   │       │
│  │ includes a      │    │  │ PLOS). Evidence │       │
│  │ retracted study │    │  │ is consistent   │       │
│  │ [unreliable]."  │    │  │ and reproducible."       │
│  └─────────────────┘    │  └─────────────────┘       │
│                         │                            │
│  Confidence: LOW ⚠️    │  Confidence: HIGH ✅       │
│  Risk: HIGH ❌         │  Risk: LOW ✅              │
│                         │                            │
├─────────────────────────┴────────────────────────────┤
│                                                      │
│  [Copy Both Answers]  [Report Differences]           │
│  [Adjust Filters]     [Run New Query]                │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**Key Elements:**
- **Two-column layout:** "Without" (left, red accent), "With" (right, green accent)
- **Icon bar:** Visual representation of papers (✅ ⚠️ ❌) — shows at a glance
- **Papers filtered out:** highlight in the filter column
- **LLM answers:** side-by-side text blocks, color-coded
- **Confidence badges:** LOW (red), HIGH (green)
- **Actions:** Copy, report, adjust, rerun

**Interactions:**
- Hover over icon bar → tooltip with paper title and score
- Click "Adjust Filters" → open a filter sidebar (min tier, top-k)
- "Report Differences" → download PDF highlighting excluded papers + their reasons

---

## 4. Navigation Map

```
Landing (Home)
  ├─→ [Search by DOI] ────→ DOI Search ────→ Paper Detail
  ├─→ [Search by Query] ──→ Query Search ──→ Paper Detail
  ├─→ [Bulk Upload] ──────→ CSV Upload ───→ Results Grid
  ├─→ [Configure] ────────→ Settings
  └─→ [RAG Demo] ─────────→ Before/After
```

---

## 5. Color Palette & Typography

### Colors
| Element | Color | Hex | Usage |
|---------|-------|-----|-------|
| Trusted | Green | `#10a456` | Tier badge, checkmarks, positive signals |
| Caution | Amber | `#f5a623` | Tier badge, warnings, soft flags |
| Untrusted | Red | `#d32f2f` | Tier badge, X marks, hard flags |
| Primary | Blue | `#007acc` | Buttons, links, active states |
| Background | Light Gray | `#f5f7fa` | Page background |
| Text | Dark Gray | `#1a1a1a` | Body text |
| Dim Text | Medium Gray | `#666666` | Secondary labels, hints |
| Border | Light Gray | `#e0e0e0` | Dividers, card borders |

### Typography
- **Headings:** Segoe UI / Inter, Bold, 24px–32px
- **Subheadings:** Segoe UI / Inter, 600-weight, 16px–18px
- **Body:** Segoe UI / Inter, Regular, 14px
- **Monospace (code, DOI):** Courier New / Monaco, 12px, gray background

---

## 6. Interactive Components

### Badge Components
- **Score Badge:** `[78/100]` — large number, color-coded background
- **Tier Badge:** Icon + label (`✅ Trusted`, `⚠️ Caution`, `❌ Untrusted`)
- **Flag Badge:** Code + minus/plus sign (`🔴 NO_DATA_DEPOSIT - 3 pts`, `✅ OPEN_DATA + 6 pts`)

### Cards (repeating pattern)
- **Result Card:** title, score, tier, top flags, actions
- **Flag Card:** code, explanation, evidence quote, impact (minus/plus points)
- **Dimension Bar:** label, percentage bar, tooltip on hover

### Buttons
- **Primary:** Blue background, white text, rounded corners (8px)
- **Secondary:** Gray outline, dark text, rounded corners
- **Danger:** Red background, white text (for "delete", "exclude")
- **Icon buttons:** Score, copy, download, share

### Modals / Overlays
- **Settings modal:** dark overlay, centered card, form controls
- **Confirmation dialog:** "Are you sure?" with cancel/confirm buttons
- **Loading state:** spinner + "Scoring papers..." message

---

## 7. Mobile Responsive Behavior

### Tablet (768px – 1024px)
- Single-column layout for search results
- Tier section headers become inline labels
- Cards stack vertically

### Mobile (< 768px)
- Full-width cards
- Bottom navigation bar: Home | Search | History | Settings
- Modals: full-screen overlays
- Sidebar: hamburger menu (collapsible)
- Fonts: slightly smaller (12px body, 20px headings)

---

## 8. Key Microinteractions

1. **Score reveal animation:**
   - Animated bar fill (left-to-right, 0.6s ease-out)
   - Score number appears with fade-in
   - Tier label slides in from right

2. **Flag hover:**
   - Flag card expands slightly (box-shadow deepens)
   - Evidence quote fades in below
   - Tooltip appears: "Click to see full details"

3. **Result click:**
   - Card highlights (border color changes to primary blue)
   - Slide-in transition to Paper Detail screen (from right)

4. **Filter change:**
   - Results grid reflows instantly (no page refresh)
   - Tier section headers update (e.g., "Trusted (7)" → "Trusted (5)")
   - Cards fade in/out as they enter/leave filtered state

5. **Export button:**
   - Button text changes to "Copying..." (0.5s)
   - Success toast: "CSV copied to clipboard" (2s auto-dismiss)

---

## 9. Data Visualization Examples

### Dimension Radar Chart (Alternative to bars)
- 6 axes: Retraction, Stats, Reproducibility, Citations, Methodology, Venue
- Filled polygon showing score profile
- Interactive: hover over each axis → show brief label + tooltip

### Score Distribution Histogram
- When viewing query results: show histogram of scores (0–100)
- Tier bands: green zone (70–100), yellow zone (45–69), red zone (0–45)
- Bars colored by tier

---

## 10. Example User Flows

### Flow 1: Drug-Discovery Researcher (Solo Paper Assessment)
1. Land on home page
2. Click "Search by DOI"
3. Paste `10.1056/NEJMoa1811403` (VITAL trial)
4. Click "Score"
5. See result: 78/100, Trusted, "Safe to include"
6. Click "View Details"
7. Scroll through flags and methodology critique
8. Click "Copy BibTeX" → citation in clipboard
9. Back to home

### Flow 2: RAG Pipeline Team (Bulk Query + Filter)
1. Land on home page
2. Click "Search by Query"
3. Type "GLP-1 receptor agonists in metabolic disease"
4. Set top-k = 20, min-tier = Caution
5. Click "Search"
6. See results grouped by tier (5 Trusted, 8 Caution, 7 Untrusted)
7. Click "RAG Comparison" button
8. See before/after panels side-by-side
9. Download full report (CSV + summaries)
10. Integrate into RAG pipeline

### Flow 3: Literature Review (Settings Customization)
1. Click Settings (top-right)
2. Adjust scoring weights:
   - "Increase penalty for missing data" (-5 pts instead of -3)
   - "Increase bonus for open code" (+8 pts instead of +4)
   - "Raise hard-flag cap" (30 instead of 25)
3. Save settings
4. Run a search → see updated scores

---

## 11. Accessibility Requirements

- **WCAG 2.1 AA compliance** minimum
- **Color contrast:** Text on color backgrounds ≥ 4.5:1
- **Keyboard navigation:** All buttons/links focusable, Tab/Shift+Tab to navigate
- **Screen reader:** alt text on all images, semantic HTML, ARIA labels
- **Mobile:** touch targets ≥ 44×44 px
- **No auto-play audio/video**

---

## 12. Brand & Tone

**Brand voice:** Rigorous, trustworthy, scientific  
**Visual tone:** Clean, minimal, professional (think: Nature journal UI, not social media)  
**Iconography:** Simple, monochromatic icons (checkmark, X, warning triangle, bars)  
**Messaging:** Emphasize credibility, risk, and actionable decisions

Example copy:
- ✅ "Safe to include in drug-discovery hypothesis"
- ⚠️ "Verify key claims before relying on this"
- ❌ "Exclude from analysis or flag prominently"

---

## 13. Deliverables Expected from Figma

1. **Wireframes** (low-fidelity): All 5 screens + mobile variants
2. **High-fidelity mockups** (stylized): All screens with real typography, colors, icons
3. **Interactive prototype:** Clickable flows (Landing → DOI → Detail; Landing → Query → Results → Detail; RAG Comparison)
4. **Component library:** Reusable buttons, cards, badges, modals
5. **Design system doc:** Color palette, typography scale, spacing rules, shadow/elevation
6. **Responsive breakpoints:** Desktop (1280px), Tablet (768px), Mobile (375px)
7. **Micro-interaction specs:** Animation timings, easing, hover states (document in comments)

---

## 14. Success Metrics

- Users can score a paper by DOI in <30 seconds
- Query results are scannable in <10 seconds (clear visual hierarchy)
- Paper detail screen answers "Is this safe to use?" in top 2 lines
- RAG comparison clearly shows value ("Without filter shows risky papers")
- 95%+ of interactions are intuitive without tooltips

---

## 15. Out of Scope (v1)

- User authentication / account management
- Saved libraries or sharing (will add in v2)
- Custom reporting templates
- Integration with Zotero / Mendeley / Notion (v2+)
- Mobile native apps (web-only for v1)

---

**This brief provides everything Figma designers need to build a world-class prototype. Start with wireframes (screens 1–3), then polish the critical path (Search by DOI → Paper Detail). RAG Comparison (Screen 5) is the "wow" factor that should be visually compelling.**

**Timeline estimate:** 4–6 weeks for high-fidelity prototype + interactive flows.
