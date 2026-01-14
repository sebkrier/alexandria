"use client";

import { useState } from "react";
import { Search, LayoutGrid, List, Menu, MessageSquare } from "lucide-react";
import { useStore } from "@/lib/store";
import { Button } from "@/components/ui/Button";
import { AskModal } from "@/components/AskModal";

export function Header() {
  const [askModalOpen, setAskModalOpen] = useState(false);
  const {
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    toggleSidebar,
  } = useStore();

  return (
    <header className="h-14 bg-dark-surface border-b border-dark-border px-4 flex items-center gap-4">
      {/* Sidebar toggle */}
      <button
        onClick={toggleSidebar}
        className="p-2 text-dark-muted hover:text-dark-text hover:bg-dark-hover rounded-lg transition-colors"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Search */}
      <div className="flex-1 max-w-xl">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-muted" />
          <input
            type="text"
            placeholder="Search articles..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text placeholder-dark-muted focus:outline-none focus:ring-2 focus:ring-article-blue focus:border-transparent"
          />
        </div>
      </div>

      {/* Ask button */}
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setAskModalOpen(true)}
        className="gap-2"
      >
        <MessageSquare className="w-4 h-4" />
        Ask
      </Button>

      {/* View toggle */}
      <div className="flex items-center gap-1 p-1 bg-dark-bg rounded-lg border border-dark-border">
        <button
          onClick={() => setViewMode("grid")}
          className={`p-1.5 rounded ${
            viewMode === "grid"
              ? "bg-dark-hover text-white"
              : "text-dark-muted hover:text-dark-text"
          }`}
        >
          <LayoutGrid className="w-4 h-4" />
        </button>
        <button
          onClick={() => setViewMode("list")}
          className={`p-1.5 rounded ${
            viewMode === "list"
              ? "bg-dark-hover text-white"
              : "text-dark-muted hover:text-dark-text"
          }`}
        >
          <List className="w-4 h-4" />
        </button>
      </div>

      {/* Ask Modal */}
      <AskModal open={askModalOpen} onClose={() => setAskModalOpen(false)} />
    </header>
  );
}
