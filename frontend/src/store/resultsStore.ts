/**
 * Zustand store for search results and API state.
 */

import { create } from 'zustand';
import type { Paper, ApiError } from '../api/client';

interface ResultsState {
  // Results
  papers: Paper[];
  loading: boolean;
  error: ApiError | null;
  lastQuery: string | null;
  tookSeconds: number | null;

  // Actions
  setPapers: (papers: Paper[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: ApiError | null) => void;
  setLastQuery: (query: string) => void;
  setTookSeconds: (seconds: number) => void;
  clearResults: () => void;
}

const initialState = {
  papers: [],
  loading: false,
  error: null,
  lastQuery: null,
  tookSeconds: null,
};

export const useResultsStore = create<ResultsState>((set) => ({
  ...initialState,

  setPapers: (papers: Paper[]) => set({ papers }),

  setLoading: (loading: boolean) => set({ loading }),

  setError: (error: ApiError | null) => set({ error }),

  setLastQuery: (query: string) => set({ lastQuery: query }),

  setTookSeconds: (seconds: number) => set({ tookSeconds: seconds }),

  clearResults: () => set(initialState),
}));
