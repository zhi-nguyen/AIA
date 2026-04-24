"""
reset_database.py — Xoá sạch và tạo lại toàn bộ database AIA từ đầu.

Cách chạy (từ trong container backend):
    docker compose exec backend python reset_database.py

Hoặc từ host (nếu port 5433 expose):
    DATABASE_URL=postgresql://aia_user:aia_secret_2024@localhost:5433/aia_db python backend/reset_database.py

Script sẽ:
  1. DROP CASCADE toàn bộ bảng hiện có (đúng thứ tự FK)
  2. DROP bảng vector store (LlamaIndex pgvector)
  3. Tạo lại toàn bộ schema sạch từ đầu (không ALTER, không migration)
  4. Flush Redis cache
"""

import asyncio
import asyncpg
import os
import sys

# ── Config ─────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://aia_user:aia_secret_2024@postgres:5432/aia_db"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# Chuẩn hoá URL cho asyncpg
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


# ── Schema: Định nghĩa duy nhất, chuẩn, không migration ──────────────────────
SCHEMA_SQL = """
-- ==============================
-- 1. USERS & AUTH
-- ==============================
CREATE TABLE users (
    id UUID PRIMARY KEY,
    role VARCHAR(50) NOT NULL DEFAULT 'guest',
    google_id VARCHAR(255) UNIQUE,
    email VARCHAR(255),
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    address TEXT,
    address_lat DOUBLE PRECISION,
    address_lon DOUBLE PRECISION,
    address_province TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    google_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    encrypted_access_token TEXT,
    encrypted_refresh_token TEXT,
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, google_id)
);

-- ==============================
-- 2. EMAIL PROCESSING
-- ==============================
CREATE TABLE processed_emails (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gmail_id VARCHAR(255) NOT NULL,
    PRIMARY KEY (user_id, gmail_id)
);

-- ==============================
-- 3. PROPOSALS & EVENTS
-- ==============================
CREATE TABLE pending_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    participants TEXT[],
    proposed_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    note TEXT,
    weather_dependent BOOLEAN DEFAULT FALSE,
    weather_alerted BOOLEAN DEFAULT FALSE,
    weather_task_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pending_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gmail_id VARCHAR(255),
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================
-- 4. WEATHER
-- ==============================
CREATE TABLE weather_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    data JSONB NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================
-- 5. TOKEN USAGE
-- ==============================
CREATE TABLE token_usage (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period VARCHAR(7) NOT NULL,
    tokens_in BIGINT DEFAULT 0,
    tokens_out BIGINT DEFAULT 0,
    PRIMARY KEY (user_id, period)
);

-- ==============================
-- 6. CHAT HISTORY
-- ==============================
CREATE TABLE chat_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    is_temporary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""


async def reset_database():
    print("=" * 60)
    print("  AIA DATABASE RESET")
    print("=" * 60)
    print(f"  Target: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print()

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # ── Bước 1: DROP toàn bộ bảng ─────────────────────────────────────
        print("[1/4] Dropping all tables...")

        # Lấy danh sách bảng hiện có
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        table_names = [r["tablename"] for r in tables]

        if table_names:
            # DROP CASCADE hết — không cần lo thứ tự FK
            drop_sql = ", ".join(f'"{t}"' for t in table_names)
            await conn.execute(f"DROP TABLE IF EXISTS {drop_sql} CASCADE")
            print(f"       Dropped {len(table_names)} tables: {', '.join(table_names)}")
        else:
            print("       No tables found.")

        # ── Bước 2: Recreate schema sạch ────────────────────────────────────
        print("[2/4] Creating fresh schema...")
        await conn.execute(SCHEMA_SQL)
        
        # Verify
        new_tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        print(f"       Created {len(new_tables)} tables: {', '.join(r['tablename'] for r in new_tables)}")

        # ── Bước 3: Đảm bảo extension pgvector ──────────────────────────────
        print("[3/4] Ensuring pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("       pgvector extension ready.")

        # ── Bước 4: Flush Redis ──────────────────────────────────────────────
        print("[4/4] Flushing Redis cache...")
        try:
            import redis
            r = redis.from_url(REDIS_URL)
            r.flushdb()
            print("       Redis FLUSHDB done.")
        except ImportError:
            print("       [SKIP] redis package not available, skip Redis flush.")
        except Exception as e:
            print(f"       [WARN] Redis flush error: {e}")

    finally:
        await conn.close()

    print()
    print("=" * 60)
    print("  ✅ DATABASE RESET COMPLETE")
    print("  Restart backend + celery-worker to reinitialize.")
    print("=" * 60)


if __name__ == "__main__":
    # Xác nhận trước khi xoá
    if "--yes" not in sys.argv:
        answer = input("\n⚠️  CẢNH BÁO: Thao tác này sẽ XOÁ TOÀN BỘ dữ liệu!\n   Gõ 'yes' để tiếp tục: ")
        if answer.strip().lower() != "yes":
            print("Đã huỷ.")
            sys.exit(0)

    asyncio.run(reset_database())
