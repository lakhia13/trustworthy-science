/**
 * Zustand store for single paper detail view.
 */

import { create } from 'zustand';
import type { Paper, ApiError } from '../api/client';

interface PaperState {
  // Current paper
  paper: Paper | null;
  loading: boolean;
  error: ApiError | null;
  tookSeconds: number | null;

  // Actions
  setPaper: (paper: Paper) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: ApiError | null) => void;
  setTookSeconds: (seconds: number) => void;
  clearPaper: () => void;
}

const initialState = {
  paper: null,
  loading: false,
  error: null,
  tookSeconds: null,
};

export const usePaperStore = create<PaperState>((set) => ({
  ...initialState,

  setPaper: (paper: Paper) => set({ paper }),

  setLoading: (loading: boolean) => set({ loading }),

  setError: (error: ApiError | null) => set({ error }),

  setTookSeconds: (seconds: number) => set({ tookSeconds: seconds }),

  clearPaper: () => set(initialState),
}));
