/**
 * API client for Trustworthy Science backend.
 * Uses Axios to communicate with FastAPI REST endpoints.
 */

import axios, { AxiosError, type AxiosInstance } from 'axios';

// Get API URL from environment.
// Empty string = relative URLs (production via Nginx proxy).
// Falls back to localhost only when VITE_API_URL is not defined at all.
const API_BASE = import.meta.env.VITE_API_URL !== undefined
  ? import.meta.env.VITE_API_URL
  : 'http://localhost:8000';

// Create Axios instance with base config
const client: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request logging in development
if (import.meta.env.MODE === 'development') {
  client.interceptors.request.use((config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.data);
    return config;
  });

  client.interceptors.response.use(
    (response) => {
      console.log(`[API] Response ${response.status}`, response.data);
      return response;
    },
    (error) => {
      console.error(`[API] Error: ${error.message}`, error.response?.data);
      return Promise.reject(error);
    }
  );
}

// ============================================================================
// Type Definitions
// ============================================================================

export interface EvidenceQuote {
  text: string;
  section?: string;
}

export interface Flag {
  tier: 'hard' | 'soft' | 'quality';
  code: string;
  message?: string;
  source_agent?: string;
  evidence?: EvidenceQuote[];
}

export interface DimensionScore {
  dimension: string;
  score: number;
  reason?: string;
}

export interface StructuredReport {
  overall_verdict: string;
  score_breakdown: DimensionScore[];
  key_concerns: string[];
  positive_signals: string[];
  recommendation: string;
  raw_score?: number;
  tier?: string;
}

export interface ScoringWeights {
  retraction_cap?: number;
  no_data_deposit_penalty?: number;
  open_data_bonus?: number;
  replicated_bonus?: number;
  methods_nudge_pct?: number;
}

export interface Paper {
  doi?: string;
  title: string;
  authors?: string[];
  year?: number;
  venue?: string;
  abstract?: string;
  composite_score?: number;
  score?: number;
  tier: 'Trusted' | 'Caution' | 'Untrusted';
  summary: string;
  hard_flags: string[] | Flag[];
  soft_flags: string[] | Flag[];
  quality_signals: string[] | Flag[];
  per_dimension?: DimensionScore[] | Record<string, number>;
  coverage?: string;
  structured_report?: StructuredReport;
  fetch_source?: string;
}

export interface DeepResearchJobStatus {
  status: 'pending' | 'running' | 'completed' | 'failed';
  message?: string;
  collection_name?: string;
  generated_queries: string[];
  mesh_terms: string[];
  query_metadata: Record<string, any>[];
  accepted_papers: Paper[];
  scored_papers: Paper[];
  literature_review?: string;
  cited_papers: Paper[];
  session_id?: string;
  elapsed_seconds?: number;
}

export interface ScoreResponse {
  papers: Paper[];
  took_seconds: number;
}

export interface FilterResponse {
  papers: Paper[];
  took_seconds: number;
}

export interface PaperDetailResponse {
  paper: Paper;
  took_seconds: number;
}

export interface ApiError {
  message: string;
  code?: string;
  status?: number;
  details?: Record<string, any>;
}

// ============================================================================
// API Methods
// ============================================================================

/**
 * Score papers by DOI list, PMID list, or natural-language query.
 */
export async function scorePapers(
  dois?: string[],
  query?: string,
  topK: number = 10,
  pmids?: string[],
): Promise<ScoreResponse> {
  try {
    const response = await client.post<ScoreResponse>('/score', {
      dois: dois || [],
      pmids: pmids || [],
      query,
      top_k: topK,
    });
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/**
 * Filter papers for RAG input by query.
 */
export async function filterForRAG(
  query: string,
  topK: number = 20,
  minTier: 'Trusted' | 'Caution' | 'Untrusted' = 'Caution'
): Promise<FilterResponse> {
  try {
    const response = await client.post<FilterResponse>('/filter', {
      query,
      top_k: topK,
      min_tier: minTier,
    });
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/**
 * Get detailed credibility report for a single paper by DOI or PMID.
 * Uses POST /explain (the only single-paper detail endpoint on the backend).
 */
export async function getSinglePaper(doi: string, pmid?: string): Promise<PaperDetailResponse> {
  try {
    const body = pmid ? { pmid } : { doi };
    const response = await client.post<Paper>('/explain', body);
    // /explain returns PaperResult directly (not wrapped); normalise here
    return { paper: response.data, took_seconds: 0 };
  } catch (error) {
    throw formatError(error);
  }
}

/**
 * Check API health status.
 */
export async function checkHealth(): Promise<{ status: string; service: string }> {
  try {
    const response = await client.get('/', {
      baseURL: API_BASE, // Explicit base URL
    });
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format Axios errors into structured ApiError objects.
 */
function formatError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ error?: string; code?: string }>;
    const status = axiosError.response?.status;
    const data = axiosError.response?.data;

    return {
      message: data?.error || axiosError.message || 'Unknown error',
      code: data?.code || 'unknown',
      status: status,
      details: axiosError.response?.data,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
      code: 'error',
    };
  }

  return {
    message: 'Unknown error occurred',
    code: 'unknown',
  };
}

/**
 * Get user-friendly error message.
 */
export function getUserErrorMessage(error: ApiError): string {
  if (error.status === 404) {
    return 'Paper not found. Please check the DOI and try again.';
  }
  if (error.status === 400) {
    return 'Invalid request. Please check your input.';
  }
  if (error.status === 504) {
    return 'Request timed out. The server is taking too long to respond.';
  }
  if (error.status === 500 || error.status === 503) {
    return 'Server error. Please try again later.';
  }
  return error.message || 'An unexpected error occurred.';
}

// ============================================================================
// Graph RAG — Literature Review Session Types
// ============================================================================

export interface GraphNode {
  id: string;
  title: string;
  score: number;
  tier: 'Trusted' | 'Caution' | 'Untrusted';
  year?: number;
  venue?: string;
  hard_flags: string[];
  soft_flags: string[];
  quality_signals: string[];
  val?: number; // visual size hint
}

export interface GraphEdge {
  source: string;
  target: string;
  type: 'CITES' | 'SHARES_TOPIC';
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_papers: number;
    trusted: number;
    caution: number;
    total_edges: number;
  };
}

export interface PaperSummary {
  doi: string;
  title: string;
  score: number;
  tier: string;
  reason?: string;
}

export interface AddPapersResponse {
  added: PaperSummary[];
  excluded: PaperSummary[];
  graph_size: number;
  graph_stats: Record<string, number>;
  took_seconds: number;
}

export interface QueryResponse {
  answer: string;
  papers_used: PaperSummary[];
  graph_size: number;
  took_seconds: number;
}

export interface SessionStats {
  session_id: string;
  graph_stats: Record<string, number>;
  query_count: number;
  total_scored: number;
  total_added: number;
  total_excluded: number;
  created_at: string;
}

// ============================================================================
// Graph RAG API Methods
// ============================================================================

/** Start a new literature review session. Returns the session_id. */
export async function startReviewSession(): Promise<{ session_id: string }> {
  try {
    const response = await client.post<{ session_id: string }>('/review/start');
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/** Score papers and add Trusted/Caution ones to the session graph. */
export async function addPapersToSession(
  sessionId: string,
  dois?: string[],
  query?: string,
  topK: number = 10
): Promise<AddPapersResponse> {
  try {
    const response = await client.post<AddPapersResponse>(`/review/${sessionId}/add`, {
      dois: dois || [],
      query,
      top_k: topK,
    });
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/** Get the full graph (nodes + edges) for visualization. */
export async function getSessionGraph(sessionId: string): Promise<GraphResponse> {
  try {
    const response = await client.get<GraphResponse>(`/review/${sessionId}/graph`);
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/** Query the session's knowledge graph, get LLM answer grounded in trusted papers. */
export async function querySessionGraph(
  sessionId: string,
  question: string,
  topK: number = 5
): Promise<QueryResponse> {
  try {
    const response = await client.post<QueryResponse>(`/review/${sessionId}/query`, {
      question,
      top_k: topK,
    });
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/** Get session statistics. */
export async function getSessionStats(sessionId: string): Promise<SessionStats> {
  try {
    const response = await client.get<SessionStats>(`/review/${sessionId}/stats`);
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

// ============================================================================
// Deep Research API Methods
// ============================================================================

/**
 * Start an async deep research job. Returns job_id immediately.
 */
export async function startDeepResearch(
  prompt: string,
  topK: number = 10,
  minTier: string = 'Caution',
  collectionName?: string,
  weights?: ScoringWeights
): Promise<{ job_id: string }> {
  try {
    const response = await client.post<{ job_id: string }>('/api/deep-research', {
      prompt,
      top_k: topK,
      min_tier: minTier,
      collection_name: collectionName,
      weights: weights || undefined,
    });
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/**
 * Poll the status of a deep research job.
 */
export async function getDeepResearchStatus(jobId: string): Promise<DeepResearchJobStatus> {
  try {
    const response = await client.get<DeepResearchJobStatus>(`/api/deep-research/status/${jobId}`);
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

/**
 * Send a follow-up chat message about the collected research.
 */
export async function chatWithResearch(
  sessionId: string,
  message: string,
  collectionName: string
): Promise<{ answer: string; cited_papers: Paper[] }> {
  try {
    const response = await client.post<{ answer: string; cited_papers: Paper[] }>(
      '/api/deep-research/chat',
      { session_id: sessionId, message, collection_name: collectionName }
    );
    return response.data;
  } catch (error) {
    throw formatError(error);
  }
}

export default client;
