# Hackathon Judge's Report — Trustworthy Science

## VERDICT: Strong Submission — Top 20% Potential, but with a Critical Gap

---

## 1. Problem Statement Alignment

The use case asks for **4 specific capabilities**. Honest scorecard:

| Requirement | Status | Notes |
|---|---|---|
| **Find & Flag** unreliable papers | ✅ Fully built | P-hacking, retraction, predatory venue, COI, methods flaws |
| **Downgrade or Remove** bad research | ✅ Fully built | `filter_for_rag()` drops papers below min tier from RAG context |
| **Be Critically Minded** — analyze distributions & methodology | ✅ Fully built | P-curve from the exact 2011 paper cited + LLM methodology critique |
| **Citation Networks** — small citation bubbles? | ✅ Partially built | Self-citation ratio + diversity score — no deep graph traversal |
| **Conflict of Interest Analysis** | ⚠️ Partial | Detects presence/absence of COI statement — doesn't analyze funding source names |
| **Replicability Scores** — has another lab replicated this? | ❌ Missing | Retraction check exists but no actual replication lookup |
| **Lay-friendly output** | ⚠️ Partial | CLI is technical; Streamlit UI exists but unclear if polished |
| **PubMed / PMC / BioRxiv sources** | ✅ All three integrated | ArXiv not integrated |

> **Direct hit on the 2011 p-value paper cited in the problem statement** — p-curve analysis was implemented from that exact reference. Judges who read the problem statement carefully will notice and reward this.

---

## 2. What's Genuinely Impressive

**Architecture depth** — a LangGraph multi-agent pipeline with 9 specialized agents running in parallel is not something a team hacks together in a weekend. Most teams submit a single GPT call wrapped in a loop.

**Paper Type Classifier** — sophisticated thinking. Penalizing a theoretical math paper for "no data deposit" is wrong. 8 paper type categories with a type-aware applicability matrix. No other team will have this.

**Configurable scoring in YAML** — everything is tunable without touching code. This is production-thinking. Regeneron scientists could adjust thresholds themselves.

**55/55 tests passing** — "fully tested, fully reproducible" can be said with confidence. Most hackathon projects are untested.

**The scoring formula is explainable** — `70 - penalties + bonuses + methods_nudge`. Every deduction has a reason. Judges can audit it.

---

## 3. The Critical Gap (Be Honest About This)

**Paywalled full text kills 80% of real-world scoring quality.**

Live evidence — the VITAL trial (NEJM, DOI: `10.1056/NEJMoa1811403`) scored **63/Caution** when the real answer is **~85/Trusted**. The flags (`NO_DATA_DEPOSIT`, `NO_CODE_AVAILABILITY`) were false positives purely because the tool couldn't see the paper's methods section.

A judge will ask: *"What happens when I give this a real NEJM paper?"*

Honest answer: *"Metadata-only mode — 35% accuracy — unless the paper is open access on PMC or bioRxiv."*

This is not a disqualifier, but you need a plan.

---

## 4. Gaps vs. the Problem Statement

### Missing: Real Replication Check
The problem statement explicitly says: *"Has any other lab successfully replicated these findings?"*

Retraction status (paper pulled) is checked — but not replication status (paper tried and failed).

### Missing: Knockout Mouse / Drug Discovery Angle
The entire problem statement is framed around Regeneron's knockout mouse crisis. The demo should show a **specific biomedical paper** being scored — not a generic omega-3 trial. Score something in gene knockout, CRISPR, or rare disease — that's the audience.

### Missing: "Before vs. After" RAG Demo
The most compelling demo: show RAG output **without** the filter (hallucinates, cites retracted paper), then **with** the filter (clean, reliable answer). `filter_for_rag()` is built — but no demo of this end-to-end.

---

## 5. What to Add Before Submission (Prioritized)

### High Impact, Low Effort

#### A. Hardcode 3 demo papers in a `demo.py`
One retracted paper, one predatory venue paper, one gold-standard open-access paper. Live demo beats everything. Show the score drop from 80 → 25 when a retraction is added. Judges remember visuals.

```python
# Suggested demo papers:
# RETRACTED:  10.1016/j.jns.2015.03.021  (retracted neuroscience paper)
# GOLD:       10.1371/journal.pmed.1001747 (PLOS Medicine, open access, preregistered)
# PREDATORY:  any paper from a Beall's List venue
```

#### B. Before/After RAG Comparison (30 min of work)

```python
# Without filter: feed 10 papers including retracted ones into an LLM
# With filter: same query, filtered to Trusted only → show answer quality difference
```

#### C. Add drug discovery context to Untrusted verdicts
When a paper scores Untrusted, surface:
> "Basing a drug target hypothesis on this paper would carry elevated risk of downstream replication failure."

### Medium Impact, Medium Effort

#### D. Replication Database Lookup
[ReplicationWiki](http://replicationwiki.wikidot.com/) and [SSRP](https://www.socialsciencereproduction.org/) have APIs. Even checking if a DOI appears in a "failed replication" list directly addresses the problem statement's explicit ask.

#### E. Funding Source Name Detection
Currently: detect presence/absence of COI.
Upgrade: if "Pfizer", "Merck", "industry" appears in funding with no COI disclosure → flag `INDUSTRY_ONLY_FUNDING_NO_COI`.

### Great Ideas for Q&A (Mention, Don't Build)

- **Benford's Law on reported statistics** — tables of numbers should follow Benford's distribution; deviations signal data fabrication
- **Figure duplication detection** — image similarity hashing across figures catches image manipulation fraud
- **Co-authorship network graph** — visualize when the same 5 people only cite each other
- **Temporal p-value drift** — track if a research group's p-values are suspiciously clustered at 0.049 across all their papers over time

---

## 6. Presentation Strategy

**Open with the Regeneron story** — "A mouse model that didn't replicate cost years of research. We built the filter that would have caught it." Don't start with architecture.

**Lead with a live demo**, not slides. Score a real paper in real time. The CLI output with color-coded flags reads well on a projector.

**Name three key differentiators:**
1. Type-aware scoring (nobody else will have this)
2. P-curve analysis from the exact statistical method the problem cited
3. RAG-ready API — one function call filters an entire literature search

**Anticipate the hard questions:**

| Question | Answer |
|---|---|
| *"What about paywalled papers?"* | "Open access is 50%+ of biomedical literature and growing. PMC alone has 9M full-text papers." |
| *"How do you validate your scores?"* | "55 unit tests, plus we manually verified against known retracted and gold-standard papers." |
| *"Couldn't an LLM just do this in one prompt?"* | "An LLM hallucinates retraction status and has no p-value extraction. Our deterministic scoring layer is auditable — Regeneron's scientists can read exactly why a score dropped." |

---

## 7. Overall Judge Score

| Dimension | Score | Comment |
|---|---|---|
| Problem fit | 8/10 | Hits all explicit asks; missing replication lookup |
| Technical depth | 9/10 | Multi-agent, tested, configurable — genuinely impressive |
| Innovation | 8/10 | Paper type classifier + type-aware scoring is original |
| Presentation readiness | 6/10 | Needs a live demo story and before/after RAG |
| Real-world viability | 7/10 | Paywall gap is real but solvable |
| **Overall** | **38/50** | **Top tier with a focused push before submission** |

---

> The project is solid. The gap is storytelling and the demo, not the code.
> Spend the remaining time on the `demo.py` before/after RAG script. **That's what wins hackathons.**
