<!-- .github/copilot-instructions.md - Project-specific guidance for AI coding agents -->

# Quick Onboarding — Project Snapshot
- **Purpose:** Telegram bot that indexes photos, computes a difference-hash, and finds duplicates/similar images.
- **Runtime:** Python async using `aiogram` + PostgreSQL backend (via `psycopg`/`psycopg-pool`). Image processing uses `Pillow` and `dlib`.

# High-level Architecture
- `main.py`: app entrypoint. Creates `Bot`, `Dispatcher`, DB pool (`get_pg_pool`) and registers routers from `handlers/`.
- `handlers/`: per-module `Router` objects. `admin.py` defines an `IsAdmin` filter and admin commands; `users.py` handles incoming photos and forwarding.
- `database/`: DB helpers — `database.py` builds connection strings and returns a connection pool; `image.py` defines `ImageRecord`, table creation, insert/query helpers.
- `image/vectorize.py`: image hashing (DifferenceHash) and face detection (dlib).
- `middleware/user.py`: `AlbumMiddleware` collects media group messages and supplies `album` to handlers.

# Key Patterns & Conventions (use these when changing code)
- Routers are module-scoped and included in `main.py` via `dp.include_router(...)`.
- Filters are applied to routers (e.g. `admin.router.message.filter(IsAdmin(...))`). Use `BaseFilter` subclasses for auth-like checks.
- Router-scoped middlewares: attach with `router.message.outer_middleware(...)` to provide extra handler `data` (see `AlbumMiddleware`).
- DB pool is passed into handlers through dispatcher workflow data and as an argument in handler signatures (e.g. `async def process_data_command(message: Message, db_pool)`).
- Config loaded with `config.load_config()` using `environs` and `.env` variables; keys the code expects: `BOT_TOKEN`, `ADMIN_IDS`, `DB_NAME`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `IMAGE_PATH`.

# Important Files to Reference
- `main.py` — startup, router inclusion, and how `db_pool` and `IMAGE_PATH` are injected.
- `database/database.py` — `get_pg_pool`, `build_pg_conninfo` (connection string format) and logging of DB version.
- `database/image.py` — schema creation (`images` table), `ImageRecord` fields, `append_image_record`, `find_similar_images`, and `create_database` which reads `IMAGE_PATH`.
- `image/vectorize.py` — `DifferenceHash()` implementation and `detect_faces()` (uses `dlib`).
- `handlers/admin.py` and `handlers/users.py` — show command handlers, how images are downloaded, compared, and forwarded to admins.

# Running & Debugging (concrete commands)
- Start dependencies (Postgres + pgAdmin):
```bash
docker-compose up -d
```
- Local dev (recommended):
```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
python main.py
```
- Notes: `docker-compose.yml` reads a `.env` file for DB credentials used both by compose and by `environs` in Python. Ensure `.env` defines the expected keys.

# Project-specific gotchas and observable behaviors
- Image storage & table schema: `images` table has the columns `(user_id, user_name, image_name, upload_date, image_hash, image_type, image_location)` — handlers rely on `image_name` sometimes being a Telegram `file_id` and sometimes a local file path.
- `AlbumMiddleware` batches media-group photos by `media_group_id` and injects `data['album']` into handlers. Tests/changes to album handling should preserve sorting by `message_id`.
- `image/vectorize.py` uses `dlib` for face detection — platform-native build deps are required for `dlib` to install successfully (this appears in `requirements.txt`).
- `main.py` sets an explicit event loop factory on Windows (SelectorEventLoop via `selectors.SelectSelector`) — preserve this when changing startup behavior on Windows.

# What to change carefully (areas an agent might update)
- When modifying DB connection handling, prefer using `get_pg_pool(...)` and preserve `log_db_version` usage: other code expects the pool to already be open.
- If changing env parsing in `config/config.py`, keep the same env variable names or update references in `docker-compose.yml` and `database/image.py` where `Env()` is used directly.

# Quick Examples (copy-paste safe)
- Find similar image (used in `handlers/users.py`):
```py
similar = await find_similar_images(db_pool, buffer)  # buffer is BytesIO()
```
- Append image record (compute hash if `ImgHash` absent):
```py
await append_image_record(db_pool, image_record, ImgHash=None, filePath=buffer)
```

# If you need more context
- Look at `requirements.txt` to confirm dependency versions (dlib, aiogram, psycopg). Use `docker-compose.yml` to reproduce the DB environment.

---
Please review this guidance — tell me if you'd like more examples, stricter rules (formatting, typing), or automated checks to add. I'll iterate on any unclear or missing sections.
