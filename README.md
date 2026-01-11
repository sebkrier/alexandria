# Alexandria

A personal research library for storing, organizing, and retrieving articles with AI-powered summarization and categorization.

## Features

- **Multi-source ingestion**: Import from URLs, PDFs, arXiv, Substack, and YouTube
- **AI summarization**: Generate structured summaries with key contributions, findings, and relevance notes
- **Auto-tagging**: AI suggests relevant tags based on content
- **Auto-categorization**: Articles are automatically placed in your category hierarchy
- **Ask your library**: RAG-powered Q&A across all your saved articles
- **Rich notes**: Markdown notes with formatting toolbar on each article
- **Full-text search**: Find articles by content, title, or metadata
- **Color coding**: Visual organization with customizable colors
- **Reading time**: Estimated reading time for each article
- **Dark mode UI**: Easy on the eyes, content-forward design

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI / SQLAlchemy / PostgreSQL
- **Frontend**: Next.js 14 / React / Tailwind CSS
- **AI Providers**: Anthropic Claude, OpenAI GPT-4, or Google Gemini
- **Storage**: Cloudflare R2 (optional, for PDF storage)

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL (via Docker or local install)

### 1. Clone and setup

```bash
git clone https://github.com/yourusername/alexandria.git
cd alexandria
```

### 2. Start PostgreSQL

Using Docker (recommended):
```bash
docker run -d --name alexandria-db \
  -e POSTGRES_DB=alexandria \
  -e POSTGRES_PASSWORD=localdev \
  -p 5432:5432 \
  postgres:15
```

Or use an existing PostgreSQL installation.

### 3. Setup the backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local development)

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 4. Setup the frontend

Open a new terminal:
```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local

# Start the dev server
npm run dev
```

### 5. Open the app

Visit **http://localhost:3000** and create your account.

## Adding AI Providers

After creating your account:

1. Go to **Settings** (gear icon)
2. Click **"Add Provider"**
3. Select your provider (Anthropic, OpenAI, or Google)
4. Enter your API key
5. Choose a model
6. Click **"Test"** to verify it works
7. Set as default if desired

Your API keys are encrypted and stored securely in the database.

## Windows Launcher (WSL)

If you're using Windows with WSL, you can create a batch file to launch everything with one click.

### Create the launcher

Save this as `Alexandria.bat` on your Desktop:

```batch
@echo off
:: Alexandria - Start Backend and Frontend

:: Start backend
start wt -w 0 new-tab -p "Ubuntu" -- wsl bash -c "cd ~/alexandria/backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000; exec bash"

:: Wait for backend to start
timeout /t 3 /nobreak > nul

:: Start frontend
start wt -w 0 new-tab -p "Ubuntu" -- wsl bash -c "cd ~/alexandria/frontend && npm run dev; exec bash"

:: Wait for frontend to start
timeout /t 5 /nobreak > nul

:: Open browser
start http://localhost:3000
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
│   │   ├── ai/              # AI provider abstraction
│   │   ├── api/             # FastAPI routes
│   │   ├── extractors/      # Content extraction (URL, PDF, arXiv, YouTube)
│   │   ├── models/          # SQLAlchemy models
│   │   └── schemas/         # Pydantic schemas
│   ├── alembic/             # Database migrations
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages
│   │   ├── components/      # React components
│   │   ├── hooks/           # React Query hooks
│   │   └── lib/             # API client, state
│   └── public/
├── scripts/                 # Utility scripts
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
| `JWT_SECRET` | Secret for JWT tokens (generate with `openssl rand -hex 32`) | Required |
| `ENCRYPTION_KEY` | Key for encrypting API keys (generate with `openssl rand -hex 32`) | Required |
| `DEBUG` | Enable debug mode | `true` |
| `CORS_ORIGINS` | Allowed frontend origins | `["http://localhost:3000"]` |
| `R2_*` | Cloudflare R2 credentials (optional) | - |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000` |

## License

MIT
