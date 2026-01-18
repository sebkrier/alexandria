# Contributing to Alexandria

Thank you for your interest in contributing to Alexandria!

## Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- pixi (Python environment manager)
- Node.js 20+ (only for WhatsApp bot)

### Getting Started

1. Fork and clone the repository
2. Follow the setup instructions in [README.md](./README.md)
3. Create a branch for your feature or fix

### Backend Development

The backend serves both the API and the HTMX-based frontend (Jinja2 templates).

```bash
cd backend

# Install dependencies
pixi install
pixi run sync

# Run migrations
pixi run migrate

# Start development server
pixi run dev

# Run tests
pixi run test

# Lint and format code
pixi run lint        # Check for issues
pixi run lint-fix    # Auto-fix issues
pixi run format      # Format code
```

### WhatsApp Bot (Optional)

```bash
cd whatsapp-bot
npm install
npm start
```

## Code Style

### Python
- Format with `ruff format`
- Lint with `ruff check`
- Use type hints for function signatures
- Follow existing patterns in the codebase

### Templates (Jinja2/HTMX)
- Follow existing template structure in `backend/templates/`
- Use Tailwind CSS classes for styling
- Use Alpine.js for client-side interactivity
- Prefer HTMX attributes over custom JavaScript

## Pull Request Guidelines

1. **Keep PRs focused** - one feature or fix per PR
2. **Write clear commit messages** - describe what and why
3. **Update documentation** if you change user-facing behavior
4. **Add tests** for new functionality
5. **Run `pixi run lint` and `pixi run test`** before submitting

## Project Structure

```
alexandria/
├── backend/
│   ├── app/
│   │   ├── ai/          # AI provider integrations (LiteLLM)
│   │   ├── api/         # FastAPI routes (htmx.py for UI, routes/ for JSON API)
│   │   ├── db/          # Database connections
│   │   ├── extractors/  # Content extraction (URL, PDF, arXiv, YouTube, Google Drive)
│   │   ├── models/      # SQLAlchemy models
│   │   └── schemas/     # Pydantic schemas
│   ├── templates/       # Jinja2 templates for HTMX UI
│   │   ├── pages/       # Full page templates
│   │   ├── partials/    # HTMX partial templates
│   │   ├── components/  # Reusable UI components
│   │   └── modals/      # Modal dialogs
│   ├── static/          # Static assets
│   └── tests/
├── whatsapp-bot/        # WhatsApp integration for remote article adding
└── scripts/             # Utility scripts (backup, etc.)
```

## Questions?

Open an issue for questions or discussion about proposed changes.
