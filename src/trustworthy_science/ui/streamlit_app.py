"""Streamlit UI for the Trustworthy Science Truth Filter.

Tabs:
  1. Score Papers      — DOI / PMID / text-query scoring with structured report cards
  2. Deep Research     — LLM-driven multi-query research pipeline with literature review + chat
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

# Ensure src/ is on path when running directly
_src = Path(__file__).parent.parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
    sys.path.insert(0, str(_src / "src"))

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Trustworthy Science",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Load base config from file (once at module level)
# ---------------------------------------------------------------------------

import yaml  # noqa: E402

base_config_path = Path(__file__).parent.parent.parent / "config" / "scoring.yaml"
try:
    with open(base_config_path) as _f:
        _base_config = yaml.safe_load(_f)
    _base_yaml_text = base_config_path.read_text()
except Exception:
    _base_config = {}
    _base_yaml_text = "# Could not load scoring.yaml\n"

# ---------------------------------------------------------------------------
# Sidebar — full YAML config editor
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🔬 Trustworthy Science")
    st.caption("AI-powered credibility filter for scientific literature")
    st.divider()

    st.subheader("Scoring Weights")
    col_a, col_b = st.columns(2)
    with col_a:
        w_retract = st.number_input("Retraction cap", 0, 50, 25, step=1)
        w_no_data = st.number_input("No data deposit", 0, 20, 8, step=1)
        w_replicated = st.number_input("Replicated bonus", 0, 20, 10, step=1)
    with col_b:
        w_open_data = st.number_input("Open data bonus", 0, 15, 6, step=1)
        w_methods = st.number_input("Methods nudge %", 0, 50, 15, step=5)

    st.divider()

    min_tier = st.selectbox(
        "Minimum tier to include (filter only)",
        ["Caution", "Trusted", "Untrusted"],
        index=0,
    )
    st.divider()
    st.caption("v0.1 — Hackathon MVP")


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

from trustworthy_science import TruthFilter  # noqa: E402


def _build_config() -> dict:
    """Overlay the five sidebar slider values onto the base file config."""
    import copy, json
    cfg = json.loads(json.dumps(_base_config))  # deep copy via JSON round-trip
    scoring = cfg.setdefault("scoring", {})
    scoring["retraction_cap"] = w_retract
    scoring["no_data_deposit_penalty"] = w_no_data
    scoring["replicated_bonus"] = w_replicated
    scoring["open_data_bonus"] = w_open_data
    scoring["methods_nudge_pct"] = w_methods
    return cfg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIER_ORDER = {"Trusted": 2, "Caution": 1, "Untrusted": 0}
_TIER_COLOR = {"Trusted": "#2ecc71", "Caution": "#f39c12", "Untrusted": "#e74c3c"}


def tier_badge(tier: str, score: int) -> str:
    color = _TIER_COLOR.get(tier, "#95a5a6")
    return (
        f"<div style='text-align:center;background:{color};border-radius:8px;padding:6px;'>"
        f"<span style='color:white;font-size:1.5rem;font-weight:bold'>{score}</span><br/>"
        f"<span style='color:white;font-size:0.75rem'>{tier}</span></div>"
    )


def render_structured_report(result: dict) -> None:
    """Render a full structured credibility report in Streamlit."""
    sr = result.get("structured_report")
    if sr is not None and hasattr(sr, "model_dump"):
        sr = sr.model_dump()

    tier = result.get("tier", "Unknown")
    score = result.get("score", 0)
    color = _TIER_COLOR.get(tier, "#95a5a6")
    coverage = result.get("coverage", "metadata_only")

    # Header
    col_s, col_t = st.columns([1, 3])
    with col_s:
        st.metric("Trust Score", f"{score}/100")
    with col_t:
        st.markdown(
            f"<div style='background:{color};border-radius:6px;padding:6px 12px;display:inline-block'>"
            f"<span style='color:white;font-weight:bold'>{tier}</span></div>",
            unsafe_allow_html=True,
        )

    if coverage == "metadata_only":
        st.warning("Metadata-only scoring (35% confidence) — full text unavailable.")
    elif coverage == "abstract_only":
        st.info("Abstract-only scoring (60% confidence) — limited checks.")

    if sr:
        # Overall verdict
        if sr.get("overall_verdict"):
            st.info(sr["overall_verdict"])

        # Score breakdown
        breakdown = sr.get("score_breakdown", [])
        if breakdown:
            st.subheader("Score Breakdown")
            import pandas as pd
            rows = []
            for entry in breakdown:
                pct = entry.get("score_pct", 0) if isinstance(entry, dict) else entry.score_pct
                dim = entry.get("dimension", "") if isinstance(entry, dict) else entry.dimension
                rat = entry.get("rationale", "") if isinstance(entry, dict) else entry.rationale
                rows.append({"Dimension": dim, "Score (%)": pct, "Rationale": rat})
            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Dimension": st.column_config.TextColumn(width="small"),
                    "Score (%)": st.column_config.ProgressColumn(
                        min_value=0, max_value=100, format="%d%%", width="small"
                    ),
                    "Rationale": st.column_config.TextColumn(width="large"),
                },
            )

        # Key concerns
        concerns = sr.get("key_concerns", [])
        if concerns:
            with st.expander("Key Concerns", expanded=True):
                for c in concerns:
                    st.markdown(f"- {c}")

        # Positive signals
        positives = sr.get("positive_signals", [])
        if positives:
            with st.expander("Positive Signals", expanded=False):
                for p in positives:
                    st.markdown(f"- {p}")

        # Recommendation
        rec = sr.get("recommendation", "")
        if rec:
            st.success(f"**Recommendation:** {rec}")

    else:
        # Fallback: flat summary + flags
        summary = result.get("summary", "")
        if summary:
            st.write(summary)
        if result.get("hard_flags"):
            st.error("Critical flags: " + " | ".join(result["hard_flags"]))
        if result.get("soft_flags"):
            st.warning("Concerns: " + " | ".join(result["soft_flags"]))
        if result.get("quality_signals"):
            st.success("Positive signals: " + " | ".join(result["quality_signals"]))


def render_paper_card(r: dict, key_prefix: str = "", detail_state_key: str = "selected_paper_data") -> None:
    tier = r.get("tier", "Unknown")
    score = r.get("score", 0)
    color = _TIER_COLOR.get(tier, "#95a5a6")
    hard = ", ".join(r.get("hard_flags", []))
    soft = ", ".join(r.get("soft_flags", [])[:3])
    quality = ", ".join(r.get("quality_signals", [])[:3])

    with st.container(border=True):
        c1, c2 = st.columns([8, 2])
        with c1:
            st.markdown(f"**{r.get('title', r.get('doi', '—'))}**")
            st.caption(f"{r.get('venue', '')}  |  {r.get('year', '')}  |  DOI: {r.get('doi','—')}")
            if hard:
                st.markdown(f"<span style='color:#e74c3c'>● HARD: {hard}</span>", unsafe_allow_html=True)
            if soft:
                st.markdown(f"<span style='color:#f39c12'>● SOFT: {soft}</span>", unsafe_allow_html=True)
            if quality:
                st.markdown(f"<span style='color:#2ecc71'>● GOOD: {quality}</span>", unsafe_allow_html=True)
        with c2:
            st.markdown(tier_badge(tier, score), unsafe_allow_html=True)

        doi = r.get("doi")
        pmid = r.get("pmid")
        uid = doi or pmid or r.get("title", "")
        key = f"{key_prefix}_detail_{uid}"
        if uid and st.button("Full Report", key=key):
            st.session_state["selected_paper"] = uid
            st.session_state[detail_state_key] = r


# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

tab_score, tab_deep = st.tabs(["Score Papers", "Deep Research"])

# ===========================================================================
# Tab 1 — Score Papers
# ===========================================================================

with tab_score:
    st.header("Score Papers")
    st.caption("Score by DOI, PMID, or free-text query. Results include a structured credibility report.")

    input_mode = st.radio(
        "Input mode",
        ["DOI(s)", "PMID(s)", "Text query"],
        horizontal=True,
    )

    if input_mode == "DOI(s)":
        doi_input = st.text_area(
            "DOIs (one per line)",
            placeholder="10.1038/s41586-020-2748-1\n10.1016/j.cell.2020.04.004",
            height=100,
        )
        pmid_input = None
        query_input = None
        top_k = 10
    elif input_mode == "PMID(s)":
        pmid_input = st.text_area(
            "PMIDs (one per line)",
            placeholder="23193264\n33301246",
            height=100,
        )
        doi_input = None
        query_input = None
        top_k = 10
    else:
        query_input = st.text_input(
            "Research question",
            placeholder="CRISPR cancer therapy clinical trials",
        )
        top_k = st.slider("Max papers to retrieve", 3, 20, 10)
        doi_input = None
        pmid_input = None

    run_score = st.button("Run Scoring", type="primary", key="run_score")

    if run_score:
        tf = TruthFilter(config=_build_config())
        results: list[dict] = []

        with st.spinner("Scoring papers — this may take a minute..."):
            if input_mode == "DOI(s)" and doi_input:
                dois = [d.strip() for d in doi_input.strip().splitlines() if d.strip()]
                results = tf.score_papers(dois=dois)
            elif input_mode == "PMID(s)" and pmid_input:
                for p in pmid_input.strip().splitlines():
                    p = p.strip()
                    if p:
                        r = tf.score_single_by_pmid(p)
                        if r:
                            results.append(r)
            elif input_mode == "Text query" and query_input:
                results = tf.score_papers(query=query_input, top_k=top_k)
            else:
                st.warning("Please enter a valid input.")
                st.stop()

        if not results:
            st.error("No results returned.")
            st.stop()

        st.session_state["score_results"] = results

    results = st.session_state.get("score_results", [])
    if results:
        min_tier_val = TIER_ORDER.get(min_tier, 1)
        filtered = [r for r in results if TIER_ORDER.get(r.get("tier", "Untrusted"), 0) >= min_tier_val]

        tab_all, tab_filtered, tab_detail = st.tabs([
            f"All ({len(results)})",
            f"Filtered ≥ {min_tier} ({len(filtered)})",
            "Paper Detail",
        ])

        with tab_all:
            for r in results:
                render_paper_card(r, key_prefix="all")

        with tab_filtered:
            if filtered:
                for r in filtered:
                    render_paper_card(r, key_prefix="filt")
            else:
                st.warning(f"No papers met the minimum tier '{min_tier}'.")

        with tab_detail:
            sel_data = st.session_state.get("selected_paper_data")
            if not sel_data:
                st.info("Click **Full Report** on any paper card to see the detailed credibility report.")
            else:
                st.subheader(sel_data.get("title", sel_data.get("doi", "—")))
                st.caption(f"{sel_data.get('venue', '')} | {sel_data.get('year', '')} | DOI: {sel_data.get('doi','—')}")
                st.divider()
                render_structured_report(sel_data)
                with st.expander("Raw JSON"):
                    # Serialise Pydantic models
                    safe = {}
                    for k, v in sel_data.items():
                        if hasattr(v, "model_dump"):
                            safe[k] = v.model_dump()
                        elif isinstance(v, list):
                            safe[k] = [x.model_dump() if hasattr(x, "model_dump") else x for x in v]
                        else:
                            safe[k] = v
                    st.json(safe)


# ===========================================================================
# Tab 2 — Deep Research
# ===========================================================================

with tab_deep:
    st.header("Deep Research")
    st.caption(
        "Describe your research task and the system will automatically extract PICO concepts, "
        "validate them against the MeSH database, generate Boolean PubMed queries, "
        "score all retrieved papers, and build a credibility-filtered literature review."
    )

    research_prompt = st.text_area(
        "Research task",
        placeholder="I want to design a randomized clinical trial for a novel new antibiotic drug",
        height=80,
    )
    col_k, col_tier = st.columns(2)
    with col_k:
        dr_top_k = st.slider("Max papers to fetch", 5, 30, 20, key="dr_top_k")
    with col_tier:
        dr_min_tier = st.selectbox("Min tier for review", ["Caution", "Trusted", "Untrusted"], key="dr_min_tier")

    run_deep = st.button("Run Deep Research", type="primary", key="run_deep")

    if run_deep and research_prompt.strip():
        tf_dr = TruthFilter(config=_build_config())

        with st.spinner("Running deep research pipeline (this may take several minutes)..."):
            dr_result = tf_dr.deep_research(
                prompt=research_prompt.strip(),
                top_k=dr_top_k,
                min_tier=dr_min_tier,
            )

        st.session_state["dr_result"] = dr_result
        st.session_state["dr_prompt"] = research_prompt.strip()
        st.success(
            f"Deep research complete. "
            f"{len(dr_result.get('accepted_papers', []))} papers accepted "
            f"({len(dr_result.get('scored_papers', []))} scored total)."
        )
    elif run_deep:
        st.warning("Please enter a research task description.")

    dr_result = st.session_state.get("dr_result")
    if dr_result:
        queries = dr_result.get("generated_queries", [])
        accepted = dr_result.get("accepted_papers", [])
        scored = dr_result.get("scored_papers", [])
        review = dr_result.get("literature_review", "")
        cited = dr_result.get("cited_papers", [])
        session_id = dr_result.get("session_id", "")
        collection_name = dr_result.get("collection_name", "")
        mesh_terms = dr_result.get("mesh_terms", [])
        query_metadata = dr_result.get("query_metadata", [])

        # Build a lookup: query text → pmid_count for easy display
        _qmeta = {m.get("query", ""): m.get("pmid_count", 0) for m in query_metadata}

        # ---------------------------------------------------------------
        # Generated queries + MeSH terms panel
        # ---------------------------------------------------------------
        if queries or mesh_terms:
            with st.expander("Search Strategy", expanded=True):
                # MeSH terms validated
                if mesh_terms:
                    st.markdown("**MeSH Terms Used**")
                    st.markdown(
                        " &nbsp;·&nbsp; ".join(
                            f"`{t}`" for t in mesh_terms
                        ),
                        unsafe_allow_html=True,
                    )
                    st.divider()

                # Generated Boolean queries with result counts
                if queries:
                    st.markdown("**Generated PubMed Queries**")
                    for i, q in enumerate(queries, 1):
                        count = _qmeta.get(q, None)
                        count_badge = f" — **{count} results**" if count is not None else ""
                        st.markdown(f"**{i}.** `{q}`{count_badge}")

        st.divider()

        # ---------------------------------------------------------------
        # Literature review
        # ---------------------------------------------------------------
        st.subheader("Literature Review")
        if review:
            st.write(review)
        else:
            st.warning("No literature review could be generated.")

        # Citations
        if cited:
            with st.expander(f"Cited Papers ({len(cited)})", expanded=False):
                for p in cited:
                    c = _TIER_COLOR.get(p.get("tier", ""), "#95a5a6")
                    st.markdown(
                        f"- **{p.get('title', 'Unknown')}** ({p.get('year', '')}) "
                        f"— DOI: {p.get('doi', '—')} "
                        f"| Score: {p.get('score', 0)}/100 "
                        f"| <span style='color:{c}'>{p.get('tier','')}</span>",
                        unsafe_allow_html=True,
                    )

        st.divider()

        # ---------------------------------------------------------------
        # Accepted paper cards
        # ---------------------------------------------------------------
        if accepted:
            st.subheader(f"Accepted Papers ({len(accepted)} ≥ {dr_min_tier})")
            for r in accepted:
                render_paper_card(r, key_prefix="dr_acc", detail_state_key="dr_selected_paper_data")
        elif scored:
            st.warning(f"No papers met the minimum tier '{dr_min_tier}'. Showing all scored papers:")
            for r in scored:
                render_paper_card(r, key_prefix="dr_scored", detail_state_key="dr_selected_paper_data")

        # -------------------------------------------------------------------
        # Paper Detail panel (Deep Research)
        # -------------------------------------------------------------------
        dr_sel = st.session_state.get("dr_selected_paper_data")
        if dr_sel:
            st.divider()
            st.subheader("Paper Detail")
            st.subheader(dr_sel.get("title", dr_sel.get("doi", "—")))
            st.caption(
                f"{dr_sel.get('venue', '')} | {dr_sel.get('year', '')} | DOI: {dr_sel.get('doi', '—')}"
            )
            st.divider()
            render_structured_report(dr_sel)
            with st.expander("Raw JSON"):
                safe = {}
                for k, v in dr_sel.items():
                    if hasattr(v, "model_dump"):
                        safe[k] = v.model_dump()
                    elif isinstance(v, list):
                        safe[k] = [x.model_dump() if hasattr(x, "model_dump") else x for x in v]
                    else:
                        safe[k] = v
                st.json(safe)
        else:
            st.divider()
            st.info("Click **Full Report** on any paper card above to see its detailed credibility report.")

        st.divider()

        # ---------------------------------------------------------------
        # Chat window
        # ---------------------------------------------------------------
        st.subheader("Chat with the Research Collection")
        if not collection_name:
            st.warning("No ChromaDB collection available — run Deep Research first.")
        else:
            st.caption(
                f"Ask follow-up questions about the literature. "
                f"Collection: `{collection_name}`  |  Session: `{session_id[:8]}...`"
            )

            if "chat_history" not in st.session_state:
                st.session_state["chat_history"] = []

            for turn in st.session_state["chat_history"]:
                role = turn["role"]
                with st.chat_message(role):
                    st.write(turn["content"])

            user_q = st.chat_input("Ask a question about the literature...", key="chat_input")
            if user_q:
                from trustworthy_science.agents.research_chat import chat as research_chat

                st.session_state["chat_history"].append({"role": "user", "content": user_q})
                with st.chat_message("user"):
                    st.write(user_q)

                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            tf_chat = TruthFilter(config=_build_config())
                            answer = research_chat(
                                session_id=session_id,
                                user_message=user_q,
                                collection_name=collection_name,
                                config=tf_chat._config,
                            )
                        except Exception as exc:
                            answer = f"Error: {exc}"
                    st.write(answer)
                    st.session_state["chat_history"].append({"role": "assistant", "content": answer})
