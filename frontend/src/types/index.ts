// API Types

export type SourceType = "url" | "pdf" | "arxiv" | "video";
export type ProcessingStatus = "pending" | "processing" | "completed" | "failed";
export type ProviderName = "anthropic" | "openai" | "google";

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Article {
  id: string;
  source_type: SourceType;
  original_url: string | null;
  title: string;
  authors: string[];
  publication_date: string | null;
  summary: string | null;
  summary_model: string | null;
  color_id: string | null;
  file_path: string | null;
  metadata: Record<string, unknown>;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  word_count: number | null;
  reading_time_minutes: number | null;
  created_at: string;
  updated_at: string;
  categories: CategoryBrief[];
  tags: TagBrief[];
  note_count: number;
}

export interface CategoryBrief {
  id: string;
  name: string;
  is_primary: boolean;
}

export interface TagBrief {
  id: string;
  name: string;
  color: string | null;
}

export interface Category {
  id: string;
  name: string;
  parent_id: string | null;
  description: string | null;
  position: number;
  article_count: number;
  created_at: string;
  updated_at: string;
  children?: Category[];
}

export interface Tag {
  id: string;
  name: string;
  color: string | null;
  article_count: number;
  created_at: string;
}

export interface Color {
  id: string;
  name: string;
  hex_value: string;
  position: number;
}

export interface AIProvider {
  id: string;
  provider_name: ProviderName;
  display_name: string;
  model_id: string;
  api_key_masked: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Note {
  id: string;
  article_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

// API Response Types

export interface ArticleListResponse {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface AvailableProviders {
  providers: Record<
    string,
    {
      display_name: string;
      models: Record<string, string>;
      default_model: string;
    }
  >;
}

// Request Types

export interface LoginRequest {
  email: string;
  password: string;
}

export interface CreateArticleRequest {
  url: string;
}

export interface CreateProviderRequest {
  provider_name: ProviderName;
  display_name: string;
  model_id: string;
  api_key: string;
}

// Ask (RAG) Types

export interface ArticleReference {
  id: string;
  title: string;
}

export interface AskResponse {
  answer: string;
  articles: ArticleReference[];
}
