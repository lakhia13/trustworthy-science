x/**
 * API client for Trustworthy Science backend.
 * Uses Axios to communicate with FastAPI REST endpoints.
 */

import axios, { AxiosError, AxiosInstance } from 'axios';

// Get API URL from environment, default to localhost for development
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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
  per_dimension?: Record<string, number>;
  coverage?: string;
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
 * Score papers by DOI list or natural-language query.
 */
export async function scorePapers(
  dois?: string[],
  query?: string,
  topK: number = 10
): Promise<ScoreResponse> {
  try {
    const response = await client.post<ScoreResponse>('/score', {
      dois: dois || [],
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
 * Get detailed credibility report for a single paper by DOI.
 */
export async function getSinglePaper(doi: string): Promise<PaperDetailResponse> {
  try {
    // DOI contains slashes, so use :path syntax in route
    const response = await client.get<PaperDetailResponse>(`/paper/${doi}`);
    return response.data;
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

export default client;
