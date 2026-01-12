# Alexandria - Claude Code Context

## Project Overview

Alexandria is a personal research library with AI-powered summarization. Single-user application deployed on Railway.

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Backend | Python + FastAPI | AI SDKs are Python-first, async support |
| Frontend | Next.js 14 + Tailwind | React ecosystem, server components |
| Database | PostgreSQL + pgvector | Full-text search + vector similarity |
| Embeddings | sentence-transformers | Local embeddings, no API key needed |
| Storage | Cloudflare R2 | S3-compatible, free egress |
| AI | Claude (default) | Best summarization quality |

## Database Schema

```
users           - Single user auth
articles        - Main content store with full-text search + embedding vector (768 dims)
categories      - Hierarchical tree (parent_id self-reference), two-level max
tags            - Flat tags with optional colors
article_categories / article_tags - Junction tables
notes           - Markdown notes per article
ai_providers    - Encrypted API key storage
colors          - User's color palette
reorganization_suggestions - AI suggestions for restructuring
```

**Key columns on articles:**
- `search_vector` (tsvector) - PostgreSQL full-text search
- `embedding` (vector(768)) - Semantic search via pgvector
- `word_count` (int) - For reading time calculation

## Key API Endpoints

```
POST   /api/auth/setup          - First-run account creation
POST   /api/auth/login          - Get JWT token
POST   /api/articles            - Create from URL
POST   /api/articles/upload     - Upload PDF
POST   /api/articles/{id}/process - Run AI summarization
POST   /api/articles/ask        - Ask questions (RAG with query routing)
POST   /api/articles/bulk/delete - Bulk delete articles
POST   /api/articles/bulk/color  - Bulk recolor articles
POST   /api/articles/bulk/reanalyze - Bulk re-analyze articles
GET    /api/categories          - Get category tree with article counts
POST   /api/settings/providers  - Add AI provider
```

## AI Provider Interface

All providers implement:
```python
class AIProvider(ABC):
    async def summarize(text, title, source_type) -> Summary
    async def suggest_tags(text, summary, existing_tags) -> list[TagSuggestion]
    async def suggest_category(text, summary, categories) -> CategorySuggestion
    async def answer_question(context, question) -> str  # For Ask feature
    async def health_check() -> bool
```

## Key Modules

### Embeddings (`app/ai/embeddings.py`)
Local embedding generation using sentence-transformers. No API key required.

```python
from app.ai.embeddings import generate_embedding, generate_query_embedding

# For documents (during article processing)
embedding = generate_embedding(text)  # Returns 768-dim vector

# For search queries (in Ask feature)
query_embedding = generate_query_embedding(question)
```

- Model: `sentence-transformers/all-mpnet-base-v2`
- Dimensions: 768
- First call downloads ~420MB model from Hugging Face

### Query Router (`app/ai/query_router.py`)
Routes Ask questions to appropriate handler:
- **Content queries** → Hybrid search (semantic + keyword) + RAG
- **Metadata queries** → Direct database queries (counts, lists, filters)

### Content Extractors (`app/extractors/`)
- `pdf.py` - Handles both uploaded PDFs and PDF URLs (downloads automatically)
- `url.py` - Generic webpage extraction with readability fallback
- `arxiv.py`, `substack.py`, `youtube.py` - Specialized extractors
- Automatic Content-Type detection for URLs that don't match patterns

## Running Locally

```bash
# Database
docker run -d -e POSTGRES_DB=alexandria -e POSTGRES_PASSWORD=localdev -p 5432:5432 postgres:15

# Backend
cd backend && source venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

## Running with Docker Compose

```bash
docker-compose up -d
```

## Adding New AI Providers

1. Create `backend/app/ai/providers/newprovider.py`:
```python
class NewProvider(AIProvider):
    provider_name = "newprovider"
    MODELS = {"model-id": "Model Name"}
    # Implement summarize, suggest_tags, suggest_category, health_check
```

2. Register in `backend/app/ai/providers/__init__.py`
3. Add to `PROVIDER_CLASSES` in `backend/app/ai/factory.py`

## Adding New Article Source Types

1. Create `backend/app/extractors/newsource.py`:
```python
class NewSourceExtractor(BaseExtractor):
    @staticmethod
    def can_handle(url: str) -> bool:
        return "newsource.com" in url

    async def extract(self, url: str) -> ExtractedContent:
        # Extract content
```

2. Add to `EXTRACTORS` list in `backend/app/extractors/__init__.py` (before GenericURLExtractor)

## Environment Variables

### Backend (Production)
```
DATABASE_URL          - PostgreSQL connection (Railway auto-injects)
JWT_SECRET           - 32-byte hex string
ENCRYPTION_KEY       - 32-byte hex string (for API keys at rest)
CORS_ORIGINS         - ["https://your-frontend.up.railway.app"]
R2_ACCESS_KEY_ID     - Cloudflare R2 credentials
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_ENDPOINT
```

### Frontend
```
NEXT_PUBLIC_API_URL  - Backend URL
```

## File Locations

- Backend entry: `backend/app/main.py`
- Database models: `backend/app/models/`
- API routes: `backend/app/api/routes/`
- AI providers: `backend/app/ai/providers/`
- Content extractors: `backend/app/extractors/`
- Frontend pages: `frontend/src/app/`
- React components: `frontend/src/components/`
- API client: `frontend/src/lib/api.ts`

## Scripts

```bash
# Backfill embeddings for existing articles (after enabling pgvector)
cd backend && python scripts/backfill_embeddings.py

# Run migrations
cd backend && alembic upgrade head
```

## Testing

```bash
# Extractor tests
cd backend && python tests/test_extractors.py

# AI tests (requires API key)
ANTHROPIC_API_KEY=sk-... python tests/test_ai.py
```

## What NOT to Do

- **Don't switch embedding models** without re-running the backfill script. Different models produce incompatible vectors.
- **Don't remove pgvector dependency** — semantic search and the Ask feature depend on it.
- **Don't assign articles to parent categories** — always assign to subcategories. Parent counts are cumulative.
- **Don't skip migrations** — pgvector extension must be enabled before adding articles with embeddings.
