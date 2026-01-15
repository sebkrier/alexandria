"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Check,
  Clock,
  ArrowLeft,
  CheckCircle,
  X,
} from "lucide-react";
import { useArticle } from "@/hooks/useArticles";
import { useUnreadNavigation, useMarkAsRead, useUnreadList } from "@/hooks/useReader";
import { MarkAsReadModal } from "@/components/reader/MarkAsReadModal";
import { clsx } from "clsx";
import ReactMarkdown from "react-markdown";

const KEYBOARD_HINTS_DISMISSED_KEY = "alexandria-keyboard-hints-dismissed";

export default function ReaderPage() {
  const params = useParams();
  const router = useRouter();
  const articleId = params.id as string;

  const { data: article, isLoading } = useArticle(articleId);
  const { data: navigation } = useUnreadNavigation(articleId);
  const { data: unreadList } = useUnreadList();
  const markAsRead = useMarkAsRead();

  const [showMarkAsReadModal, setShowMarkAsReadModal] = useState(false);
  const [showKeyboardHints, setShowKeyboardHints] = useState(true);
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Check if keyboard hints were dismissed
  useEffect(() => {
    const dismissed = localStorage.getItem(KEYBOARD_HINTS_DISMISSED_KEY);
    if (dismissed === "true") {
      setShowKeyboardHints(false);
    }
  }, []);

  const dismissKeyboardHints = () => {
    setShowKeyboardHints(false);
    localStorage.setItem(KEYBOARD_HINTS_DISMISSED_KEY, "true");
  };

  // Extract domain from URL
  const sourceDomain = useMemo(() => {
    if (!article?.original_url) return null;
    try {
      const url = new URL(article.original_url);
      return url.hostname.replace("www.", "");
    } catch {
      return null;
    }
  }, [article?.original_url]);

  // Check if summary is long (> 300 words)
  const summaryWordCount = article?.summary?.split(/\s+/).length || 0;
  const isLongSummary = summaryWordCount > 300;

  // Progress percentage
  const progressPercent = navigation
    ? (navigation.current_position / navigation.total_unread) * 100
    : 0;

  // Open article in new tab
  const openArticle = useCallback(() => {
    if (article?.original_url) {
      window.open(article.original_url, "_blank");
    } else {
      const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(article?.title || "")}`;
      window.open(searchUrl, "_blank");
    }
  }, [article]);

  // Navigation handlers with transition
  const goToPrev = useCallback(() => {
    if (navigation?.prev_id) {
      setIsTransitioning(true);
      setTimeout(() => {
        router.push(`/reader/${navigation.prev_id}`);
      }, 150);
    }
  }, [navigation, router]);

  const goToNext = useCallback(() => {
    if (navigation?.next_id) {
      setIsTransitioning(true);
      setTimeout(() => {
        router.push(`/reader/${navigation.next_id}`);
      }, 150);
    }
  }, [navigation, router]);

  const handleMarkAsRead = useCallback(
    (colorId?: string, categoryIds?: string[]) => {
      markAsRead.mutate(
        { articleId, colorId, categoryIds },
        {
          onSuccess: () => {
            setShowMarkAsReadModal(false);
            if (navigation?.next_id) {
              setIsTransitioning(true);
              setTimeout(() => {
                router.push(`/reader/${navigation.next_id}`);
              }, 150);
            } else {
              router.push("/");
            }
          },
        }
      );
    },
    [articleId, markAsRead, navigation, router]
  );

  // Reset transition state on article change
  useEffect(() => {
    setIsTransitioning(false);
    setSummaryExpanded(false);
  }, [articleId]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case "ArrowLeft":
        case "j":
          goToPrev();
          break;
        case "ArrowRight":
        case "k":
          goToNext();
          break;
        case "o":
        case "Enter":
          openArticle();
          break;
        case "m":
          setShowMarkAsReadModal(true);
          break;
        case "Escape":
          if (showMarkAsReadModal) {
            setShowMarkAsReadModal(false);
          } else {
            router.push("/");
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [goToPrev, goToNext, openArticle, showMarkAsReadModal, router]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-dark-bg">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-article-blue" />
      </div>
    );
  }

  // Empty state - all caught up
  if (!article || (unreadList && unreadList.total === 0)) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-dark-bg animate-in fade-in duration-300">
        <CheckCircle className="w-20 h-20 text-green-500 mb-6" />
        <h1 className="text-2xl font-bold text-white mb-2">All caught up!</h1>
        <p className="text-dark-muted mb-8">Your reading queue is empty</p>
        <button
          onClick={() => router.push("/")}
          className="px-6 py-3 bg-article-blue text-white rounded-lg hover:bg-article-blue/90 transition-all hover:scale-[1.02]"
        >
          Back to Library
        </button>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        "min-h-screen bg-dark-bg transition-opacity duration-150",
        isTransitioning ? "opacity-0" : "opacity-100 animate-in fade-in duration-300"
      )}
    >
      {/* Progress bar */}
      <div className="fixed top-0 left-0 right-0 z-20 h-1 bg-dark-surface">
        <div
          className="h-full bg-article-blue transition-all duration-300"
          style={{
            width: `${progressPercent}%`,
            boxShadow: "0 0 10px rgba(59, 130, 246, 0.5)",
          }}
        />
      </div>

      {/* Header */}
      <header className="sticky top-1 z-10 bg-dark-surface/95 backdrop-blur border-b border-dark-border">
        <div className="max-w-4xl mx-auto px-4 py-2 flex items-center justify-between">
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-2 text-dark-muted hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm">Library</span>
          </button>

          <div className="text-sm text-dark-muted">
            {navigation && (
              <span>
                <span className="text-white font-medium">{navigation.current_position}</span>
                <span className="mx-1">/</span>
                <span>{navigation.total_unread}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={goToPrev}
              disabled={!navigation?.prev_id}
              className={clsx(
                "p-1.5 rounded transition-colors",
                navigation?.prev_id
                  ? "text-dark-muted hover:text-white hover:bg-dark-hover"
                  : "text-dark-muted/30 cursor-not-allowed"
              )}
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button
              onClick={goToNext}
              disabled={!navigation?.next_id}
              className={clsx(
                "p-1.5 rounded transition-colors",
                navigation?.next_id
                  ? "text-dark-muted hover:text-white hover:bg-dark-hover"
                  : "text-dark-muted/30 cursor-not-allowed"
              )}
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-4 py-8 pb-32">
        {/* Article info */}
        <div className="mb-8 mt-4">
          {/* Title */}
          <h1 className="text-2xl md:text-3xl font-bold text-white mb-4 leading-tight">
            {article.title}
          </h1>

          {/* Source with favicon */}
          {sourceDomain && (
            <div className="flex items-center gap-2 mb-3">
              <img
                src={`https://www.google.com/s2/favicons?domain=${sourceDomain}&sz=16`}
                alt=""
                className="w-4 h-4"
              />
              <span className="text-sm text-dark-muted">{sourceDomain}</span>
            </div>
          )}

          {/* Authors */}
          {article.authors.length > 0 && (
            <p className="text-sm text-dark-muted mb-4">
              {article.authors.join(", ")}
            </p>
          )}

          {/* Metadata row */}
          <div className="flex flex-wrap items-center gap-2 mb-6">
            {article.reading_time_minutes && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-dark-hover rounded-full text-sm text-dark-muted">
                <Clock className="w-3.5 h-3.5" />
                {article.reading_time_minutes} min read
              </span>
            )}
            {/* Tags - horizontal scroll */}
            {article.tags.length > 0 && (
              <div className="flex items-center gap-2 overflow-x-auto scrollbar-hide">
                {article.tags.map((tag) => (
                  <span
                    key={tag.id}
                    className="flex-shrink-0 px-3 py-1 rounded-full text-sm whitespace-nowrap"
                    style={{
                      backgroundColor: tag.color ? `${tag.color}20` : "#8B5CF620",
                      color: tag.color || "#8B5CF6",
                    }}
                  >
                    {tag.name}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex flex-col gap-3">
            <button
              onClick={openArticle}
              className="w-full flex items-center justify-center gap-2 px-6 py-3.5 bg-article-blue text-white rounded-xl font-medium transition-all hover:brightness-110 hover:scale-[1.01] active:scale-[0.99]"
            >
              <ExternalLink className="w-5 h-5" />
              <span>Open Article</span>
            </button>
            <button
              onClick={() => setShowMarkAsReadModal(true)}
              className="w-full flex items-center justify-center gap-2 px-6 py-3.5 border border-dark-border text-white rounded-xl font-medium transition-all hover:bg-dark-hover hover:scale-[1.01] active:scale-[0.99]"
            >
              <Check className="w-5 h-5" />
              <span>Mark as Read</span>
            </button>
          </div>
        </div>

        {/* Summary */}
        {article.summary && (
          <div className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-8">
            <h2 className="text-lg font-semibold text-white mb-4">Summary</h2>
            <div
              className={clsx(
                "prose-dark relative",
                isLongSummary && !summaryExpanded && "max-h-80 overflow-hidden"
              )}
            >
              <ReactMarkdown>{article.summary}</ReactMarkdown>
              {/* Gradient fade */}
              {isLongSummary && !summaryExpanded && (
                <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-dark-surface to-transparent" />
              )}
            </div>
            {isLongSummary && (
              <button
                onClick={() => setSummaryExpanded(!summaryExpanded)}
                className="mt-4 text-sm text-article-blue hover:text-article-blue/80 transition-colors"
              >
                {summaryExpanded ? "Show less" : "Show more"}
              </button>
            )}
            {article.summary_model && (
              <p className="mt-4 text-xs text-dark-muted">
                Generated by {article.summary_model}
              </p>
            )}
          </div>
        )}

        {/* Categories */}
        {article.categories.length > 0 && (
          <div className="mb-8">
            <span className="text-xs uppercase tracking-wider text-dark-muted mb-3 block">
              Categories
            </span>
            <div className="flex flex-wrap gap-2">
              {article.categories.map((cat) => (
                <span
                  key={cat.id}
                  className="px-3 py-1.5 bg-dark-hover text-dark-muted rounded-lg text-sm"
                >
                  {cat.name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Keyboard hints - dismissable, desktop only */}
        {showKeyboardHints && (
          <div className="hidden md:flex items-center justify-center gap-4 mt-12 text-xs text-dark-muted">
            <span>
              Press <kbd className="px-1.5 py-0.5 bg-dark-hover rounded mx-1">J</kbd>/<kbd className="px-1.5 py-0.5 bg-dark-hover rounded mx-1">K</kbd> to navigate
              <span className="mx-2">·</span>
              <kbd className="px-1.5 py-0.5 bg-dark-hover rounded mx-1">O</kbd> to open
              <span className="mx-2">·</span>
              <kbd className="px-1.5 py-0.5 bg-dark-hover rounded mx-1">M</kbd> to mark read
            </span>
            <button
              onClick={dismissKeyboardHints}
              className="p-1 hover:text-white transition-colors"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </main>

      {/* Mark as Read Modal */}
      {showMarkAsReadModal && (
        <MarkAsReadModal
          article={article}
          onConfirm={handleMarkAsRead}
          onCancel={() => setShowMarkAsReadModal(false)}
        />
      )}
    </div>
  );
}
