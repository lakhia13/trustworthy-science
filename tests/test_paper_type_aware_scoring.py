"""
Tests for paper-type-aware credibility scoring.

These tests define the EXPECTED behaviour after implementing paper type
classification.  Run them before implementation to confirm they all fail,
then run again after implementation to confirm they all pass.

Eight representative paper categories, each with a crafted fixture that
contains only the signals a real paper of that type would include.
"""

from __future__ import annotations

import pytest
from trustworthy_science.state import PaperState, PaperStub, ParsedPaper


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _state(
    title: str,
    abstract: str,
    methods: str = "",
    results: str = "",
    full_text: str = "",
    paper_type: str | None = None,
) -> PaperState:
    """Build a PaperState from text components.  Sets coverage=full_text when
    full_text is provided, otherwise abstract_only."""
    stub = PaperStub(
        doi="10.9999/test.typeaware",
        title=title,
        venue="Test Journal",
        year=2023,
        abstract=abstract,
    )
    ft = full_text or " ".join(filter(None, [abstract, methods, results]))
    parsed = ParsedPaper(
        full_text=ft,
        abstract=abstract,
        methods=methods,
        results=results,
    )
    state = PaperState(
        stub=stub,
        parsed=parsed,
        coverage="full_text",
    )
    if paper_type is not None:
        state.paper_type = paper_type
    return state


# ============================================================
# PART 1 — Paper Classifier
# ============================================================

class TestPaperClassifier:
    """classify_paper_type() must identify each category from title+abstract."""

    def _classify(self, title: str, abstract: str) -> str:
        from trustworthy_science.agents.paper_classifier import classify_paper_type
        state = _state(title=title, abstract=abstract)
        result = classify_paper_type(state)
        return result["paper_type"]

    def test_narrative_review(self):
        pt = self._classify(
            title="Molecular mechanisms of autophagy: a comprehensive review",
            abstract=(
                "This review provides an overview of autophagy signalling pathways. "
                "We surveyed 200 studies published between 2000 and 2023 and summarise "
                "current understanding of the regulatory mechanisms involved."
            ),
        )
        assert pt == "review_narrative"

    def test_systematic_review_meta_analysis(self):
        pt = self._classify(
            title="Efficacy of antidepressants in treatment-resistant depression: "
                  "a systematic review and meta-analysis",
            abstract=(
                "We conducted a systematic review following PRISMA guidelines. "
                "We searched PubMed, Cochrane Central, and Embase. "
                "Random-effects meta-analysis was performed on 42 eligible RCTs."
            ),
        )
        assert pt == "systematic_review_meta"

    def test_clinical_trial(self):
        pt = self._classify(
            title="Efficacy of Drug X in treating Condition Y: "
                  "a randomized controlled trial",
            abstract=(
                "Background: We conducted a randomized controlled trial (RCT) to evaluate "
                "Drug X. Registered at ClinicalTrials.gov: NCT02735707. "
                "Patients were randomly assigned 1:1 to Drug X or placebo."
            ),
        )
        assert pt == "clinical_trial"

    def test_case_report(self):
        pt = self._classify(
            title="Bilateral pneumothorax following thoracentesis: a case report",
            abstract=(
                "We report a case of a 45-year-old female who presented with acute "
                "respiratory distress. We describe the clinical course, diagnostic workup, "
                "and management. This rare complication has not been previously reported."
            ),
        )
        assert pt == "case_report"

    def test_opinion_commentary(self):
        pt = self._classify(
            title="Commentary: Rethinking reproducibility standards in neuroscience",
            abstract=(
                "In this perspective we argue that current reproducibility standards are "
                "insufficient. We offer a viewpoint on how the field should reform its "
                "practices and provide recommendations for editors and reviewers."
            ),
        )
        assert pt == "opinion_commentary"

    def test_theoretical(self):
        pt = self._classify(
            title="A mathematical framework for modelling population dynamics "
                  "under environmental stress",
            abstract=(
                "We develop a theoretical framework based on coupled differential equations "
                "to model population dynamics. We derive analytical solutions and prove "
                "stability conditions. No experimental data were collected."
            ),
        )
        assert pt == "theoretical"

    def test_computational_methods(self):
        pt = self._classify(
            title="SeqPipe: a scalable computational pipeline for RNA-seq analysis",
            abstract=(
                "We present SeqPipe, a software tool for end-to-end RNA-seq analysis. "
                "The algorithm implements a novel alignment strategy. Source code is "
                "available at github.com/biolab/seqpipe under the MIT licence."
            ),
        )
        assert pt == "computational_methods"

    def test_empirical_quantitative_fallback(self):
        """Papers without classification signals default to empirical_quantitative."""
        pt = self._classify(
            title="Effects of exercise on cognitive function in elderly adults",
            abstract=(
                "We enrolled 45 participants aged 65-80. Participants completed a "
                "12-week exercise intervention. Cognitive assessments were performed at "
                "baseline and follow-up. p < 0.05 for the primary outcome."
            ),
        )
        assert pt == "empirical_quantitative"


# ============================================================
# PART 2 — Reproducibility Agent (type-aware flag gating)
# ============================================================

class TestReproducibilityTypeAware:
    """
    When paper_type is set in state, the reproducibility agent must only
    penalise criteria that apply to that type.
    """

    def _run(self, state: PaperState) -> dict:
        from trustworthy_science.agents.reproducibility import reproducibility_agent
        return reproducibility_agent(state)

    # ------------------------------------------------------------------
    # 1. Narrative Review — nothing required, nothing penalised
    # ------------------------------------------------------------------
    def test_review_narrative_no_soft_flags(self):
        state = _state(
            title="A comprehensive review of autophagy",
            abstract="This review surveys 200 studies on autophagy mechanisms.",
            paper_type="review_narrative",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_DATA_DEPOSIT" not in soft_codes
        assert "NO_CODE_AVAILABILITY" not in soft_codes
        assert "NO_PREREGISTRATION" not in soft_codes

    def test_review_narrative_repro_score_is_high(self):
        state = _state(
            title="A comprehensive review of autophagy",
            abstract="This review surveys 200 studies on autophagy mechanisms.",
            paper_type="review_narrative",
        )
        result = self._run(state)
        score = result["sub_scores"]["reproducibility"].score
        assert score >= 0.9, f"Expected >=0.9 for review_narrative, got {score}"

    # ------------------------------------------------------------------
    # 2. Clinical Trial — data + prereg expected; code NOT expected
    # ------------------------------------------------------------------
    def test_clinical_trial_prereg_detected(self):
        state = _state(
            title="RCT of Drug X",
            abstract=(
                "Randomized controlled trial. NCT02735707. "
                "Patients randomly assigned to treatment or placebo."
            ),
            paper_type="clinical_trial",
        )
        result = self._run(state)
        quality_codes = [f.code for f in result.get("quality_signals", [])]
        assert "PREREGISTERED" in quality_codes

    def test_clinical_trial_no_code_flag(self):
        """Code availability should NOT be checked for clinical trials."""
        state = _state(
            title="RCT of Drug X",
            abstract="NCT02735707. Patients randomized. No code mentioned.",
            paper_type="clinical_trial",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_CODE_AVAILABILITY" not in soft_codes

    def test_clinical_trial_data_still_required(self):
        """Data deposit IS expected for clinical trials."""
        state = _state(
            title="RCT of Drug X",
            abstract="NCT02735707. Patients randomized. No data deposited.",
            paper_type="clinical_trial",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_DATA_DEPOSIT" in soft_codes

    # ------------------------------------------------------------------
    # 3. Systematic Review / Meta-analysis — prereg NOT required
    # ------------------------------------------------------------------
    def test_systematic_review_no_prereg_flag(self):
        state = _state(
            title="Systematic review of antidepressants",
            abstract=(
                "We followed PRISMA guidelines. Meta-analysis of 42 RCTs. "
                "No pre-registration identifier."
            ),
            paper_type="systematic_review_meta",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_PREREGISTRATION" not in soft_codes

    def test_systematic_review_data_still_required(self):
        """Data extraction tables/supplementary are expected for meta-analyses."""
        state = _state(
            title="Systematic review of antidepressants",
            abstract="PRISMA. Meta-analysis. No data repository mentioned.",
            paper_type="systematic_review_meta",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_DATA_DEPOSIT" in soft_codes

    # ------------------------------------------------------------------
    # 4. Theoretical — nothing required, score high
    # ------------------------------------------------------------------
    def test_theoretical_no_soft_flags(self):
        state = _state(
            title="Mathematical model of population dynamics",
            abstract="We derive differential equations. No data collected.",
            paper_type="theoretical",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert len(soft_codes) == 0, f"Expected no soft flags, got: {soft_codes}"

    def test_theoretical_repro_score_is_high(self):
        state = _state(
            title="Mathematical model of population dynamics",
            abstract="We derive differential equations. No data collected.",
            paper_type="theoretical",
        )
        result = self._run(state)
        score = result["sub_scores"]["reproducibility"].score
        assert score >= 0.9, f"Expected >=0.9 for theoretical, got {score}"

    # ------------------------------------------------------------------
    # 5. Empirical quantitative (good) — data + code present, prereg missing
    # ------------------------------------------------------------------
    def test_empirical_good_open_data_and_code(self):
        state = _state(
            title="Single-cell RNA-seq of tumour microenvironment",
            abstract="Transcriptomic profiling. Data deposited at GEO (GSE123456).",
            methods="Code available at github.com/lab/scrna-pipeline.",
            paper_type="empirical_quantitative",
        )
        result = self._run(state)
        quality_codes = [f.code for f in result.get("quality_signals", [])]
        assert "OPEN_DATA" in quality_codes
        assert "OPEN_CODE" in quality_codes

    def test_empirical_good_still_flags_missing_prereg(self):
        state = _state(
            title="Single-cell RNA-seq of tumour microenvironment",
            abstract="Transcriptomic profiling. Data deposited at GEO (GSE123456).",
            methods="Code available at github.com/lab/scrna-pipeline.",
            paper_type="empirical_quantitative",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_PREREGISTRATION" in soft_codes

    # ------------------------------------------------------------------
    # 6. Empirical quantitative (bad) — BACKWARD COMPATIBILITY
    #    All three soft flags must still be emitted when no signals present
    # ------------------------------------------------------------------
    def test_empirical_bad_all_three_soft_flags(self):
        state = _state(
            title="Effects of exercise on cognitive function",
            abstract="We enrolled 45 participants. p < 0.05. No data deposited.",
            paper_type="empirical_quantitative",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_DATA_DEPOSIT" in soft_codes
        assert "NO_CODE_AVAILABILITY" in soft_codes
        assert "NO_PREREGISTRATION" in soft_codes

    def test_empirical_bad_repro_score_is_low(self):
        """Score must stay ~0.46 — preserving pre-existing behaviour."""
        state = _state(
            title="Effects of exercise on cognitive function",
            abstract="We enrolled 45 participants. p < 0.05. No data deposited.",
            paper_type="empirical_quantitative",
        )
        result = self._run(state)
        score = result["sub_scores"]["reproducibility"].score
        assert score <= 0.50, f"Expected <=0.50 for bad empirical, got {score}"

    # ------------------------------------------------------------------
    # 7. Case Report — nothing required
    # ------------------------------------------------------------------
    def test_case_report_no_soft_flags(self):
        state = _state(
            title="Bilateral pneumothorax: a case report",
            abstract="We report a case of a 45-year-old female with acute respiratory distress.",
            paper_type="case_report",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert len(soft_codes) == 0, f"Expected no soft flags, got: {soft_codes}"

    # ------------------------------------------------------------------
    # 8. Computational methods — code required, data + prereg not required
    # ------------------------------------------------------------------
    def test_computational_code_found_no_data_flag(self):
        state = _state(
            title="SeqPipe: a pipeline for RNA-seq",
            abstract="We present SeqPipe. Code at github.com/biolab/seqpipe.",
            paper_type="computational_methods",
        )
        result = self._run(state)
        quality_codes = [f.code for f in result.get("quality_signals", [])]
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "OPEN_CODE" in quality_codes
        assert "NO_DATA_DEPOSIT" not in soft_codes
        assert "NO_PREREGISTRATION" not in soft_codes

    def test_computational_no_code_flagged(self):
        """Missing code IS a soft flag for computational methods papers."""
        state = _state(
            title="SeqPipe: a pipeline for RNA-seq",
            abstract="We present a novel alignment algorithm. No code link provided.",
            paper_type="computational_methods",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "NO_CODE_AVAILABILITY" in soft_codes


# ============================================================
# PART 3 — Stats Integrity Agent (type-aware waivers)
# ============================================================

class TestStatsIntegrityTypeAware:
    """Non-empirical paper types must not be penalised for effect-size /
    sample-size criteria that simply don't apply to them."""

    def _run(self, state: PaperState) -> dict:
        from trustworthy_science.agents.stats_integrity import stats_integrity_agent
        return stats_integrity_agent(state)

    def test_review_no_effect_size_flag(self):
        state = _state(
            title="Review of cardiovascular risk",
            abstract="We surveyed 200 studies on cardiovascular risk factors.",
            results="These findings suggest a general trend across the literature.",
            paper_type="review_narrative",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "MISSING_EFFECT_SIZES" not in soft_codes

    def test_review_no_small_sample_flag(self):
        state = _state(
            title="Review of cardiovascular risk",
            abstract="We surveyed 200 studies on cardiovascular risk factors.",
            paper_type="review_narrative",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "SMALL_SAMPLE_UNDERPOWERED" not in soft_codes

    def test_theoretical_no_effect_size_flag(self):
        state = _state(
            title="Mathematical model of neural dynamics",
            abstract="We derive analytical solutions for neural population models.",
            paper_type="theoretical",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "MISSING_EFFECT_SIZES" not in soft_codes

    def test_empirical_still_flags_missing_effect_sizes(self):
        """Backward compatibility: empirical papers still get flagged.
        Must have >=3 p-values to trigger the check (agent threshold)."""
        state = _state(
            title="Drug X in elderly patients",
            abstract="n=12 patients. p = 0.03. p = 0.04. p = 0.02. No effect sizes reported.",
            results="p = 0.03, p = 0.04, p = 0.02. Statistically significant.",
            paper_type="empirical_quantitative",
        )
        result = self._run(state)
        soft_codes = [f.code for f in result.get("soft_flags", [])]
        assert "MISSING_EFFECT_SIZES" in soft_codes


# ============================================================
# PART 4 — Composite score end-to-end
# ============================================================

class TestCompositeScoreTypeAware:
    """End-to-end: running both repro + stats agents on type-classified states
    must produce scores in the expected ranges."""

    def _run_both(self, state: PaperState) -> tuple[float, float]:
        """Return (repro_score, composite approximation from flags)."""
        from trustworthy_science.agents.reproducibility import reproducibility_agent
        from trustworthy_science.agents.stats_integrity import stats_integrity_agent
        from trustworthy_science.scoring.rules import compute_composite_score

        r1 = reproducibility_agent(state)
        r2 = stats_integrity_agent(state)

        all_soft = r1.get("soft_flags", []) + r2.get("soft_flags", [])
        all_quality = r1.get("quality_signals", []) + r2.get("quality_signals", [])
        all_hard = r1.get("hard_flags", []) + r2.get("hard_flags", [])

        repro_score = r1["sub_scores"]["reproducibility"].score
        composite, tier = compute_composite_score(all_hard, all_soft, all_quality)
        return repro_score, composite

    def test_review_gets_high_repro_and_composite(self):
        state = _state(
            title="Review of autophagy mechanisms",
            abstract="This review surveys the literature on autophagy.",
            paper_type="review_narrative",
        )
        repro, composite = self._run_both(state)
        assert repro >= 0.9, f"repro={repro}"
        # No spurious reproducibility penalties → composite stays near base (70)
        assert composite >= 57, f"composite={composite}"

    def test_empirical_bad_gets_low_repro(self):
        state = _state(
            title="Exercise and cognition study",
            abstract="n=12 participants. p=0.03. No data or code deposited.",
            results="p = 0.03. No effect sizes reported.",
            paper_type="empirical_quantitative",
        )
        repro, composite = self._run_both(state)
        assert repro <= 0.50, f"repro={repro}"

    def test_theoretical_gets_high_repro_and_no_stat_penalties(self):
        state = _state(
            title="Mathematical model of epidemics",
            abstract="We derive a compartmental model and analyse stability.",
            paper_type="theoretical",
        )
        repro, composite = self._run_both(state)
        assert repro >= 0.9, f"repro={repro}"
        assert composite >= 57, f"composite={composite}"

    def test_clinical_trial_with_nct_scores_well(self):
        state = _state(
            title="RCT of Drug X in Condition Y",
            abstract=(
                "Randomized controlled trial. NCT02735707. "
                "Patients randomly assigned. Data at zenodo.org/record/9999."
            ),
            paper_type="clinical_trial",
        )
        repro, composite = self._run_both(state)
        # Both NCT (prereg) and data (zenodo) detected → bonuses, no big penalties
        assert composite >= 70, f"composite={composite}"
