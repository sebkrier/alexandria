"use client";

import Link from "next/link";
import { FileText, Globe, GraduationCap, Loader2, AlertCircle, Clock, Video, Check } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { MediaTypeBadge } from "@/components/ui/MediaTypeBadge";
import type { Article } from "@/types";
import { clsx } from "clsx";
import { useColors } from "@/hooks/useProviders";
import { useStore } from "@/lib/store";

interface ArticleCardProps {
  article: Article;
  viewMode: "grid" | "list";
}

const sourceIcons = {
  url: Globe,
  pdf: FileText,
  arxiv: GraduationCap,
  video: Video,
};

const statusIcons = {
  pending: Clock,
  processing: Loader2,
  completed: null,
  failed: AlertCircle,
};

export function ArticleCard({ article, viewMode }: ArticleCardProps) {
  const { data: colors } = useColors();
  const { selectedArticleIds, toggleArticleSelection } = useStore();
  const SourceIcon = sourceIcons[article.source_type] || Globe;
  const StatusIcon = statusIcons[article.processing_status];
  const articleColor = colors?.find((c) => c.id === article.color_id);

  const isProcessing = article.processing_status === "processing";
  const isFailed = article.processing_status === "failed";
  const isSelected = selectedArticleIds.has(article.id);

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    toggleArticleSelection(article.id);
  };

  // Get summary preview (first paragraph)
  const summaryPreview = article.summary
    ?.split("\n")
    .find((line) => line.trim() && !line.startsWith("#"))
    ?.slice(0, 200);

  // Get link for paperclip - URL if available, otherwise Google search
  const externalLink = article.original_url
    ? article.original_url
    : `https://www.google.com/search?q=${encodeURIComponent(article.title || "")}`;

  if (viewMode === "list") {
    return (
      <Link
        href={`/article/${article.id}`}
        className={clsx(
          "flex items-start gap-4 p-4 bg-dark-surface border rounded-lg transition-colors",
          isSelected
            ? "border-article-blue bg-article-blue/5"
            : "border-dark-border hover:border-dark-hover hover:bg-dark-hover/50"
        )}
      >
        {/* Color indicator */}
        {articleColor && (
          <div
            className="w-1 self-stretch rounded-full flex-shrink-0"
            style={{ backgroundColor: articleColor.hex_value }}
          />
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-3">
            <SourceIcon className="w-4 h-4 text-dark-muted mt-1 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                {!article.is_read && (
                  <span className="w-2 h-2 rounded-full bg-article-blue flex-shrink-0" title="Unread" />
                )}
                <h3 className="font-medium text-white truncate">{article.title}</h3>
              </div>
              {summaryPreview && (
                <p className="text-sm text-dark-muted mt-1 line-clamp-2">{summaryPreview}</p>
              )}
              <div className="flex items-center gap-2 mt-2">
                {(article.categories || []).slice(0, 1).map((cat) => (
                  <Badge key={cat.id} size="sm" color="#6B7280" variant="outline">
                    {cat.name}
                  </Badge>
                ))}
                {(article.tags || []).slice(0, 3).map((tag) => (
                  <Badge key={tag.id} size="sm" color={tag.color || "#8B5CF6"}>
                    {tag.name}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Meta */}
        <div className="flex items-center gap-3 flex-shrink-0 text-sm text-dark-muted">
          {article.reading_time_minutes && (
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              {article.reading_time_minutes} min
            </span>
          )}
          {StatusIcon && (
            <StatusIcon
              className={clsx("w-4 h-4", isProcessing && "animate-spin", isFailed && "text-article-red")}
            />
          )}
          <MediaTypeBadge type={article.media_type} />
          <a
            href={externalLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="hover:text-article-blue transition-colors"
            title={article.original_url ? "Open source" : "Search on Google"}
          >
            📎
          </a>
          {/* Checkbox */}
          <button
            onClick={handleCheckboxClick}
            className={clsx(
              "w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors",
              isSelected
                ? "bg-article-blue border-article-blue"
                : "border-dark-border hover:border-dark-muted"
            )}
          >
            {isSelected && <Check className="w-3 h-3 text-white" />}
          </button>
        </div>
      </Link>
    );
  }

  // Grid view
  return (
    <Link
      href={`/article/${article.id}`}
      className={clsx(
        "flex flex-col p-4 bg-dark-surface border rounded-lg transition-colors h-full",
        isSelected
          ? "border-article-blue bg-article-blue/5"
          : "border-dark-border hover:border-dark-hover hover:bg-dark-hover/50"
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <SourceIcon className="w-4 h-4 text-dark-muted" />
          {articleColor && (
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: articleColor.hex_value }}
            />
          )}
        </div>
        <div className="flex items-center gap-2">
          {StatusIcon && (
            <StatusIcon
              className={clsx(
                "w-4 h-4",
                isProcessing && "animate-spin text-article-blue",
                isFailed && "text-article-red"
              )}
            />
          )}
          {/* Checkbox */}
          <button
            onClick={handleCheckboxClick}
            className={clsx(
              "w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors",
              isSelected
                ? "bg-article-blue border-article-blue"
                : "border-dark-border hover:border-dark-muted"
            )}
          >
            {isSelected && <Check className="w-3 h-3 text-white" />}
          </button>
        </div>
      </div>

      {/* Title */}
      <div className="flex items-start gap-2 mb-2">
        {!article.is_read && (
          <span className="w-2 h-2 rounded-full bg-article-blue flex-shrink-0 mt-1.5" title="Unread" />
        )}
        <h3 className="font-medium text-white line-clamp-2">{article.title}</h3>
      </div>

      {/* Summary preview */}
      {summaryPreview && (
        <p className="text-sm text-dark-muted line-clamp-3 mb-3 flex-1">{summaryPreview}</p>
      )}

      {/* Categories & Tags */}
      <div className="flex flex-wrap gap-1.5 mt-auto">
        {(article.categories || []).slice(0, 1).map((cat) => (
          <Badge key={cat.id} size="sm" color="#6B7280" variant="outline">
            {cat.name}
          </Badge>
        ))}
        {(article.tags || []).slice(0, 2).map((tag) => (
          <Badge key={tag.id} size="sm" color={tag.color || "#8B5CF6"}>
            {tag.name}
          </Badge>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-dark-border flex justify-between items-center">
        {article.reading_time_minutes ? (
          <span className="flex items-center gap-1 text-xs text-dark-muted">
            <Clock className="w-3 h-3" />
            {article.reading_time_minutes} min read
          </span>
        ) : (
          <span />
        )}
        <div className="flex items-center gap-2">
          <MediaTypeBadge type={article.media_type} />
          <a
            href={externalLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-dark-muted hover:text-article-blue transition-colors"
            title={article.original_url ? "Open source" : "Search on Google"}
          >
            📎
          </a>
        </div>
      </div>
    </Link>
  );
}
