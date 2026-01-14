import { create } from "zustand";
import type { Category, Color } from "@/types";

interface AppState {
  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;

  // View preferences
  viewMode: "grid" | "list";
  setViewMode: (mode: "grid" | "list") => void;

  // Filters
  selectedCategoryId: string | null;
  setSelectedCategoryId: (id: string | null) => void;
  selectedTagId: string | null;
  setSelectedTagId: (id: string | null) => void;
  selectedColorId: string | null;
  setSelectedColorId: (id: string | null) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  // Cached data
  categories: Category[];
  setCategories: (categories: Category[]) => void;
  colors: Color[];
  setColors: (colors: Color[]) => void;

  // Modal state
  addArticleModalOpen: boolean;
  setAddArticleModalOpen: (open: boolean) => void;

  // Article selection (for bulk operations)
  selectedArticleIds: Set<string>;
  toggleArticleSelection: (id: string) => void;
  selectAllArticles: (ids: string[]) => void;
  deselectAllArticles: () => void;
  isArticleSelected: (id: string) => boolean;

  // Reset filters
  resetFilters: () => void;
}

export const useStore = create<AppState>((set) => ({
  // UI state
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  // View preferences
  viewMode: "grid",
  setViewMode: (mode) => set({ viewMode: mode }),

  // Filters
  selectedCategoryId: null,
  setSelectedCategoryId: (id) => set({ selectedCategoryId: id }),
  selectedTagId: null,
  setSelectedTagId: (id) => set({ selectedTagId: id }),
  selectedColorId: null,
  setSelectedColorId: (id) => set({ selectedColorId: id }),
  searchQuery: "",
  setSearchQuery: (query) => set({ searchQuery: query }),

  // Cached data
  categories: [],
  setCategories: (categories) => set({ categories }),
  colors: [],
  setColors: (colors) => set({ colors }),

  // Modal state
  addArticleModalOpen: false,
  setAddArticleModalOpen: (open) => set({ addArticleModalOpen: open }),

  // Article selection (for bulk operations)
  selectedArticleIds: new Set(),
  toggleArticleSelection: (id) =>
    set((state) => {
      const newSet = new Set(state.selectedArticleIds);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return { selectedArticleIds: newSet };
    }),
  selectAllArticles: (ids) =>
    set({ selectedArticleIds: new Set(ids) }),
  deselectAllArticles: () =>
    set({ selectedArticleIds: new Set() }),
  isArticleSelected: (id) => false, // This is handled by component checking the Set directly

  // Reset filters
  resetFilters: () =>
    set({
      selectedCategoryId: null,
      selectedTagId: null,
      selectedColorId: null,
      searchQuery: "",
    }),
}));
