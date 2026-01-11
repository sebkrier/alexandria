import { create } from "zustand";
import type { User, Category, Color } from "@/types";

interface AppState {
  // User state
  user: User | null;
  setUser: (user: User | null) => void;

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

  // Reset filters
  resetFilters: () => void;
}

export const useStore = create<AppState>((set) => ({
  // User state
  user: null,
  setUser: (user) => set({ user }),

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

  // Reset filters
  resetFilters: () =>
    set({
      selectedCategoryId: null,
      selectedTagId: null,
      selectedColorId: null,
      searchQuery: "",
    }),
}));
