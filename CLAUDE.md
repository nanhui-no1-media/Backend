# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run python manage.py runserver          # Start dev server
uv run python manage.py migrate            # Apply migrations
uv run python manage.py makemigrations     # Generate migrations
uv run python manage.py check              # Validate project config
uv run python manage.py test               # Run tests
uv run python manage.py test <app>         # Run tests for a single app
uv add <package>                           # Add a dependency
```

## Architecture

- **Python 3.13** project managed with **uv** (`pyproject.toml` + `uv.lock`)
- **Django 6.0** with `config/` as the project settings module (ROOT_URLCONF = `config.urls`)
- Database: SQLite (default, dev only)
- New Django apps should be created with `uv run python manage.py startapp <name>` and added to `INSTALLED_APPS` in `config/settings.py`
