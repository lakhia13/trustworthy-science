"""Paper Analyzer agent — classifies paper type and characteristics."""

from __future__ import annotations

import json
import logging

from trustworthy_science.llm import get_llm
from trustworthy_science.state import PaperState

logger = logging.getLogger(__name__)

_PAPER_TYPE_PROMPT = """\
You are an expert academic who specializes in research methodology.
Your task is to classify a scientific paper based on its title and abstract.

Paper Title: {title}
Abstract:
---
{abstract}
---

First, classify the paper into ONE of the following primary types:
- "quantitative_study": Original research testing a hypothesis with numerical data.
- "qualitative_study": Original research gathering non-numerical data (interviews, observations).
- "mixed_methods_study": A study that explicitly combines quantitative and qualitative methods.
- "meta_analysis": A statistical analysis that combines the results of multiple scientific studies.
- "systematic_review": A review of a clearly formulated question that uses systematic and explicit methods to identify, select, and critically appraise relevant research.
- "literature_review": A scholarly paper that presents the current knowledge including substantive findings, as well as theoretical and methodological contributions to a particular topic.
- "case_study": An in-depth, detailed examination of a particular case (or cases) within a real-world context.
- "methods_paper": A paper whose primary contribution is a new research method.
- "theoretical_paper": A paper that focuses on developing or refining theory without collecting new data.
- "commentary_or_opinion": An article expressing a personal viewpoint or perspective.

Second, identify all relevant characteristics from the following list:
- "uses_statistical_tests": The abstract mentions statistical analysis (e.g., p-values, t-tests, regression).
- "involves_human_subjects": The study involves human participants.
- "involves_animal_subjects": The study involves non-human animal subjects.
- "is_simulation": The research is based on computer simulations.
- "proposes_new_model_or_algorithm": The paper introduces a new computational model or algorithm.
- "is_longitudinal": The study collects data over a period of time.

Respond with ONLY a single valid JSON object with two keys, "paper_type" and "characteristics".

Example:
{{
  "paper_type": "quantitative_study",
  "characteristics": ["uses_statistical_tests", "involves_human_subjects"]
}}

Now, analyze the provided paper. Return ONLY the JSON.
"""


def paper_analyzer_agent(state: PaperState, config: dict | None = None) -> dict:
    """Node: Use an LLM to classify the paper type and characteristics."""
    cfg = config or {}
    llm_cfg = cfg.get("llm", {})
    max_tokens = int(llm_cfg.get("analyzer_max_tokens", 200))

    abstract = state.stub.abstract
    title = state.stub.title

    if not abstract:
        logger.info("No abstract available for paper type analysis for DOI %s.", state.stub.doi)
        return {}

    try:
        result = _call_llm(
            prompt=_PAPER_TYPE_PROMPT.format(title=title, abstract=abstract),
            max_tokens=max_tokens,
            config=cfg,
        )
        # Basic validation
        if "paper_type" in result and "characteristics" in result:
            return {
                "paper_type": result["paper_type"],
                "characteristics": result["characteristics"],
            }
        else:
            logger.warning("LLM response for paper analyzer was malformed: %s", result)
            return {}
    except Exception as exc:
        logger.warning("Paper analyzer LLM call failed for DOI %s: %s", state.stub.doi, exc)
        return {}


def _call_llm(prompt: str, max_tokens: int, config: dict | None = None) -> dict:
    """Call the LLM and return parsed JSON response."""
    llm = get_llm(max_tokens=max_tokens, config=config, temperature=0.0)

    from langchain_core.messages import HumanMessage
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)
