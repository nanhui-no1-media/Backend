# User Authentication Design

## Overview

A user authentication system with login, registration, password reset, and session management. Built on the existing Django + React stack with front-end/back-end separation.

## Tech Decisions

- **Authentication**: Django built-in `django.contrib.auth` + Session (Cookie-based)
- **Cross-origin**: `django-cors-headers` — frontend (localhost:3000) calls backend API (localhost:8000)
- **Password reset email**: `django.core.mail.backends.console.ConsoleEmailBackend` (dev only, prints to console)
- **Phone login**: UI tab exists but marked "not yet available" — SMS integration deferred

## Backend

### New Django app: `accounts`

Uses Django's built-in User model (no custom user model).

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login/` | POST | Login (username/email + password) |
| `/api/auth/register/` | POST | Register |
| `/api/auth/logout/` | POST | Logout |
| `/api/auth/password-reset/` | POST | Request password reset email |
| `/api/auth/password-reset/confirm/` | POST | Confirm password reset with token |
| `/api/auth/me/` | GET | Get current user info |

### Request/Response Examples

**POST /api/auth/login/**
```json
{ "username": "user1", "password": "secret123" }
```
Response 200:
```json
{ "user": { "id": 1, "username": "user1", "email": "user1@example.com" } }
```

**POST /api/auth/register/**
```json
{ "username": "user1", "email": "user1@example.com", "password": "secret123" }
```

**POST /api/auth/password-reset/**
```json
{ "email": "user1@example.com" }
```

**POST /api/auth/password-reset/confirm/**
```json
{ "uid": "MQ", "token": "abc123...", "new_password": "newsecret456" }
```

### Session Flow

1. Frontend sends POST with credentials
2. Django validates, creates session, returns `Set-Cookie: sessionid=...`
3. Browser automatically includes cookie on subsequent requests
4. Django `AuthenticationMiddleware` identifies user from session

### Settings Changes

- Add `corsheaders` and `accounts` to `INSTALLED_APPS`
- Add `CorsMiddleware` to `MIDDLEWARE`
- Set `CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]`
- Set `CORS_ALLOW_CREDENTIALS = True`
- Set `EMAIL_BACKEND` to console backend

## Frontend

### New Dependencies

- `react-router-dom` — client-side routing
- Webpack CSS support: `style-loader` + `css-loader`

### Pages and Routes

| Route | Page | Protected |
|-------|------|-----------|
| `/login` | LoginPage | No |
| `/register` | RegisterPage | No |
| `/forgot-password` | ForgotPasswordPage | No |
| `/` | HomePage | Yes |

### LoginPage

- Single form with Tab switching: Username+Password / Email+Password / Phone+Code
- Phone tab shows "Not yet available" notice
- On success: redirect to `/`
- Link to Register and Forgot Password pages

### Directory Structure

```
frontend/src/
├── api/           # API client (fetch wrapper)
├── components/    # Shared components
├── pages/
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── ForgotPasswordPage.tsx
│   └── HomePage.tsx
├── App.tsx        # Router setup
└── index.tsx
```

## Password Reset Flow

1. User enters email on `/forgot-password`
2. Django generates token, console-email prints reset URL
3. For dev testing: user copies URL from Django console, opens in browser
4. Frontend at `/reset-password?uid=...&token=...` shows new password form
5. On success: redirect to `/login`

## Scope

- In scope: login, register, logout, session persistence, password reset (console email), route protection
- Out of scope: phone SMS verification, social login (OAuth), email verification, custom user model, production email backend
