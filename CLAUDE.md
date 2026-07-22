# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Django)

```bash
uv run python manage.py runserver          # Start dev server
uv run python manage.py migrate            # Apply migrations
uv run python manage.py makemigrations     # Generate migrations
uv run python manage.py check              # Validate project config
uv run python manage.py test               # Run tests
uv run python manage.py test <app>         # Run tests for a single app
uv add <package>                           # Add a Python dependency
```

### Frontend (React)

```bash
cd frontend
npm run dev                                # Start dev server (localhost:3000, HMR)
npm run build                              # Production build → frontend/dist/
```

## Architecture

- **Python 3.14** + **Django 6.0** backend, managed with **uv** (`pyproject.toml` + `uv.lock`)
- **React 19** + **TypeScript** + **Webpack 5** frontend in `frontend/`, managed with **npm**
- Django settings module: `config/` (ROOT_URLCONF = `config.urls`)
- Frontend entry: `frontend/src/index.tsx` → built to `frontend/dist/`
- Database: SQLite (default, dev only)
- New Django apps: `uv run python manage.py startapp <name>` → add to `INSTALLED_APPS` in `config/settings.py`

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `nanhui-no1-media/Backend`, managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles; the label string equals the role name (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
