# Contributing to Alexandria

Thank you for your interest in contributing to Alexandria!

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ with pgvector extension
- pixi (Python environment manager)

### Getting Started

1. Fork and clone the repository
2. Follow the setup instructions in [README.md](./README.md)
3. Create a branch for your feature or fix

### Backend Development

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

# Lint code
pixi run ruff check .
pixi run ruff format .
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Lint code
npm run lint

# Type check
npx tsc --noEmit
```

## Code Style

### Python
- Format with `ruff format`
- Lint with `ruff check`
- Use type hints for function signatures
- Follow existing patterns in the codebase

### TypeScript/React
- Follow ESLint configuration
- Use TypeScript strict mode
- Prefer functional components with hooks

## Pull Request Guidelines

1. **Keep PRs focused** - one feature or fix per PR
2. **Write clear commit messages** - describe what and why
3. **Update documentation** if you change user-facing behavior
4. **Add tests** for new functionality
5. **Ensure CI passes** before requesting review

## Project Structure

```
alexandria/
├── backend/
│   ├── app/
│   │   ├── ai/          # AI provider integrations
│   │   ├── api/         # FastAPI routes
│   │   ├── db/          # Database connections
│   │   ├── extractors/  # Content extraction
│   │   ├── models/      # SQLAlchemy models
│   │   └── schemas/     # Pydantic schemas
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/         # Next.js pages
│       ├── components/  # React components
│       ├── hooks/       # React Query hooks
│       └── lib/         # Utilities
└── whatsapp-bot/        # WhatsApp integration
```

## Questions?

Open an issue for questions or discussion about proposed changes.
