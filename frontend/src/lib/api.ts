import axios, { AxiosInstance } from "axios";
import type {
  Article,
  ArticleListResponse,
  Category,
  Tag,
  Color,
  AIProvider,
  AvailableProviders,
  CreateProviderRequest,
  Note,
  AskResponse,
  UnreadNavigationResponse,
  UnreadListResponse,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_URL}/api`,
      withCredentials: true,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  // Articles
  async getArticles(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    category_id?: string;
    tag_id?: string;
    color_id?: string;
    status?: string;
    is_read?: boolean;
  }): Promise<ArticleListResponse> {
    const { data } = await this.client.get("/articles", { params });
    return data;
  }

  async getArticle(id: string): Promise<Article> {
    const { data } = await this.client.get(`/articles/${id}`);
    return data;
  }

  async getArticleText(id: string): Promise<{ text: string }> {
    const { data } = await this.client.get(`/articles/${id}/text`);
    return data;
  }

  async createArticleFromUrl(url: string): Promise<Article> {
    const { data } = await this.client.post("/articles", { url });
    return data;
  }

  async uploadArticle(file: File): Promise<Article> {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await this.client.post("/articles/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  }

  async updateArticle(
    id: string,
    updates: { title?: string; color_id?: string; category_ids?: string[]; tag_ids?: string[]; is_read?: boolean }
  ): Promise<Article> {
    const { data } = await this.client.patch(`/articles/${id}`, updates);
    return data;
  }

  async deleteArticle(id: string): Promise<void> {
    await this.client.delete(`/articles/${id}`);
  }

  async processArticle(id: string, providerId?: string): Promise<Article> {
    const { data } = await this.client.post(`/articles/${id}/process`, null, {
      params: providerId ? { provider_id: providerId } : undefined,
    });
    return data;
  }

  async reorganizeArticles(uncategorizedOnly: boolean = true): Promise<{
    message: string;
    processed: number;
    total_articles: number;
    errors: string[];
  }> {
    const { data } = await this.client.post(`/articles/reorganize`, null, {
      params: { uncategorized_only: uncategorizedOnly },
    });
    return data;
  }

  async askQuestion(question: string): Promise<AskResponse> {
    const { data } = await this.client.post("/articles/ask", { question });
    return data;
  }

  // Bulk operations
  async bulkDeleteArticles(articleIds: string[]): Promise<{ deleted: number; failed: string[] }> {
    const { data } = await this.client.post("/articles/bulk/delete", { article_ids: articleIds });
    return data;
  }

  async bulkUpdateColor(articleIds: string[], colorId: string | null): Promise<{ updated: number; failed: string[] }> {
    const { data } = await this.client.patch("/articles/bulk/color", {
      article_ids: articleIds,
      color_id: colorId,
    });
    return data;
  }

  async bulkReanalyzeArticles(articleIds: string[]): Promise<{ queued: number; skipped: number; failed: string[] }> {
    const { data } = await this.client.post("/articles/bulk/reanalyze", { article_ids: articleIds });
    return data;
  }

  // Unread Reader
  async getUnreadList(): Promise<UnreadListResponse> {
    const { data } = await this.client.get("/articles/unread/list");
    return data;
  }

  async getUnreadNavigation(articleId: string): Promise<UnreadNavigationResponse> {
    const { data } = await this.client.get(`/articles/unread/navigation/${articleId}`);
    return data;
  }

  // Categories
  async getCategories(): Promise<Category[]> {
    const { data } = await this.client.get("/categories");
    return data;
  }

  async createCategory(category: { name: string; parent_id?: string; description?: string }): Promise<Category> {
    const { data } = await this.client.post("/categories", category);
    return data;
  }

  async updateCategory(id: string, updates: { name?: string; parent_id?: string; description?: string }): Promise<Category> {
    const { data } = await this.client.patch(`/categories/${id}`, updates);
    return data;
  }

  async deleteCategory(id: string): Promise<void> {
    await this.client.delete(`/categories/${id}`);
  }

  // Tags
  async getTags(): Promise<Tag[]> {
    const { data } = await this.client.get("/tags");
    return data;
  }

  async createTag(tag: { name: string; color?: string }): Promise<Tag> {
    const { data } = await this.client.post("/tags", tag);
    return data;
  }

  async deleteTag(id: string): Promise<void> {
    await this.client.delete(`/tags/${id}`);
  }

  // Notes
  async getArticleNotes(articleId: string): Promise<Note[]> {
    const { data } = await this.client.get(`/articles/${articleId}/notes`);
    return data;
  }

  async createNote(articleId: string, content: string): Promise<Note> {
    const { data } = await this.client.post(`/articles/${articleId}/notes`, { content });
    return data;
  }

  async updateNote(noteId: string, content: string): Promise<Note> {
    const { data } = await this.client.patch(`/notes/${noteId}`, { content });
    return data;
  }

  async deleteNote(noteId: string): Promise<void> {
    await this.client.delete(`/notes/${noteId}`);
  }

  // Settings - AI Providers
  async getAvailableProviders(): Promise<AvailableProviders> {
    const { data } = await this.client.get("/settings/providers/available");
    return data;
  }

  async getProviders(): Promise<AIProvider[]> {
    const { data } = await this.client.get("/settings/providers");
    return data;
  }

  async createProvider(provider: CreateProviderRequest): Promise<AIProvider> {
    const { data } = await this.client.post("/settings/providers", provider);
    return data;
  }

  async updateProvider(
    id: string,
    updates: { display_name?: string; model_id?: string; api_key?: string; is_default?: boolean; is_active?: boolean }
  ): Promise<AIProvider> {
    const { data } = await this.client.patch(`/settings/providers/${id}`, updates);
    return data;
  }

  async deleteProvider(id: string): Promise<void> {
    await this.client.delete(`/settings/providers/${id}`);
  }

  async testProvider(id: string): Promise<{ success: boolean; message: string }> {
    const { data } = await this.client.post(`/settings/providers/${id}/test`);
    return data;
  }

  // Settings - Colors
  async getColors(): Promise<Color[]> {
    const { data } = await this.client.get("/settings/colors");
    return data;
  }

  async updateColor(id: string, updates: { name?: string; hex_value?: string }): Promise<Color> {
    const { data } = await this.client.patch(`/settings/colors/${id}`, null, { params: updates });
    return data;
  }

  // Settings - Prompts
  async getSummaryPrompt(): Promise<{ system_prompt: string; user_prompt: string }> {
    const { data } = await this.client.get("/settings/prompts/summary");
    return data;
  }

  // Health
  async healthCheck(): Promise<{ status: string; database: string }> {
    const { data } = await this.client.get("/health");
    return data;
  }
}

export const api = new ApiClient();
