"use client";

import { useEffect, useState } from "react";
import {
  Plus,
  Trash2,
  Star,
  CheckCircle,
  XCircle,
  Loader2,
  Key,
  Bot,
  FileText,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
} from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { AddArticleModal } from "@/components/articles/AddArticleModal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import {
  useProviders,
  useAvailableProviders,
  useCreateProvider,
  useUpdateProvider,
  useDeleteProvider,
  useTestProvider,
  useColors,
  useUpdateColor,
  useSummaryPrompt,
} from "@/hooks/useProviders";
import { clsx } from "clsx";
import type { ProviderName } from "@/types";

export default function SettingsPage() {
  const providers = useProviders();
  const availableProviders = useAvailableProviders();
  const createProvider = useCreateProvider();
  const updateProvider = useUpdateProvider();
  const deleteProvider = useDeleteProvider();
  const testProvider = useTestProvider();
  const { data: colors } = useColors();
  const updateColor = useUpdateColor();
  const { data: promptData, isLoading: promptLoading } = useSummaryPrompt();
  const [editingColors, setEditingColors] = useState<Record<string, string>>({});

  const [showAddModal, setShowAddModal] = useState(false);
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);
  const [showUserPrompt, setShowUserPrompt] = useState(false);
  const [copiedSystem, setCopiedSystem] = useState(false);
  const [copiedUser, setCopiedUser] = useState(false);
  const [newProvider, setNewProvider] = useState({
    provider_name: "anthropic" as ProviderName,
    display_name: "",
    model_id: "",
    api_key: "",
  });

  // Set default model when provider changes
  useEffect(() => {
    if (availableProviders.data) {
      const provider = availableProviders.data.providers[newProvider.provider_name];
      if (provider) {
        setNewProvider((prev) => ({
          ...prev,
          model_id: provider.default_model,
          display_name: prev.display_name || `${provider.display_name} API`,
        }));
      }
    }
  }, [newProvider.provider_name, availableProviders.data]);

  const handleAddProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    await createProvider.mutateAsync(newProvider);
    setShowAddModal(false);
    setNewProvider({
      provider_name: "anthropic",
      display_name: "",
      model_id: "",
      api_key: "",
    });
  };

  const copyToClipboard = async (text: string, type: "system" | "user") => {
    await navigator.clipboard.writeText(text);
    if (type === "system") {
      setCopiedSystem(true);
      setTimeout(() => setCopiedSystem(false), 2000);
    } else {
      setCopiedUser(true);
      setTimeout(() => setCopiedUser(false), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-dark-bg flex">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <Header />

        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>

            {/* AI Providers Section */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-white">AI Providers</h2>
                  <p className="text-sm text-dark-muted mt-1">
                    Configure AI providers for summarization and categorization
                  </p>
                </div>
                <Button size="sm" onClick={() => setShowAddModal(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Provider
                </Button>
              </div>

              {providers.isLoading && (
                <div className="py-8 text-center">
                  <Loader2 className="w-6 h-6 text-article-blue animate-spin mx-auto" />
                </div>
              )}

              {providers.data && providers.data.length === 0 && (
                <div className="py-8 text-center text-dark-muted">
                  <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No AI providers configured</p>
                  <p className="text-sm mt-1">Add a provider to enable AI features</p>
                </div>
              )}

              {providers.data && providers.data.length > 0 && (
                <div className="space-y-3">
                  {providers.data.map((provider) => (
                    <div
                      key={provider.id}
                      className={clsx(
                        "flex items-center justify-between p-4 rounded-lg border",
                        provider.is_active
                          ? "bg-dark-bg border-dark-border"
                          : "bg-dark-bg/50 border-dark-border/50 opacity-60"
                      )}
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={clsx(
                            "w-10 h-10 rounded-lg flex items-center justify-center",
                            provider.provider_name === "anthropic" && "bg-orange-500/20",
                            provider.provider_name === "openai" && "bg-green-500/20",
                            provider.provider_name === "google" && "bg-blue-500/20"
                          )}
                        >
                          <Key className="w-5 h-5 text-dark-text" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-white">
                              {provider.display_name}
                            </span>
                            {provider.is_default && (
                              <span className="flex items-center gap-1 text-xs text-article-blue">
                                <Star className="w-3 h-3 fill-current" />
                                Default
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-dark-muted">
                            {provider.model_id} &middot; {provider.api_key_masked}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => testProvider.mutate(provider.id)}
                          disabled={testProvider.isPending}
                        >
                          {testProvider.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            "Test"
                          )}
                        </Button>
                        {!provider.is_default && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              updateProvider.mutate({
                                id: provider.id,
                                updates: { is_default: true },
                              })
                            }
                          >
                            Set Default
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteProvider.mutate(provider.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Colors Section */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6 mb-6">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-white">Color Labels</h2>
                <p className="text-sm text-dark-muted mt-1">
                  Customize color labels for organizing articles
                </p>
              </div>

              {colors && (
                <div className="grid grid-cols-2 gap-3">
                  {colors.map((color) => (
                    <div
                      key={color.id}
                      className="flex items-center gap-3 p-3 bg-dark-bg rounded-lg border border-dark-border"
                    >
                      <div
                        className="w-4 h-4 rounded-full flex-shrink-0"
                        style={{ backgroundColor: color.hex_value }}
                      />
                      <input
                        type="text"
                        value={editingColors[color.id] ?? color.name}
                        onChange={(e) =>
                          setEditingColors((prev) => ({
                            ...prev,
                            [color.id]: e.target.value,
                          }))
                        }
                        onBlur={() => {
                          const newName = editingColors[color.id];
                          if (newName && newName !== color.name) {
                            updateColor.mutate({ id: color.id, name: newName });
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.currentTarget.blur();
                          }
                        }}
                        className="flex-1 bg-transparent text-dark-text border-none outline-none focus:ring-1 focus:ring-article-blue rounded px-1"
                      />
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Summarization Prompt Section */}
            <section className="bg-dark-surface border border-dark-border rounded-lg p-6">
              <div className="mb-4">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-article-blue" />
                  <h2 className="text-lg font-semibold text-white">Summarization Prompt</h2>
                </div>
                <p className="text-sm text-dark-muted mt-1">
                  The AI prompt used to generate article summaries
                </p>
              </div>

              {promptLoading && (
                <div className="py-4 text-center">
                  <Loader2 className="w-6 h-6 text-article-blue animate-spin mx-auto" />
                </div>
              )}

              {promptData && (
                <div className="space-y-4">
                  {/* System Prompt */}
                  <div className="border border-dark-border rounded-lg overflow-hidden">
                    <button
                      onClick={() => setShowSystemPrompt(!showSystemPrompt)}
                      className="w-full flex items-center justify-between p-4 bg-dark-bg hover:bg-dark-hover transition-colors"
                    >
                      <span className="font-medium text-white">System Prompt</span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(promptData.system_prompt, "system");
                          }}
                          className="p-1 hover:bg-dark-border rounded"
                          title="Copy to clipboard"
                        >
                          {copiedSystem ? (
                            <Check className="w-4 h-4 text-green-500" />
                          ) : (
                            <Copy className="w-4 h-4 text-dark-muted" />
                          )}
                        </button>
                        {showSystemPrompt ? (
                          <ChevronUp className="w-5 h-5 text-dark-muted" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-dark-muted" />
                        )}
                      </div>
                    </button>
                    {showSystemPrompt && (
                      <div className="p-4 bg-dark-bg/50 border-t border-dark-border">
                        <pre className="text-sm text-dark-text whitespace-pre-wrap font-mono overflow-x-auto max-h-96 overflow-y-auto">
                          {promptData.system_prompt}
                        </pre>
                      </div>
                    )}
                  </div>

                  {/* User Prompt */}
                  <div className="border border-dark-border rounded-lg overflow-hidden">
                    <button
                      onClick={() => setShowUserPrompt(!showUserPrompt)}
                      className="w-full flex items-center justify-between p-4 bg-dark-bg hover:bg-dark-hover transition-colors"
                    >
                      <span className="font-medium text-white">User Prompt Template</span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(promptData.user_prompt, "user");
                          }}
                          className="p-1 hover:bg-dark-border rounded"
                          title="Copy to clipboard"
                        >
                          {copiedUser ? (
                            <Check className="w-4 h-4 text-green-500" />
                          ) : (
                            <Copy className="w-4 h-4 text-dark-muted" />
                          )}
                        </button>
                        {showUserPrompt ? (
                          <ChevronUp className="w-5 h-5 text-dark-muted" />
                        ) : (
                          <ChevronDown className="w-5 h-5 text-dark-muted" />
                        )}
                      </div>
                    </button>
                    {showUserPrompt && (
                      <div className="p-4 bg-dark-bg/50 border-t border-dark-border">
                        <pre className="text-sm text-dark-text whitespace-pre-wrap font-mono overflow-x-auto">
                          {promptData.user_prompt}
                        </pre>
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-dark-muted">
                    To customize the prompt, edit the file at: <code className="bg-dark-bg px-1 rounded">backend/app/ai/prompts.py</code>
                  </p>
                </div>
              )}
            </section>
          </div>
        </main>
      </div>

      <AddArticleModal />

      {/* Add Provider Modal */}
      <Modal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        title="Add AI Provider"
        size="md"
      >
        <form onSubmit={handleAddProvider}>
          <div className="space-y-4">
            {/* Provider select */}
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1.5">
                Provider
              </label>
              <select
                value={newProvider.provider_name}
                onChange={(e) =>
                  setNewProvider((prev) => ({
                    ...prev,
                    provider_name: e.target.value as ProviderName,
                  }))
                }
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text focus:outline-none focus:ring-2 focus:ring-article-blue"
              >
                {availableProviders.data &&
                  Object.entries(availableProviders.data.providers).map(
                    ([key, provider]) => (
                      <option key={key} value={key}>
                        {provider.display_name}
                      </option>
                    )
                  )}
              </select>
            </div>

            {/* Display name */}
            <Input
              id="display_name"
              label="Display Name"
              placeholder="My Claude API"
              value={newProvider.display_name}
              onChange={(e) =>
                setNewProvider((prev) => ({ ...prev, display_name: e.target.value }))
              }
              required
            />

            {/* Model select */}
            <div>
              <label className="block text-sm font-medium text-dark-text mb-1.5">
                Model
              </label>
              <select
                value={newProvider.model_id}
                onChange={(e) =>
                  setNewProvider((prev) => ({ ...prev, model_id: e.target.value }))
                }
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-dark-text focus:outline-none focus:ring-2 focus:ring-article-blue"
              >
                {availableProviders.data &&
                  Object.entries(
                    availableProviders.data.providers[newProvider.provider_name]?.models || {}
                  ).map(([key, name]) => (
                    <option key={key} value={key}>
                      {name}
                    </option>
                  ))}
              </select>
            </div>

            {/* API Key */}
            <Input
              id="api_key"
              type="password"
              label="API Key"
              placeholder="sk-..."
              value={newProvider.api_key}
              onChange={(e) =>
                setNewProvider((prev) => ({ ...prev, api_key: e.target.value }))
              }
              required
            />
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <Button type="button" variant="secondary" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={createProvider.isPending}>
              Add Provider
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
