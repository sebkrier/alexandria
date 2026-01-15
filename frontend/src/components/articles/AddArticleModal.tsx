"use client";

import { useState, useRef } from "react";
import { Upload, Link as LinkIcon } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useStore } from "@/lib/store";
import { useCreateArticle, useUploadArticle, useProcessArticle } from "@/hooks/useArticles";
import { clsx } from "clsx";

export function AddArticleModal() {
  const { addArticleModalOpen, setAddArticleModalOpen } = useStore();
  const [mode, setMode] = useState<"url" | "upload">("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [autoProcess, setAutoProcess] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const createArticle = useCreateArticle();
  const uploadArticle = useUploadArticle();
  const processArticle = useProcessArticle();

  const isLoading = createArticle.isPending || uploadArticle.isPending;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      let article;

      if (mode === "url" && url) {
        article = await createArticle.mutateAsync(url);
      } else if (mode === "upload" && file) {
        article = await uploadArticle.mutateAsync(file);
      }

      if (article && autoProcess) {
        processArticle.mutate({ id: article.id });
      }

      // Reset and close
      setUrl("");
      setFile(null);
      setAddArticleModalOpen(false);
    } catch {
      // Error handled by mutation's onError callback
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && selectedFile.type === "application/pdf") {
      setFile(selectedFile);
    }
  };

  return (
    <Modal
      open={addArticleModalOpen}
      onClose={() => setAddArticleModalOpen(false)}
      title="Add Article"
      size="md"
    >
      {/* Mode tabs */}
      <div className="flex gap-2 mb-6">
        <button
          type="button"
          onClick={() => setMode("url")}
          className={clsx(
            "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg border transition-colors",
            mode === "url"
              ? "bg-article-blue/10 border-article-blue text-article-blue"
              : "border-dark-border text-dark-muted hover:text-dark-text hover:border-dark-hover"
          )}
        >
          <LinkIcon className="w-4 h-4" />
          <span>URL</span>
        </button>
        <button
          type="button"
          onClick={() => setMode("upload")}
          className={clsx(
            "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg border transition-colors",
            mode === "upload"
              ? "bg-article-blue/10 border-article-blue text-article-blue"
              : "border-dark-border text-dark-muted hover:text-dark-text hover:border-dark-hover"
          )}
        >
          <Upload className="w-4 h-4" />
          <span>PDF Upload</span>
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {mode === "url" ? (
          <div className="mb-4">
            <Input
              id="url"
              type="url"
              label="Article URL"
              placeholder="https://example.com/article or https://arxiv.org/abs/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
            <p className="mt-2 text-xs text-dark-muted">
              Supports web articles, blog posts, and arXiv papers
            </p>
          </div>
        ) : (
          <div className="mb-4">
            <label className="block text-sm font-medium text-dark-text mb-1.5">
              PDF File
            </label>
            <div
              onClick={() => fileInputRef.current?.click()}
              className={clsx(
                "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
                file
                  ? "border-article-blue bg-article-blue/5"
                  : "border-dark-border hover:border-dark-hover"
              )}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              {file ? (
                <div>
                  <p className="text-white font-medium">{file.name}</p>
                  <p className="text-sm text-dark-muted mt-1">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <div>
                  <Upload className="w-8 h-8 text-dark-muted mx-auto mb-2" />
                  <p className="text-dark-muted">Click to select a PDF file</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Auto-process option */}
        <label className="flex items-center gap-3 mb-6 cursor-pointer">
          <input
            type="checkbox"
            checked={autoProcess}
            onChange={(e) => setAutoProcess(e.target.checked)}
            className="w-4 h-4 rounded border-dark-border bg-dark-bg text-article-blue focus:ring-article-blue"
          />
          <span className="text-sm text-dark-text">
            Automatically generate summary and tags
          </span>
        </label>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => setAddArticleModalOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            loading={isLoading}
            disabled={(mode === "url" && !url) || (mode === "upload" && !file)}
          >
            Add Article
          </Button>
        </div>
      </form>
    </Modal>
  );
}
