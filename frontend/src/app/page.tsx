"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ArticleCard } from "@/components/articles/ArticleCard";
import { AddArticleModal } from "@/components/articles/AddArticleModal";
import { BulkActionBar } from "@/components/articles/BulkActionBar";
import { Button } from "@/components/ui/Button";
import { useStore } from "@/lib/store";
import { useArticles, useReorganizeArticles } from "@/hooks/useArticles";
import { Loader2, BookOpen, FolderSync } from "lucide-react";

export default function HomePage() {
  const { viewMode, selectedCategoryId, selectedColorId, searchQuery } = useStore();

  const articles = useArticles();
  const reorganize = useReorganizeArticles();

  return (
    <div className="min-h-screen bg-dark-bg flex">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <Header />

        <main className="flex-1 overflow-y-auto p-6">
          {/* Actions bar */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-dark-muted">
              {(selectedCategoryId || selectedColorId || searchQuery) && (
                <>
                  <span>Showing filtered results</span>
                  <button
                    onClick={() => useStore.getState().resetFilters()}
                    className="text-article-blue hover:underline"
                  >
                    Clear filters
                  </button>
                </>
              )}
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => reorganize.mutate(true)}
              loading={reorganize.isPending}
              title="Reorganize uncategorized articles using AI"
            >
              <FolderSync className="w-4 h-4 mr-2" />
              Auto-categorize
            </Button>
          </div>

          {/* Loading */}
          {articles.isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-article-blue animate-spin" />
            </div>
          )}

          {/* Empty state */}
          {articles.data && articles.data.items.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 bg-dark-surface rounded-2xl flex items-center justify-center mb-4">
                <BookOpen className="w-8 h-8 text-dark-muted" />
              </div>
              <h2 className="text-lg font-medium text-white mb-2">No articles yet</h2>
              <p className="text-dark-muted max-w-sm">
                {searchQuery || selectedCategoryId || selectedColorId
                  ? "No articles match your current filters"
                  : "Add your first article to get started with your research library"}
              </p>
            </div>
          )}

          {/* Article grid/list */}
          {articles.data && articles.data.items.length > 0 && (
            <div
              className={
                viewMode === "grid"
                  ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
                  : "space-y-3"
              }
            >
              {articles.data.items.map((article) => (
                <ArticleCard key={article.id} article={article} viewMode={viewMode} />
              ))}
            </div>
          )}

          {/* Pagination info */}
          {articles.data && articles.data.total > 0 && (
            <div className="mt-6 text-center text-sm text-dark-muted">
              Showing {articles.data.items.length} of {articles.data.total} articles
            </div>
          )}
        </main>
      </div>

      <AddArticleModal />

      {/* Bulk action bar - shows when articles are selected */}
      <BulkActionBar
        articleIds={articles.data?.items.map((a) => a.id) || []}
      />
    </div>
  );
}
