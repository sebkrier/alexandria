"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { formatDistanceToNow, format } from "date-fns";
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  Globe,
  GraduationCap,
  Loader2,
  RefreshCw,
  Trash2,
  Clock,
  AlertCircle,
  Plus,
  X,
  Pencil,
  Check,
  Palette,
  Video,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { MarkdownEditor } from "@/components/ui/MarkdownEditor";
import { useArticle, useProcessArticle, useDeleteArticle, useUpdateArticle } from "@/hooks/useArticles";
import { useArticleNotes, useCreateNote, useUpdateNote, useDeleteNote } from "@/hooks/useNotes";
import { useTags, useCreateTag } from "@/hooks/useTags";
import { useCategories, useCreateCategory } from "@/hooks/useCategories";
import { useColors } from "@/hooks/useProviders";
import { clsx } from "clsx";
import type { ProcessingStatus } from "@/types";

const sourceIcons = {
  url: Globe,
  pdf: FileText,
  arxiv: GraduationCap,
  video: Video,
};

const statusLabels: Record<ProcessingStatus, string> = {
  pending: "Pending processing",
  processing: "Processing...",
  completed: "Processed",
  failed: "Processing failed",
};

export default function ArticlePage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const article = useArticle(id);
  const processArticle = useProcessArticle();
  const deleteArticle = useDeleteArticle();
  const updateArticle = useUpdateArticle();
  const { data: colors } = useColors();
  const { data: notes, isLoading: notesLoading } = useArticleNotes(id);
  const { data: allTags } = useTags();
  const { data: allCategories } = useCategories();
  const createNote = useCreateNote();
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();
  const createTag = useCreateTag();
  const createCategory = useCreateCategory();

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [newNote, setNewNote] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteContent, setEditingNoteContent] = useState("");
  const [editingTags, setEditingTags] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [showTagDropdown, setShowTagDropdown] = useState(false);
  const [editingCategories, setEditingCategories] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [showCategoryDropdown, setShowCategoryDropdown] = useState(false);
  const [selectedParentCategory, setSelectedParentCategory] = useState<string | null>(null);

  if (article.isLoading) {
    return (
      <div className="min-h-screen bg-dark-bg flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-article-blue animate-spin" />
      </div>
    );
  }

  if (!article.data) {
    return (
      <div className="min-h-screen bg-dark-bg flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-xl font-medium text-white mb-2">Article not found</h1>
          <Link href="/" className="text-article-blue hover:underline">
            Return to library
          </Link>
        </div>
      </div>
    );
  }

  const data = article.data;
  const SourceIcon = sourceIcons[data.source_type];
  const articleColor = colors?.find((c) => c.id === data.color_id);

  const handleDelete = async () => {
    await deleteArticle.mutateAsync(id);
    router.push("/");
  };

  const handleReprocess = () => {
    processArticle.mutate({ id });
  };

  const handleColorChange = (colorId: string | null) => {
    updateArticle.mutate({
      id,
      updates: { color_id: colorId || undefined },
    });
    setShowColorPicker(false);
  };

  const handleAddNote = () => {
    if (!newNote.trim()) return;
    createNote.mutate({ articleId: id, content: newNote });
    setNewNote("");
  };

  const handleUpdateNote = (noteId: string) => {
    if (!editingNoteContent.trim()) return;
    updateNote.mutate({ noteId, content: editingNoteContent, articleId: id });
    setEditingNoteId(null);
    setEditingNoteContent("");
  };

  const handleDeleteNote = (noteId: string) => {
    deleteNote.mutate({ noteId, articleId: id });
  };

  const handleRemoveTag = (tagId: string) => {
    const currentTagIds = data?.tags.map((t) => t.id) || [];
    const newTagIds = currentTagIds.filter((id) => id !== tagId);
    updateArticle.mutate({ id, updates: { tag_ids: newTagIds } });
  };

  const handleAddTag = (tagId: string) => {
    const currentTagIds = data?.tags.map((t) => t.id) || [];
    if (!currentTagIds.includes(tagId)) {
      updateArticle.mutate({ id, updates: { tag_ids: [...currentTagIds, tagId] } });
    }
    setShowTagDropdown(false);
    setNewTagName("");
  };

  const handleCreateAndAddTag = async () => {
    if (!newTagName.trim()) return;
    const result = await createTag.mutateAsync({ name: newTagName.trim() });
    if (result?.id) {
      const currentTagIds = data?.tags.map((t) => t.id) || [];
      updateArticle.mutate({ id, updates: { tag_ids: [...currentTagIds, result.id] } });
    }
    setNewTagName("");
    setShowTagDropdown(false);
  };

  // Filter tags not already on the article
  const availableTags = allTags?.filter(
    (tag) => !data?.tags.some((t) => t.id === tag.id)
  ) || [];

  // Filter dropdown by search
  const filteredTags = availableTags.filter((tag) =>
    tag.name.toLowerCase().includes(newTagName.toLowerCase())
  );

  // Category handlers
  const handleRemoveCategory = (categoryId: string) => {
    const currentCategoryIds = data?.categories.map((c) => c.id) || [];
    const newCategoryIds = currentCategoryIds.filter((id) => id !== categoryId);
    updateArticle.mutate({ id, updates: { category_ids: newCategoryIds } });
  };

  const handleAddCategory = (categoryId: string) => {
    const currentCategoryIds = data?.categories.map((c) => c.id) || [];
    if (!currentCategoryIds.includes(categoryId)) {
      updateArticle.mutate({ id, updates: { category_ids: [...currentCategoryIds, categoryId] } });
    }
    setShowCategoryDropdown(false);
    setNewCategoryName("");
  };

  const handleCreateAndAddCategory = async () => {
    if (!newCategoryName.trim()) return;
    const result = await createCategory.mutateAsync({
      name: newCategoryName.trim(),
      parent_id: selectedParentCategory || undefined,
    });
    if (result?.id) {
      const currentCategoryIds = data?.categories.map((c) => c.id) || [];
      updateArticle.mutate({ id, updates: { category_ids: [...currentCategoryIds, result.id] } });
    }
    setNewCategoryName("");
    setShowCategoryDropdown(false);
    setSelectedParentCategory(null);
  };

  // Flatten categories for dropdown (with indentation info)
  const flattenCategories = (cats: typeof allCategories, depth = 0): Array<{ id: string; name: string; depth: number }> => {
    if (!cats) return [];
    return cats.flatMap((cat) => [
      { id: cat.id, name: cat.name, depth },
      ...flattenCategories(cat.children, depth + 1),
    ]);
  };

  const allFlatCategories = flattenCategories(allCategories);

  // Filter categories not already on the article
  const availableCategories = allFlatCategories.filter(
    (cat) => !data?.categories.some((c) => c.id === cat.id)
  );

  // Filter dropdown by search
  const filteredCategories = availableCategories.filter((cat) =>
    cat.name.toLowerCase().includes(newCategoryName.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="bg-dark-surface border-b border-dark-border sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-dark-muted hover:text-dark-text transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to library</span>
          </Link>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleReprocess}
              loading={processArticle.isPending}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Reprocess
            </Button>
            {showDeleteConfirm ? (
              <div className="flex items-center gap-2">
                <span className="text-sm text-dark-muted">Delete?</span>
                <Button variant="danger" size="sm" onClick={handleDelete}>
                  Yes
                </Button>
                <Button variant="secondary" size="sm" onClick={() => setShowDeleteConfirm(false)}>
                  No
                </Button>
              </div>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setShowDeleteConfirm(true)}>
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main content */}
          <div className="lg:col-span-2">
            {/* Title */}
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-3">
                <SourceIcon className="w-5 h-5 text-dark-muted" />
                {articleColor && (
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: articleColor.hex_value }}
                  />
                )}
                <span className="text-sm text-dark-muted capitalize">{data.source_type}</span>
              </div>
              <h1 className="text-2xl font-bold text-white">{data.title}</h1>
              {data.authors.length > 0 && (
                <p className="text-dark-muted mt-2">{data.authors.join(", ")}</p>
              )}
            </div>

            {/* Processing status */}
            {data.processing_status !== "completed" && (
              <div
                className={clsx(
                  "mb-6 p-4 rounded-lg border",
                  data.processing_status === "failed"
                    ? "bg-article-red/10 border-article-red/30"
                    : "bg-article-blue/10 border-article-blue/30"
                )}
              >
                <div className="flex items-center gap-3">
                  {data.processing_status === "processing" ? (
                    <Loader2 className="w-5 h-5 text-article-blue animate-spin" />
                  ) : data.processing_status === "failed" ? (
                    <AlertCircle className="w-5 h-5 text-article-red" />
                  ) : (
                    <Clock className="w-5 h-5 text-dark-muted" />
                  )}
                  <div>
                    <p className="font-medium text-white">
                      {statusLabels[data.processing_status]}
                    </p>
                    {data.processing_error && (
                      <p className="text-sm text-dark-muted mt-1">{data.processing_error}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Summary */}
            {data.summary && (
              <div className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-6">
                <h2 className="text-lg font-semibold text-white mb-4">Summary</h2>
                <div className="prose-dark">
                  <ReactMarkdown>{data.summary}</ReactMarkdown>
                </div>
                {data.summary_model && (
                  <p className="mt-4 text-xs text-dark-muted">
                    Generated by {data.summary_model}
                  </p>
                )}
              </div>
            )}

            {/* Original link */}
            {data.original_url && (
              <div className="mb-6">
                <a
                  href={data.original_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-article-blue hover:underline"
                >
                  <ExternalLink className="w-4 h-4" />
                  View original
                </a>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Color Picker */}
            <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Color</h3>
                <button
                  onClick={() => setShowColorPicker(!showColorPicker)}
                  className="text-dark-muted hover:text-white transition-colors"
                >
                  <Palette className="w-4 h-4" />
                </button>
              </div>
              {showColorPicker ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => handleColorChange(null)}
                    className={clsx(
                      "w-8 h-8 rounded-full border-2 flex items-center justify-center",
                      !data.color_id ? "border-white" : "border-dark-border"
                    )}
                  >
                    <X className="w-4 h-4 text-dark-muted" />
                  </button>
                  {colors?.map((color) => (
                    <button
                      key={color.id}
                      onClick={() => handleColorChange(color.id)}
                      className={clsx(
                        "w-8 h-8 rounded-full border-2",
                        data.color_id === color.id ? "border-white" : "border-transparent"
                      )}
                      style={{ backgroundColor: color.hex_value }}
                      title={color.name}
                    />
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  {articleColor ? (
                    <>
                      <div
                        className="w-6 h-6 rounded-full"
                        style={{ backgroundColor: articleColor.hex_value }}
                      />
                      <span className="text-sm text-dark-text">{articleColor.name}</span>
                    </>
                  ) : (
                    <span className="text-sm text-dark-muted">No color</span>
                  )}
                </div>
              )}
            </div>

            {/* Categories */}
            <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Categories</h3>
                <button
                  onClick={() => setEditingCategories(!editingCategories)}
                  className="text-dark-muted hover:text-white transition-colors"
                >
                  {editingCategories ? <Check className="w-4 h-4" /> : <Pencil className="w-4 h-4" />}
                </button>
              </div>

              {/* Current categories */}
              {data.categories.length > 0 ? (
                <div className="flex flex-wrap gap-2 mb-3">
                  {data.categories.map((cat) => (
                    <Badge key={cat.id} size="md">
                      <span className="flex items-center gap-1">
                        {cat.name}
                        {editingCategories && (
                          <button
                            onClick={() => handleRemoveCategory(cat.id)}
                            className="ml-1 hover:text-article-red"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        )}
                      </span>
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-dark-muted mb-3">No categories</p>
              )}

              {/* Add categories UI */}
              {editingCategories && (
                <div className="relative">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCategoryName}
                      onChange={(e) => {
                        setNewCategoryName(e.target.value);
                        setShowCategoryDropdown(true);
                      }}
                      onFocus={() => setShowCategoryDropdown(true)}
                      placeholder="Add category..."
                      className="flex-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text placeholder-dark-muted text-sm focus:outline-none focus:ring-1 focus:ring-article-blue"
                    />
                    {newCategoryName.trim() && !filteredCategories.some((c) => c.name.toLowerCase() === newCategoryName.toLowerCase()) && (
                      <Button
                        size="sm"
                        onClick={handleCreateAndAddCategory}
                        loading={createCategory.isPending}
                      >
                        <Plus className="w-4 h-4" />
                      </Button>
                    )}
                  </div>

                  {/* Parent category selector for new categories */}
                  {newCategoryName.trim() && !filteredCategories.some((c) => c.name.toLowerCase() === newCategoryName.toLowerCase()) && (
                    <div className="mt-2">
                      <select
                        value={selectedParentCategory || ""}
                        onChange={(e) => setSelectedParentCategory(e.target.value || null)}
                        className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text text-sm focus:outline-none focus:ring-1 focus:ring-article-blue"
                      >
                        <option value="">No parent (top-level)</option>
                        {allFlatCategories.map((cat) => (
                          <option key={cat.id} value={cat.id}>
                            {"—".repeat(cat.depth)} {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Dropdown */}
                  {showCategoryDropdown && filteredCategories.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-dark-surface border border-dark-border rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
                      {filteredCategories.map((cat) => (
                        <button
                          key={cat.id}
                          onClick={() => handleAddCategory(cat.id)}
                          className="w-full px-3 py-2 text-left text-sm text-dark-text hover:bg-dark-bg transition-colors"
                          style={{ paddingLeft: `${12 + cat.depth * 12}px` }}
                        >
                          {cat.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Tags */}
            <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Tags</h3>
                <button
                  onClick={() => setEditingTags(!editingTags)}
                  className="text-dark-muted hover:text-white transition-colors"
                >
                  {editingTags ? <Check className="w-4 h-4" /> : <Pencil className="w-4 h-4" />}
                </button>
              </div>

              {/* Current tags */}
              {data.tags.length > 0 ? (
                <div className="flex flex-wrap gap-2 mb-3">
                  {data.tags.map((tag) => (
                    <Badge key={tag.id} size="md" color={tag.color || undefined}>
                      <span className="flex items-center gap-1">
                        {tag.name}
                        {editingTags && (
                          <button
                            onClick={() => handleRemoveTag(tag.id)}
                            className="ml-1 hover:text-article-red"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        )}
                      </span>
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-dark-muted mb-3">No tags</p>
              )}

              {/* Add tags UI */}
              {editingTags && (
                <div className="relative">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newTagName}
                      onChange={(e) => {
                        setNewTagName(e.target.value);
                        setShowTagDropdown(true);
                      }}
                      onFocus={() => setShowTagDropdown(true)}
                      placeholder="Add tag..."
                      className="flex-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text placeholder-dark-muted text-sm focus:outline-none focus:ring-1 focus:ring-article-blue"
                    />
                    {newTagName.trim() && !filteredTags.some((t) => t.name.toLowerCase() === newTagName.toLowerCase()) && (
                      <Button
                        size="sm"
                        onClick={handleCreateAndAddTag}
                        loading={createTag.isPending}
                      >
                        <Plus className="w-4 h-4" />
                      </Button>
                    )}
                  </div>

                  {/* Dropdown */}
                  {showTagDropdown && (filteredTags.length > 0 || newTagName.trim()) && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-dark-surface border border-dark-border rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
                      {filteredTags.map((tag) => (
                        <button
                          key={tag.id}
                          onClick={() => handleAddTag(tag.id)}
                          className="w-full px-3 py-2 text-left text-sm text-dark-text hover:bg-dark-bg transition-colors flex items-center gap-2"
                        >
                          {tag.color && (
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: tag.color }}
                            />
                          )}
                          {tag.name}
                        </button>
                      ))}
                      {newTagName.trim() && !filteredTags.some((t) => t.name.toLowerCase() === newTagName.toLowerCase()) && (
                        <button
                          onClick={handleCreateAndAddTag}
                          className="w-full px-3 py-2 text-left text-sm text-article-blue hover:bg-dark-bg transition-colors flex items-center gap-2"
                        >
                          <Plus className="w-3 h-3" />
                          Create "{newTagName}"
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Metadata */}
            <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Details</h3>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-dark-muted">Added</dt>
                  <dd className="text-dark-text">
                    {format(new Date(data.created_at), "MMM d, yyyy 'at' h:mm a")}
                  </dd>
                </div>
                {data.publication_date && (
                  <div>
                    <dt className="text-dark-muted">Published</dt>
                    <dd className="text-dark-text">
                      {format(new Date(data.publication_date), "MMM d, yyyy")}
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-dark-muted">Source</dt>
                  <dd className="text-dark-text capitalize">{data.source_type}</dd>
                </div>
                {data.reading_time_minutes && (
                  <div>
                    <dt className="text-dark-muted">Reading time</dt>
                    <dd className="text-dark-text">{data.reading_time_minutes} min</dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Notes */}
            <div className="bg-dark-surface border border-dark-border rounded-lg p-4">
              <h3 className="text-sm font-semibold text-white mb-3">Notes</h3>

              {/* Add new note */}
              <div className="mb-4">
                <MarkdownEditor
                  value={newNote}
                  onChange={setNewNote}
                  placeholder="Add a note..."
                  rows={3}
                />
                {newNote.trim() && (
                  <div className="flex justify-end mt-2">
                    <Button
                      size="sm"
                      onClick={handleAddNote}
                      loading={createNote.isPending}
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Add Note
                    </Button>
                  </div>
                )}
              </div>

              {/* Notes list */}
              {notesLoading ? (
                <div className="text-center py-4">
                  <Loader2 className="w-5 h-5 text-dark-muted animate-spin mx-auto" />
                </div>
              ) : notes && notes.length > 0 ? (
                <div className="space-y-3">
                  {notes.map((note) => (
                    <div
                      key={note.id}
                      className="bg-dark-bg border border-dark-border rounded-lg p-3"
                    >
                      {editingNoteId === note.id ? (
                        <div>
                          <MarkdownEditor
                            value={editingNoteContent}
                            onChange={setEditingNoteContent}
                            rows={3}
                          />
                          <div className="flex justify-end gap-2 mt-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setEditingNoteId(null);
                                setEditingNoteContent("");
                              }}
                            >
                              Cancel
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => handleUpdateNote(note.id)}
                              loading={updateNote.isPending}
                            >
                              <Check className="w-4 h-4 mr-1" />
                              Save
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="text-sm text-dark-text prose prose-invert prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0">
                            <ReactMarkdown>{note.content}</ReactMarkdown>
                          </div>
                          <div className="flex items-center justify-between mt-2 pt-2 border-t border-dark-border">
                            <span className="text-xs text-dark-muted">
                              {format(new Date(note.created_at), "MMM d, yyyy")}
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => {
                                  setEditingNoteId(note.id);
                                  setEditingNoteContent(note.content);
                                }}
                                className="p-1 text-dark-muted hover:text-white transition-colors"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteNote(note.id)}
                                className="p-1 text-dark-muted hover:text-article-red transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-dark-muted text-center py-2">
                  No notes yet
                </p>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
