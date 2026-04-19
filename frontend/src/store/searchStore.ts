/**
 * Zustand store for search filters and parameters.
 */

import { create } from 'zustand';

export type SearchType = 'doi' | 'query';

interface SearchState {
  // Search input
  query: string;
  dois: string[];

  // Filters
  searchType: SearchType;
  topK: number;
  minTier: 'Trusted' | 'Caution' | 'Untrusted';

  // Actions
  setQuery: (query: string) => void;
  setDOIs: (dois: string[]) => void;
  setSearchType: (type: SearchType) => void;
  setTopK: (topK: number) => void;
  setMinTier: (tier: 'Trusted' | 'Caution' | 'Untrusted') => void;
  reset: () => void;
}

const initialState = {
  query: '',
  dois: [],
  searchType: 'doi' as const,
  topK: 20,
  minTier: 'Caution' as const,
};

export const useSearchStore = create<SearchState>((set) => ({
  ...initialState,

  setQuery: (query: string) => set({ query }),

  setDOIs: (dois: string[]) => set({ dois }),

  setSearchType: (type: SearchType) => set({ searchType: type }),

  setTopK: (topK: number) => set({ topK: Math.max(1, Math.min(100, topK)) }),

  setMinTier: (tier: 'Trusted' | 'Caution' | 'Untrusted') => set({ minTier: tier }),

  reset: () => set(initialState),
}));
