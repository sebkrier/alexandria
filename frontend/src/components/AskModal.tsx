"use client";

import { useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { Loader2, Send, MessageSquare, FileText } from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { useAskQuestion } from "@/hooks/useAsk";
import type { AskResponse } from "@/types";

interface AskModalProps {
  open: boolean;
  onClose: () => void;
}

export function AskModal({ open, onClose }: AskModalProps) {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<AskResponse | null>(null);
  const askQuestion = useAskQuestion();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    try {
      const result = await askQuestion.mutateAsync(question);
      setResponse(result);
    } catch (error) {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    setQuestion("");
    setResponse(null);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Ask your library" size="lg">
      <div className="space-y-4">
        {/* Question input */}
        <form onSubmit={handleSubmit}>
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your saved articles..."
              className="flex-1 px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text placeholder-dark-muted focus:outline-none focus:ring-1 focus:ring-article-blue"
              disabled={askQuestion.isPending}
            />
            <Button
              type="submit"
              disabled={!question.trim() || askQuestion.isPending}
              loading={askQuestion.isPending}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </form>

        {/* Response */}
        {askQuestion.isPending && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-article-blue animate-spin" />
            <span className="ml-2 text-dark-muted">Searching your library...</span>
          </div>
        )}

        {response && !askQuestion.isPending && (
          <div className="space-y-4">
            {/* Answer */}
            <div className="bg-dark-bg border border-dark-border rounded-lg p-4">
              <div className="flex items-start gap-2 mb-2">
                <MessageSquare className="w-4 h-4 text-article-blue mt-1 flex-shrink-0" />
                <span className="text-sm font-medium text-white">Answer</span>
              </div>
              <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0">
                <ReactMarkdown>{response.answer}</ReactMarkdown>
              </div>
            </div>

            {/* Referenced articles */}
            {response.articles.length > 0 && (
              <div className="bg-dark-bg border border-dark-border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <FileText className="w-4 h-4 text-dark-muted" />
                  <span className="text-sm font-medium text-white">Sources</span>
                </div>
                <div className="space-y-2">
                  {response.articles.map((article) => (
                    <Link
                      key={article.id}
                      href={`/article/${article.id}`}
                      onClick={handleClose}
                      className="block text-sm text-article-blue hover:underline"
                    >
                      {article.title}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {!response && !askQuestion.isPending && (
          <div className="text-center py-8 text-dark-muted">
            <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Ask questions about your saved articles</p>
            <p className="text-xs mt-1">The AI will search your library and provide answers based on your content</p>
          </div>
        )}
      </div>
    </Modal>
  );
}
