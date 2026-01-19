# Alexandria - Project Context for Claude

## Overview

Alexandria is a personal research library app for storing, organizing, and retrieving articles with AI-powered summarization and categorization.

**Tech Stack:** Python/FastAPI backend + HTMX/Jinja2/Alpine.js frontend + PostgreSQL with pgvector

---

## Quick Start

```bash
# Terminal 1 - Database
docker start alexandria-db

# Terminal 2 - Backend
cd ~/alexandria/backend
pixi run dev
# Runs at http://localhost:8000/app/
```

---

## Database Connection

```
Host: localhost
Port: 5432
User: postgres
Password: localdev
Database: alexandria
```

Quick test:
```bash
PGPASSWORD=localdev psql -h localhost -U postgres -d alexandria -c "SELECT COUNT(*) FROM articles;"
```

---

## Key File Locations

| File | Purpose |
|------|---------|
| `backend/app/api/htmx.py` | All HTMX routes (~3000+ lines) |
| `backend/app/ai/llm.py` | LiteLLM provider integration + metadata extraction |
| `backend/app/ai/prompts.py` | All AI prompts (summary, tags, categories, metadata) |
| `backend/app/ai/factory.py` | AI provider factory |
| `backend/app/ai/service.py` | AI service for article processing |
| `backend/app/ai/base.py` | Pydantic models for AI responses |
| `backend/app/extractors/` | Content extraction (URL, PDF, arXiv, YouTube, Google Drive) |
| `backend/app/extractors/pdf.py` | PDF extraction with Google Drive support |
| `backend/templates/` | Jinja2 templates for HTMX UI |
| `backend/app/api/routes/` | JSON API routes (used by WhatsApp bot) |

---

## AI Providers (January 2026)

### Supported Models

| Provider | Models | Default |
|----------|--------|---------|
| **Anthropic** | Claude Opus 4.5, Sonnet 4.5, Haiku 4.5 | `claude-opus-4-5-20251101` |
| **OpenAI** | GPT-5.2, GPT-5.1, GPT-4.1, o3-mini | `gpt-5.2` |
| **Google** | Gemini 3.0 Pro, Gemini 3.0 Flash, 2.5 series | `gemini-3.0-pro` |

### Key Files
- Model lists: `backend/app/ai/llm.py` → `PROVIDER_MODELS`
- Display names: `backend/app/ai/factory.py` → `PROVIDER_DISPLAY_NAMES`
- Individual providers: `backend/app/ai/providers/`

---

## Content Extraction

The URL extractor (`backend/app/extractors/url.py`) handles article fetching:
- Uses `httpx` for async HTTP requests
- Uses `readability-lxml` for content extraction
- Falls back to BeautifulSoup for short content
- **Important:** `Accept-Encoding` header must NOT include `br` (Brotli) unless the brotli package is installed

### PDF Extraction (`backend/app/extractors/pdf.py`)

- Supports direct PDF URLs and **Google Drive** links
- Google Drive formats: `drive.google.com/file/d/`, `/open?id=`, `/uc?id=`
- Handles Google Drive virus scan confirmation for large files
- Uses PyMuPDF (fitz) for text extraction
- **AI metadata extraction**: For PDFs, the AI extracts accurate titles and full author lists during processing (see `app/ai/service.py`)

### Text Cleaning (`backend/app/extractors/base.py`)

- `_clean_text()`: Removes null bytes and control characters that break PostgreSQL
- `_clean_title()`: Sanitizes titles for database storage

---

## Development Guidelines

1. **Test after each change** - Use curl first, then browser
2. **Commit working fixes** - `git add -A && git commit -m "Fix: <description>"`
3. **Check server logs** - Watch the terminal running `pixi run dev` for Python errors
4. **Don't modify JSON API routes** - The WhatsApp bot depends on them

---

## Common Issues & Solutions

### Article extraction returns garbled text
- **Cause:** Server returns Brotli-compressed content but `brotli` package not installed
- **Fix:** Remove `br` from `Accept-Encoding` header in `url.py`

### Settings page issues
- **Add provider modal:** Uses plain JavaScript (not Alpine.js) for model dropdown
- **Active provider:** Click on provider card to make it active

### Import errors
- Run `pixi install` and `pixi run sync` to ensure dependencies are installed

---

## Useful Commands

```bash
# Lint and format
cd backend
pixi run lint
pixi run lint-fix
pixi run format

# Run tests (requires test database)
pixi run test

# Set up test database (one-time, or after schema changes)
pixi run test-db-setup

# Run setup + tests together
pixi run test-full

# Database migrations
pixi run migrate
```
