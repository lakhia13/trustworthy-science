from __future__ import annotations
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from trustworthy_science.server.schemas import PaperResult, SearchRequest, JobResponse, JobStatus
from trustworthy_science.server.dependencies import get_truth_filter, resolve_truth_filter
from trustworthy_science.api import TruthFilter
from typing import Dict, List

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store
job_store: Dict[str, List[PaperResult]] = {}
job_status: Dict[str, JobStatus] = {}

def run_search_and_score(request: SearchRequest, tf: TruthFilter, job_id: str):
    """Synchronous function to run search and scoring and store results."""
    logger.info(f"Starting search and scoring for job_id: {job_id}")
    job_status[job_id] = JobStatus(status="running", total=0, completed=0)
    results: list[PaperResult] = []
    seen: set[str] = set()

    # Estimate total number of papers to score
    total_papers = len(request.pmids) + len(request.dois)
    if request.query:
        total_papers += request.top_k
    job_status[job_id].total = total_papers

    completed_papers = 0

    # Score PMIDs
    for pmid in request.pmids:
        try:
            raw = tf.score_single_by_pmid(pmid)
            if raw:
                key = raw.get("doi") or raw.get("pmid") or pmid
                if key not in seen:
                    seen.add(key)
                    results.append(PaperResult.from_dict(raw))
        except Exception as exc:
            logger.warning("PMID %s scoring failed: %s", pmid, exc)
        completed_papers += 1
        job_status[job_id].completed = completed_papers


    # Score DOIs / query
    if request.dois or request.query:
        try:
            # This part is tricky to report progress on as it's a single call
            raw_list = tf.score_papers(
                dois=request.dois or None,
                query=request.query,
                top_k=request.top_k,
            )
            for raw in raw_list:
                key = raw.get("doi") or raw.get("pmid") or ""
                if key not in seen:
                    seen.add(key)
                    results.append(PaperResult.from_dict(raw))
        except Exception as exc:
            logger.error("score_papers failed: %s", exc)
            job_status[job_id] = JobStatus(status="failed", message=str(exc))
            return
    
    job_status[job_id].completed = total_papers # Mark as complete
    job_store[job_id] = results
    job_status[job_id].status = "completed"
    logger.info(f"Scoring completed for job_id: {job_id}")


@router.post("", response_model=JobResponse, summary="Start a search and score job for papers by DOI, PMID, or query")
def search_and_score_papers(
    request: SearchRequest,
    background_tasks: BackgroundTasks,
    tf: TruthFilter = Depends(get_truth_filter)
) -> JobResponse:
    """
    Start a background job to search for and score one or more papers.

    Supply any combination of:
    - **dois**: list of DOI strings
    - **pmids**: list of PubMed IDs (enables BioC JSON full-text fetch)
    - **query**: natural-language research question (retrieves top_k papers)

    Returns a job_id to track the scoring progress.
    """
    job_id = str(uuid.uuid4())
    active_tf = resolve_truth_filter(request.weights, tf)
    background_tasks.add_task(run_search_and_score, request, active_tf, job_id)
    return JobResponse(job_id=job_id)


@router.get("/status/{job_id}", response_model=JobStatus, summary="Get the status of a search and score job")
def get_job_status(job_id: str) -> JobStatus:
    """
    Check the status of a scoring job.
    
    Returns the current status, and results if the job is completed.
    """
    status = job_status.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    if status.status == "completed":
        status.results = job_store.get(job_id)

    return status
