"""Streamlit demo UI for the Trustworthy Science Truth Filter."""

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
# Sidebar — config & controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🔬 Trustworthy Science")
    st.caption("AI-powered credibility filter for scientific literature")
    st.divider()

    st.subheader("Input")
    mode = st.radio("Search mode", ["DOI lookup", "Research query"])

    if mode == "DOI lookup":
        doi_input = st.text_area(
            "DOIs (one per line)",
            placeholder="10.1038/s41586-020-2748-1\n10.1016/j.cell.2020.04.004",
            height=120,
        )
        query_input = None
    else:
        query_input = st.text_input(
            "Research question",
            placeholder="GLP-1 receptor agonists in NASH treatment",
        )
        doi_input = None
        top_k = st.slider("Max papers to retrieve", 3, 30, 10)

    min_tier = st.selectbox("Minimum tier to include", ["Caution", "Trusted", "Untrusted"], index=0)

    st.divider()
    st.subheader("Scoring weights")
    st.caption("These values update config/scoring.yaml live.")

    col1, col2 = st.columns(2)
    with col1:
        w_retract = st.number_input("Retraction cap", value=25, min_value=0, max_value=50)
        w_no_data = st.number_input("No data deposit", value=8, min_value=0, max_value=20)
        w_phack = st.number_input("P-hack penalty (hard)", value=0, min_value=0, max_value=50)
    with col2:
        w_replicated = st.number_input("Replicated bonus", value=10, min_value=0, max_value=20)
        w_open_data = st.number_input("Open data bonus", value=6, min_value=0, max_value=15)
        w_methods = st.number_input("Methods nudge weight", value=15, min_value=0, max_value=50, step=5)

    run_btn = st.button("Run Truth Filter", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title("Truth Filter")
st.caption("Credibility scoring for biomedical literature — signals of concern, not accusations.")

if not run_btn:
    st.info(
        "Enter one or more DOIs or a research question in the sidebar and click **Run Truth Filter**."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Build dynamic config from sidebar
# ---------------------------------------------------------------------------

from trustworthy_science import TruthFilter  # noqa: E402

base_config_path = Path(__file__).parent.parent.parent / "config" / "scoring.yaml"
try:
    import yaml
    with open(base_config_path) as f:
        config = yaml.safe_load(f)
except Exception:
    config = {}

# Override with slider values
config.setdefault("tiers", {})["hard_flag_cap"] = w_retract
config.setdefault("soft_flags", {}).setdefault("NO_DATA_DEPOSIT", {})["penalty"] = w_no_data
config.setdefault("quality_signals", {}).setdefault("INDEPENDENTLY_REPLICATED", {})["bonus"] = w_replicated
config.setdefault("quality_signals", {}).setdefault("OPEN_DATA", {})["bonus"] = w_open_data
config.setdefault("scoring", {})["methods_nudge_weight"] = w_methods / 100.0

tf = TruthFilter(config=config)

# ---------------------------------------------------------------------------
# Run scoring
# ---------------------------------------------------------------------------

with st.spinner("Running credibility agents..."):
    if mode == "DOI lookup" and doi_input:
        dois = [d.strip() for d in doi_input.strip().splitlines() if d.strip()]
        results = tf.score_papers(dois=dois)
    elif mode == "Research query" and query_input:
        results = tf.score_papers(query=query_input, top_k=top_k)
    else:
        st.warning("Please enter a DOI or research question.")
        st.stop()

if not results:
    st.error("No results returned. Check your input or API availability.")
    st.stop()

# ---------------------------------------------------------------------------
# Before / After comparison
# ---------------------------------------------------------------------------

TIER_ORDER = {"Trusted": 2, "Caution": 1, "Untrusted": 0}
min_tier_val = TIER_ORDER.get(min_tier, 1)

naive = results  # unfiltered
filtered = [r for r in results if TIER_ORDER.get(r.get("tier", "Untrusted"), 0) >= min_tier_val]

tab_naive, tab_filtered, tab_detail = st.tabs(
    ["Naive (unfiltered)", f"Truth-Filtered (≥ {min_tier})", "Paper Detail"]
)

# Helper: tier colour
def tier_color(tier: str) -> str:
    return {"Trusted": "#2ecc71", "Caution": "#f39c12", "Untrusted": "#e74c3c"}.get(tier, "#95a5a6")


def render_result_cards(papers: list[dict]) -> str | None:
    """Render paper cards; return DOI of clicked paper (via session state)."""
    for r in papers:
        tier = r.get("tier", "Unknown")
        score = r.get("score", 0)
        color = tier_color(tier)
        hard = ", ".join(r.get("hard_flags", []))
        soft = ", ".join(r.get("soft_flags", [])[:3])
        quality = ", ".join(r.get("quality_signals", [])[:3])

        with st.container(border=True):
            c1, c2 = st.columns([8, 2])
            with c1:
                st.markdown(f"**{r.get('title', r.get('doi', '—'))}**")
                st.caption(f"{r.get('venue', '')}  |  {r.get('year', '')}")
                if hard:
                    st.markdown(f"<span style='color:#e74c3c'>● HARD: {hard}</span>", unsafe_allow_html=True)
                if soft:
                    st.markdown(f"<span style='color:#f39c12'>● SOFT: {soft}</span>", unsafe_allow_html=True)
                if quality:
                    st.markdown(f"<span style='color:#2ecc71'>● GOOD: {quality}</span>", unsafe_allow_html=True)
            with c2:
                st.markdown(
                    f"<div style='text-align:center;background:{color};border-radius:8px;padding:6px'>"
                    f"<span style='color:white;font-size:1.6rem;font-weight:bold'>{score}</span><br/>"
                    f"<span style='color:white;font-size:0.8rem'>{tier}</span></div>",
                    unsafe_allow_html=True,
                )
                if r.get("doi") and st.button("Details", key=f"detail_{r['doi']}"):
                    st.session_state["selected_doi"] = r["doi"]


with tab_naive:
    st.subheader(f"{len(naive)} papers (unfiltered)")
    render_result_cards(naive)

with tab_filtered:
    delta = len(naive) - len(filtered)
    st.subheader(f"{len(filtered)} papers passed the filter ({delta} removed)")
    if filtered:
        render_result_cards(filtered)
    else:
        st.warning(f"No papers met minimum tier '{min_tier}'.")

# ---------------------------------------------------------------------------
# Paper detail pane
# ---------------------------------------------------------------------------

with tab_detail:
    selected = st.session_state.get("selected_doi")
    if not selected:
        st.info("Click **Details** on any paper to see the full credibility report.")
    else:
        detail = next((r for r in results if r.get("doi") == selected), None)
        if detail is None:
            st.warning(f"No detail found for {selected}")
        else:
            tier = detail.get("tier", "Unknown")
            score = detail.get("score", 0)
            color = tier_color(tier)

            st.subheader(detail.get("title", selected))
            st.caption(f"{detail.get('venue', '')} | {detail.get('year', '')} | DOI: {selected}")

            # Score gauge
            col_score, col_tier = st.columns([1, 3])
            with col_score:
                st.metric("Trust Score", f"{score}/100")
            with col_tier:
                st.markdown(
                    f"<div style='background:{color};border-radius:6px;padding:6px 12px;display:inline-block'>"
                    f"<span style='color:white;font-weight:bold'>{tier}</span></div>",
                    unsafe_allow_html=True,
                )

            st.divider()

            # Dimension radar — simple bar chart
            if detail.get("per_dimension"):
                import pandas as pd
                dim_data = pd.DataFrame(
                    list(detail["per_dimension"].items()),
                    columns=["Dimension", "Score (0-1)"],
                ).sort_values("Score (0-1)")
                st.bar_chart(dim_data.set_index("Dimension"))

            # Narrative summary
            st.subheader("Verdict")
            st.write(detail.get("summary", "—"))

            # Flags
            if detail.get("hard_flags"):
                st.error("Critical flags: " + " | ".join(detail["hard_flags"]))
            if detail.get("soft_flags"):
                st.warning("Concerns: " + " | ".join(detail["soft_flags"]))
            if detail.get("quality_signals"):
                st.success("Positive signals: " + " | ".join(detail["quality_signals"]))

            # Raw JSON for judges
            with st.expander("Raw JSON report"):
                st.json(detail)
