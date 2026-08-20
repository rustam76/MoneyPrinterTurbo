# Authentication

MoneyPrinterTurbo supports optional production authentication backed by **PostgreSQL**.

By default authentication is **disabled** (`MPT_AUTH_ENABLED=false`) so existing deployments keep working without a database.

## Environment

Copy `.env.example` and set:

```env
MPT_AUTH_ENABLED=true
DATABASE_URL=postgresql://username:password@host:5432/moneyprinter_auth
MPT_SESSION_SECRET=LONG_RANDOM_SECRET
MPT_SESSION_EXPIRE_HOURS=24
MPT_COOKIE_SECURE=true
MPT_PUBLIC_API_URL=https://your-domain.example
MPT_PUBLIC_WEBUI_URL=https://your-domain.example
```

Do **not** set admin credentials via environment variables. There is no `MPT_ADMIN_USERNAME`, `MPT_ADMIN_EMAIL`, or `MPT_ADMIN_PASSWORD`.

## First deployment

1. Provision PostgreSQL and set `DATABASE_URL`.
2. Set a strong `MPT_SESSION_SECRET`.
3. Start API + WebUI (Docker / Coolify). Migrations run on API startup when auth is enabled.
4. Open the WebUI **Setup** page (`pages/0_Setup.py` in the sidebar).
5. Create the first administrator (username, email, password).
6. You are redirected through `/auth/establish` to set an HttpOnly session cookie, then can use the app.
7. Setup is disabled once any user exists.

## Login

Use the **Login** page (username or email + password).

## User management

Admins open the **Users** page to create/edit users, reset passwords, activate/deactivate, and delete users (with last-admin safety checks).

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/auth/status` | `{enabled, setup_required}` |
| POST | `/auth/setup` | First admin only |
| POST | `/auth/login` | Sets `MPT_SESSION` cookie |
| POST | `/auth/logout` | Invalidates session |
| GET | `/auth/me` | Current user |
| GET | `/auth/csrf` | CSRF token for mutating API calls |
| GET | `/auth/establish` | Cookie bridge for Streamlit |
| * | `/users/*` | Admin only |

When auth is enabled, `/api/v1/*` and `/tasks/*` require a valid session. Mutating API requests need header `X-CSRF-Token`.

## Migrations

```bash
# Automatic on API startup when MPT_AUTH_ENABLED=true
# Or manually:
export DATABASE_URL=postgresql://...
uv run alembic upgrade head
```

## Docker / Coolify

- Pass `DATABASE_URL`, `MPT_AUTH_ENABLED`, `MPT_SESSION_SECRET`, `MPT_SESSION_EXPIRE_HOURS` via environment (see `docker-compose.yml`).
- Use an **external** PostgreSQL instance (Coolify database resource or managed Postgres).
- Terminate TLS at the reverse proxy; set `MPT_COOKIE_SECURE=true`.
- Prefer one public hostname that routes `/api` + `/auth` to the API service and `/` to the WebUI so the session cookie is shared.

## Security notes

- Passwords are hashed with Argon2.
- Session cookies are HttpOnly + SameSite=Lax (+ Secure when configured).
- Session tokens are stored hashed in PostgreSQL.
- Login is rate-limited (5 failures / 15 minutes per IP+identifier).
- Never log passwords, hashes, session tokens, or raw `DATABASE_URL` credentials.
