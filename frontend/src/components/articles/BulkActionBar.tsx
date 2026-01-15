"use client";

import { useState, useEffect } from "react";
import { Trash2, Palette, RefreshCw, X, CheckSquare, Square } from "lucide-react";
import { clsx } from "clsx";
import { useStore } from "@/lib/store";
import { useColors } from "@/hooks/useProviders";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

interface BulkActionBarProps {
  articleIds: string[];  // All visible article IDs for "select all"
}

export function BulkActionBar({ articleIds }: BulkActionBarProps) {
  const queryClient = useQueryClient();
  const { data: colors } = useColors();
  const {
    selectedArticleIds,
    deselectAllArticles,
    selectAllArticles,
  } = useStore();

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpdatingColor, setIsUpdatingColor] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);

  const selectedCount = selectedArticleIds.size;
  const allSelected = articleIds.length > 0 && articleIds.every(id => selectedArticleIds.has(id));

  // Handle Escape key to clear selection
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedCount > 0) {
        deselectAllArticles();
        setShowDeleteConfirm(false);
        setShowColorPicker(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedCount, deselectAllArticles]);

  // Don't render if nothing selected
  if (selectedCount === 0) return null;

  const handleSelectAllToggle = () => {
    if (allSelected) {
      deselectAllArticles();
    } else {
      selectAllArticles(articleIds);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      const result = await api.bulkDeleteArticles(Array.from(selectedArticleIds));

      if (result.deleted > 0) {
        toast.success(`Deleted ${result.deleted} article${result.deleted > 1 ? "s" : ""}`);
      }
      if (result.failed.length > 0) {
        toast.error(`Failed to delete ${result.failed.length} article${result.failed.length > 1 ? "s" : ""}`);
      }

      deselectAllArticles();
      setShowDeleteConfirm(false);
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    } catch {
      toast.error("Failed to delete articles");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleColorChange = async (colorId: string | null) => {
    setIsUpdatingColor(true);
    try {
      const result = await api.bulkUpdateColor(Array.from(selectedArticleIds), colorId);

      if (result.updated > 0) {
        toast.success(`Updated color for ${result.updated} article${result.updated > 1 ? "s" : ""}`);
      }
      if (result.failed.length > 0) {
        toast.error(`Failed to update ${result.failed.length} article${result.failed.length > 1 ? "s" : ""}`);
      }

      deselectAllArticles();
      setShowColorPicker(false);
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    } catch {
      toast.error("Failed to update color");
    } finally {
      setIsUpdatingColor(false);
    }
  };

  const handleReanalyze = async () => {
    setIsReanalyzing(true);
    toast.loading(`Re-analyzing ${selectedCount} article${selectedCount > 1 ? "s" : ""}...`, { id: "reanalyze" });

    try {
      const result = await api.bulkReanalyzeArticles(Array.from(selectedArticleIds));

      toast.dismiss("reanalyze");

      if (result.queued > 0) {
        toast.success(`Re-analyzed ${result.queued} article${result.queued > 1 ? "s" : ""}`);
      }
      if (result.skipped > 0) {
        toast(`Skipped ${result.skipped} already processing`);
      }
      if (result.failed.length > 0) {
        toast.error(`Failed: ${result.failed.length}`);
      }

      deselectAllArticles();
      queryClient.invalidateQueries({ queryKey: ["articles"] });
    } catch {
      toast.dismiss("reanalyze");
      toast.error("Failed to re-analyze articles");
    } finally {
      setIsReanalyzing(false);
    }
  };

  return (
    <>
      {/* Floating action bar */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
        <div className="flex items-center gap-3 px-4 py-3 bg-dark-surface border border-dark-border rounded-xl shadow-2xl">
          {/* Selection info */}
          <div className="flex items-center gap-2 pr-3 border-r border-dark-border">
            <button
              onClick={handleSelectAllToggle}
              className="p-1 hover:bg-dark-hover rounded transition-colors"
              title={allSelected ? "Deselect all" : "Select all"}
            >
              {allSelected ? (
                <CheckSquare className="w-5 h-5 text-article-blue" />
              ) : (
                <Square className="w-5 h-5 text-dark-muted" />
              )}
            </button>
            <span className="text-sm text-white font-medium">
              {selectedCount} selected
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            {/* Color */}
            <div className="relative">
              <button
                onClick={() => setShowColorPicker(!showColorPicker)}
                disabled={isUpdatingColor}
                className={clsx(
                  "flex items-center gap-2 px-3 py-2 rounded-lg transition-colors",
                  "text-dark-muted hover:text-white hover:bg-dark-hover",
                  isUpdatingColor && "opacity-50 cursor-not-allowed"
                )}
              >
                <Palette className="w-4 h-4" />
                <span className="text-sm">Color</span>
              </button>

              {/* Color picker popover */}
              {showColorPicker && (
                <div className="absolute bottom-full left-0 mb-2 p-2 bg-dark-surface border border-dark-border rounded-lg shadow-xl">
                  <div className="flex flex-wrap gap-2 w-48">
                    {/* Clear color option */}
                    <button
                      onClick={() => handleColorChange(null)}
                      className="w-8 h-8 rounded-full border-2 border-dashed border-dark-border hover:border-dark-muted transition-colors flex items-center justify-center"
                      title="Clear color"
                    >
                      <X className="w-4 h-4 text-dark-muted" />
                    </button>
                    {colors?.map((color) => (
                      <button
                        key={color.id}
                        onClick={() => handleColorChange(color.id)}
                        className="w-8 h-8 rounded-full border-2 border-transparent hover:border-white transition-colors"
                        style={{ backgroundColor: color.hex_value }}
                        title={color.name}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Re-analyze */}
            <button
              onClick={handleReanalyze}
              disabled={isReanalyzing}
              className={clsx(
                "flex items-center gap-2 px-3 py-2 rounded-lg transition-colors",
                "text-dark-muted hover:text-white hover:bg-dark-hover",
                isReanalyzing && "opacity-50 cursor-not-allowed"
              )}
            >
              <RefreshCw className={clsx("w-4 h-4", isReanalyzing && "animate-spin")} />
              <span className="text-sm">Re-analyze</span>
            </button>

            {/* Delete */}
            <button
              onClick={() => setShowDeleteConfirm(true)}
              disabled={isDeleting}
              className={clsx(
                "flex items-center gap-2 px-3 py-2 rounded-lg transition-colors",
                "text-article-red hover:bg-article-red/10",
                isDeleting && "opacity-50 cursor-not-allowed"
              )}
            >
              <Trash2 className="w-4 h-4" />
              <span className="text-sm">Delete</span>
            </button>
          </div>

          {/* Close selection */}
          <button
            onClick={deselectAllArticles}
            className="p-2 text-dark-muted hover:text-white hover:bg-dark-hover rounded-lg transition-colors ml-2"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-dark-surface border border-dark-border rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-semibold text-white mb-2">
              Delete {selectedCount} article{selectedCount > 1 ? "s" : ""}?
            </h3>
            <p className="text-dark-muted mb-6">
              This action cannot be undone. All selected articles and their notes will be permanently deleted.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-dark-muted hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className={clsx(
                  "px-4 py-2 bg-article-red text-white rounded-lg hover:bg-article-red/90 transition-colors",
                  isDeleting && "opacity-50 cursor-not-allowed"
                )}
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
