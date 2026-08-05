
# Apcotex R&D Backend

Production-grade FastAPI backend for the **Apcotex R&D Patent Research & Polymer Recipe Simulation** platform.

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| Runtime | Python 3.13 |
| Database | PostgreSQL 15+ |
| ORM | SQLAlchemy 2.x (Async) |
| Driver | asyncpg |
| Migrations | Alembic |
| Schemas | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Settings | pydantic-settings |

---

## Project Structure

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── auth.py          # POST /login, POST /refresh
│   │   ├── users.py         # GET /me
│   │   └── health.py        # GET /health
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env vars)
│   │   ├── security.py      # JWT + bcrypt helpers
│   │   └── logging.py       # Console + rotating file logger
│   ├── db/
│   │   ├── database.py      # Async engine + Base
│   │   └── session.py       # AsyncSession factory + get_db()
│   ├── models/
│   │   ├── base.py          # UUIDPrimaryKeyMixin, TimestampMixin
│   │   ├── user.py          # User ORM model
│   │   └── research_run.py  # ResearchRun ORM model
│   ├── schemas/
│   │   ├── common.py        # SuccessResponse[T], ErrorResponse
│   │   ├── auth.py          # LoginRequest, TokenResponse
│   │   └── user.py          # UserOut, UserCreate
│   ├── services/
│   │   ├── auth_service.py  # login(), refresh()
│   │   └── user_service.py  # get_by_id(), get_by_email()
│   ├── repositories/
│   │   └── user_repository.py  # Async CRUD for users
│   ├── dependencies/
│   │   └── auth.py          # get_current_user(), require_role()
│   ├── utils/
│   │   └── exceptions.py    # Domain exceptions + FastAPI handlers
│   └── main.py              # FastAPI application factory
├── alembic/
│   ├── env.py               # Async Alembic environment
│   ├── script.py.mako       # Migration file template
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
├── main.py                  # Uvicorn entry point
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Setup

### 1. Prerequisites

- Python 3.13
- PostgreSQL 15+

### 2. Create virtual environment

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/apcotex_db
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
```

### 5. Create the database

```bash
# Using psql
psql -U postgres -c "CREATE DATABASE apcotex_db;"
```

### 6. Run database migrations

```bash
alembic upgrade head
```

### 7. Start the server

```bash
# Development (auto-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or
python main.py
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | ❌ | Service + DB health check |
| POST | `/api/v1/auth/login` | ❌ | Login → access + refresh tokens |
| POST | `/api/v1/auth/refresh` | ❌ | Refresh → new access token |
| GET | `/api/v1/users/me` | ✅ Bearer | Current user profile |

**Swagger UI:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

---

## Seeding an Admin User

After migration, create the first admin user directly in psql:

```sql
-- Generate a bcrypt hash first (Python):
-- from passlib.context import CryptContext
-- print(CryptContext(schemes=["bcrypt"]).hash("yourpassword"))

INSERT INTO users (username, email, hashed_password, full_name, role, is_active)
VALUES (
  'admin',
  'admin@apcotex.com',
  '$2b$12$<your_bcrypt_hash_here>',
  'System Administrator',
  'ADMIN',
  true
);
```

Or run the helper script:

```bash
python -c "
from passlib.context import CryptContext
pwd = CryptContext(schemes=['bcrypt']).hash('Admin@123!')
print(pwd)
"
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | asyncpg PostgreSQL connection string |
| `SECRET_KEY` | ✅ | — | JWT signing secret (min 32 chars) |
| `ALGORITHM` | ❌ | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `30` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ❌ | `7` | Refresh token lifetime |
| `GEMINI_API_KEY` | ❌ | `""` | Phase 2 placeholder |
| `SERPER_API_KEY` | ❌ | `""` | Phase 2 placeholder |
| `LOG_LEVEL` | ❌ | `INFO` | Python log level |
| `LOG_DIR` | ❌ | `logs` | Directory for rotating log files |
| `DEBUG` | ❌ | `false` | Enables SQL echo + verbose logging |

---

## Alembic Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Generate a new migration (after changing models)
alembic revision --autogenerate -m "describe your change"

# View current migration state
alembic current

# View migration history
alembic history
```
