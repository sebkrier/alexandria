"use client";

import { useState } from "react";
import { X, Check } from "lucide-react";
import { useCategories } from "@/hooks/useCategories";
import { useColors } from "@/hooks/useProviders";
import { clsx } from "clsx";
import type { Article, Category } from "@/types";

interface MarkAsReadModalProps {
  article: Article;
  onConfirm: (colorId?: string, categoryIds?: string[]) => void;
  onCancel: () => void;
}

function CategorySelector({
  categories,
  selectedIds,
  onToggle,
  depth = 0,
}: {
  categories: Category[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  depth?: number;
}) {
  return (
    <div className="space-y-1">
      {categories.map((category) => (
        <div key={category.id}>
          <button
            onClick={() => onToggle(category.id)}
            className={clsx(
              "w-full flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors",
              selectedIds.has(category.id)
                ? "bg-article-blue/20 text-article-blue"
                : "text-dark-muted hover:text-white hover:bg-dark-hover"
            )}
            style={{ paddingLeft: `${12 + depth * 16}px` }}
          >
            <div
              className={clsx(
                "w-4 h-4 rounded border flex items-center justify-center",
                selectedIds.has(category.id)
                  ? "bg-article-blue border-article-blue"
                  : "border-dark-border"
              )}
            >
              {selectedIds.has(category.id) && <Check className="w-3 h-3 text-white" />}
            </div>
            <span>{category.name}</span>
          </button>
          {category.children && category.children.length > 0 && (
            <CategorySelector
              categories={category.children}
              selectedIds={selectedIds}
              onToggle={onToggle}
              depth={depth + 1}
            />
          )}
        </div>
      ))}
    </div>
  );
}

export function MarkAsReadModal({ article, onConfirm, onCancel }: MarkAsReadModalProps) {
  const { data: categories } = useCategories();
  const { data: colors } = useColors();

  // Initialize with current article values
  const [selectedColorId, setSelectedColorId] = useState<string | undefined>(
    article.color_id || undefined
  );
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<Set<string>>(
    new Set(article.categories.map((c) => c.id))
  );

  const toggleCategory = (id: string) => {
    const newSet = new Set(selectedCategoryIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedCategoryIds(newSet);
  };

  const handleConfirm = () => {
    onConfirm(
      selectedColorId,
      selectedCategoryIds.size > 0 ? Array.from(selectedCategoryIds) : undefined
    );
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-dark-surface border border-dark-border rounded-lg w-full max-w-md max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-dark-border">
          <h2 className="text-lg font-semibold text-white">Mark as Read</h2>
          <button onClick={onCancel} className="text-dark-muted hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 overflow-y-auto max-h-[60vh]">
          {/* Color Selection */}
          <div>
            <label className="block text-sm font-medium text-dark-muted mb-2">
              Color (optional)
            </label>
            <div className="flex flex-wrap gap-2">
              {/* No color option */}
              <button
                onClick={() => setSelectedColorId(undefined)}
                className={clsx(
                  "w-8 h-8 rounded-full border-2 flex items-center justify-center",
                  !selectedColorId
                    ? "border-article-blue"
                    : "border-dark-border hover:border-dark-muted"
                )}
              >
                <X className="w-4 h-4 text-dark-muted" />
              </button>
              {colors?.map((color) => (
                <button
                  key={color.id}
                  onClick={() => setSelectedColorId(color.id)}
                  className={clsx(
                    "w-8 h-8 rounded-full border-2",
                    selectedColorId === color.id
                      ? "border-article-blue"
                      : "border-transparent hover:border-dark-muted"
                  )}
                  style={{ backgroundColor: color.hex_value }}
                  title={color.name}
                />
              ))}
            </div>
          </div>

          {/* Category Selection */}
          <div>
            <label className="block text-sm font-medium text-dark-muted mb-2">
              Categories (optional)
            </label>
            {categories && categories.length > 0 ? (
              <div className="border border-dark-border rounded-lg p-2 max-h-48 overflow-y-auto">
                <CategorySelector
                  categories={categories}
                  selectedIds={selectedCategoryIds}
                  onToggle={toggleCategory}
                />
              </div>
            ) : (
              <p className="text-sm text-dark-muted">No categories available</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-dark-border">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-dark-muted hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm bg-article-blue text-white rounded-lg hover:bg-article-blue/90 transition-colors"
          >
            Mark as Read
          </button>
        </div>
      </div>
    </div>
  );
}
