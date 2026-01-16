# Alexandria Development

## Stack
- Backend: FastAPI + SQLAlchemy + PostgreSQL (with pgvector)
- Frontend: Currently Next.js/React, migrating to HTMX + Jinja2
- Styling: Tailwind CSS
- Package management: pixi + uv for Python, npm for JS (being removed)

## Commands
- Start PostgreSQL: `docker start alexandria-db`
- Backend dev server: `cd backend && pixi run dev` (runs on :8000)
- Frontend dev server: `cd frontend && npm run dev` (runs on :3000)
- Run backend tests: `cd backend && pixi run test`
- Lint backend: `cd backend && pixi run lint`

## HTMX Migration Rules - IMPORTANT
1. Keep ALL existing JSON API routes working - don't modify them
2. New HTML-returning routes go in `backend/app/api/htmx.py`
3. Templates go in `backend/templates/` using Jinja2
4. Always verify visually with Chrome DevTools MCP before proceeding
5. Use Tailwind via CDN, not the compiled Next.js version
6. Each migration phase must leave the app in a working state
7. If something breaks visually, STOP and debug with browser tools

## Style Guidelines
- Dark mode UI (bg-gray-900, text-gray-100 palette)
- Cards use subtle borders and hover states
- Preserve existing visual design exactly
