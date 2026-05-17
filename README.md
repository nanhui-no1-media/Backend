# Backend

Django + React full-stack project.

## Tech Stack

- **Backend**: Python 3.14 / Django 6.0 / SQLite
- **Frontend**: React 19 / TypeScript / Webpack 5

## Getting Started

### Backend

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Production build:

```bash
cd frontend
npm run build
```
