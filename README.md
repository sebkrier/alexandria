# Alexandria

![Alexandria UI](UI.png?v=2)

A personal research library for storing, organizing, and retrieving articles with AI-powered summarization and categorization.

## Features

- **Multi-source ingestion**: Import from URLs, PDFs, arXiv, Substack, YouTube, LessWrong/Alignment Forum, and Google Drive
- **AI summarization**: Generate structured summaries with key contributions, findings, and relevance notes
- **AI metadata extraction**: Automatically extracts accurate titles and full author lists from PDFs using AI
- **Auto-tagging**: AI suggests relevant tags based on content
- **Hierarchical categories**: Two-level category system (parent → subcategory) with automatic AI categorization
- **Taxonomy Optimization**: AI-powered category restructuring that analyzes your entire library and proposes an optimal category structure
- **Unread Reader**: Dedicated reading queue with keyboard navigation (J/K), progress tracking, notes, and quick mark-as-read workflow
- **Semantic search**: Find conceptually related articles using local embeddings (all-mpnet-base-v2)
- **Ask your library**: Hybrid RAG with intelligent query routing — content questions use semantic + keyword search, metadata questions query the database directly
- **Remote add via WhatsApp**: Add articles from anywhere by sending links to a WhatsApp bot
- **Bulk actions**: Select multiple articles for bulk delete, recolor, mark read/unread, or re-analyze
- **Media type badges**: Visual indicators for article sources (URL, PDF, arXiv, Video)
- **Rich notes**: WYSIWYG editor with formatting toolbar on each article
- **Full-text search**: PostgreSQL full-text search across content, title, tags, and metadata
- **Color coding**: Visual organization with customizable color labels (editable in settings)
- **Reading time**: Estimated reading time based on word count
- **Dark mode UI**: Easy on the eyes, content-forward design
- **Backup & Restore**: Export/import your entire library as JSON

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy + psycopg3 / PostgreSQL
- **Frontend**: HTMX + Jinja2 + Alpine.js + Tailwind CSS (via CDN)
- **Package Management**: pixi + uv (fast, reproducible Python environments)
- **AI Integration**: LiteLLM (unified interface for Anthropic, OpenAI, Google)
- **Embeddings**: sentence-transformers (all-mpnet-base-v2) — runs locally, no API key needed
- **Vector Search**: pgvector extension for PostgreSQL
- **Database Queries**: SQLAlchemy ORM + psycopg3 parameterized queries for security-critical operations
- **Storage**: Cloudflare R2 (optional, for PDF storage)

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension (via Docker or local install)

### 1. Clone and setup

```bash
git clone https://github.com/sebkrier/alexandria.git
cd alexandria
```

### 2. Start PostgreSQL with pgvector

Using Docker (recommended):
```bash
docker run -d --name alexandria-db \
  -e POSTGRES_DB=alexandria \
  -e POSTGRES_PASSWORD=localdev \
  -p 5432:5432 \
  pgvector/pgvector:pg15
```

Or use an existing PostgreSQL installation with pgvector extension installed.

### 3. Setup the backend

```bash
cd backend

# Install pixi if not already installed
curl -fsSL https://pixi.sh/install.sh | bash
# Or from GitHub releases if pixi.sh is unavailable:
# curl -fsSL https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-unknown-linux-musl.tar.gz | tar -xzf - -C ~/.local/bin

# Install dependencies (includes sentence-transformers for embeddings)
pixi install
pixi run sync

# Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local development)

# Run database migrations (creates tables and enables pgvector)
pixi run migrate

# Start the server
pixi run dev
```

**Note:** The first time you add an article, the embedding model (~420MB) will be downloaded from Hugging Face. This is a one-time download.

### 4. Open the app

Visit **http://localhost:8000/app/** — the app is ready to use immediately (no login required).

## Adding AI Providers

To enable AI-powered summarization and categorization:

1. Go to **Settings** (gear icon in sidebar)
2. Click **"Add Provider"**
3. Select your provider (Anthropic, OpenAI, or Google)
4. Enter your API key
5. Choose a model
6. Click **"Save Provider"**
7. Click on a provider card to make it active (the active provider is used for all AI operations)
8. Use the **"Test"** button to verify your connection works

### Supported Models (January 2026)

| Provider | Models | Get API Key |
|----------|--------|-------------|
| **Anthropic** | Claude Opus 4.5, Sonnet 4.5, Haiku 4.5 | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| **OpenAI** | GPT-5.2, GPT-5.1, GPT-4.1, o3-mini | [platform.openai.com](https://platform.openai.com/api-keys) |
| **Google** | Gemini 3.0 Pro, Gemini 3.0 Flash, 2.5 Pro/Flash | [aistudio.google.com](https://aistudio.google.com/apikey) |

Your API keys are encrypted and stored securely in the database.

## Remote Add via WhatsApp

Add articles to Alexandria from anywhere using WhatsApp. See the **Remote Add** page in the app for setup instructions, or:

### Quick Setup

```bash
cd whatsapp-bot
npm install
npm start
```

1. A QR code will appear in the terminal
2. Open WhatsApp → Settings → Linked Devices → Link a Device
3. Scan the QR code
4. Send any URL in any chat — only YOUR messages are captured (links from others are ignored)
5. Articles are automatically processed with AI summaries in the background

### Keep the bot running

Use PM2 to run the bot in the background:
```bash
npm install -g pm2
pm2 start bot.js --name alexandria-whatsapp
pm2 startup && pm2 save
```

## Backup & Restore

Alexandria supports exporting and importing your entire library for backup or migration purposes.

### Export via UI

1. Go to **Settings** → **Backup** tab
2. Click **"Export Library"**
3. A JSON file containing all your articles, tags, categories, and notes will download

### Import via UI

1. Go to **Settings** → **Backup** tab
2. Click **"Import Library"** and select a previously exported JSON file
3. Choose whether to merge with existing data or replace

### Local Database Backup

For a full PostgreSQL backup (recommended for production):

```bash
# Run the backup script
./scripts/backup_local.sh

# Or specify a custom backup directory
./scripts/backup_local.sh /path/to/backups
```

Backups are saved as timestamped `.sql.gz` files. To restore:

```bash
gunzip -c backup_file.sql.gz | PGPASSWORD=localdev psql -h localhost -U postgres -d alexandria
```

## Development

### Linting & Formatting

**Backend (Python):**
```bash
cd backend

# Check for issues
pixi run lint

# Auto-fix and format
pixi run lint-fix
pixi run format
```

### Running Tests

```bash
cd backend
pixi run test
```

To run tests with the test database (for parameterized query tests):

```bash
# Create test database (one-time setup)
sudo -u postgres psql -c "CREATE DATABASE alexandria_test;"
sudo -u postgres psql -d alexandria_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run all tests
pixi run test
```

## Windows Launcher (WSL)

If you're using Windows with WSL, you can create a batch file to launch everything with one click.

### Create the launcher

Save this as `Alexandria.bat` on your Desktop:

```batch
@echo off
:: Alexandria - Start Backend

:: Start backend
start wt -w 0 new-tab -p "Ubuntu" -- wsl bash -c "cd ~/alexandria/backend && ~/.local/bin/pixi run dev; exec bash"

:: Wait for backend to start
timeout /t 5 /nobreak > nul

:: Open browser
start http://localhost:8000/app/
```

**Note:** Replace `"Ubuntu"` with your WSL distribution name (e.g., `"Ubuntu (Preview)"`).

### Pin to taskbar

1. Right-click the `.bat` file → **Create shortcut**
2. Right-click the shortcut → **Properties**
3. Change **Target** to: `cmd.exe /c "C:\path\to\Alexandria.bat"`
4. Click **Change Icon** and pick something nice
5. Drag the shortcut to your taskbar

## Project Structure

```
alexandria/
├── backend/
│   ├── app/
│   │   ├── ai/              # AI provider abstraction (LiteLLM)
│   │   ├── api/             # FastAPI routes (htmx.py for UI, routes/ for JSON API)
│   │   ├── core/            # Constants and shared utilities
│   │   ├── db/              # psycopg3 connection pool & parameterized queries
│   │   ├── extractors/      # Content extraction (URL, PDF, arXiv, YouTube, LessWrong)
│   │   ├── models/          # SQLAlchemy models
│   │   └── schemas/         # Pydantic schemas
│   ├── templates/           # Jinja2 templates for HTMX UI
│   │   ├── pages/           # Full page templates
│   │   ├── partials/        # HTMX partial templates
│   │   ├── components/      # Reusable UI components
│   │   └── modals/          # Modal dialogs
│   ├── static/              # Static assets (images, etc.)
│   ├── alembic/             # Database migrations
│   ├── pixi.toml            # Pixi configuration
│   ├── pyproject.toml       # Python dependencies
│   └── tests/
├── frontend/                # Legacy React frontend (kept for reference)
├── whatsapp-bot/            # WhatsApp bot for remote article adding
│   ├── bot.js               # Bot implementation
│   └── package.json
├── scripts/                 # Utility scripts (backup_local.sh, etc.)
├── DEPLOYMENT.md            # Production deployment guide
└── docker-compose.yml       # Docker setup (alternative)
```

## Docker Compose (Alternative)

Instead of running services separately, you can use Docker Compose:

```bash
docker-compose up -d
```

This starts PostgreSQL, the backend, and frontend all at once.

## API Documentation

With the backend running, visit **http://localhost:8000/docs** for interactive Swagger documentation.

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for Railway deployment instructions.

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:localdev@localhost:5432/alexandria` |
| `ENCRYPTION_KEY` | Key for encrypting API keys (generate with `openssl rand -hex 32`) | Required |
| `DEBUG` | Enable debug mode | `true` |
| `CORS_ORIGINS` | Allowed frontend origins | `["http://localhost:3000"]` |
| `R2_*` | Cloudflare R2 credentials (optional) | - |

### WhatsApp Bot (`whatsapp-bot/`)

| Variable | Description | Default |
|----------|-------------|---------|
| `ALEXANDRIA_API` | Alexandria API URL | `http://localhost:8000/api` |

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](./SECURITY.md) for security practices and vulnerability reporting.

## License

MIT
