"""
db_service.py - Quản lý CSDL cho Authentication và Mail Service
Sử dụng asyncpg để thao tác với users, sessions, processed_emails và pending_events.
"""

import asyncpg
from config import get_settings
from datetime import datetime, timedelta
import uuid
import json

_pool = None

async def get_db_pool():
    global _pool
    if _pool is None:
        settings = get_settings()
        db_url = settings.database_url
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        _pool = await asyncpg.create_pool(db_url)
        await init_db_tables(_pool)
    return _pool

async def init_db_tables(pool: asyncpg.Pool):
    """Tạo tất cả bảng nếu chưa có: users, sessions, processed_emails, pending_events."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                role VARCHAR(50) NOT NULL DEFAULT 'guest',
                google_id VARCHAR(255) UNIQUE,
                email VARCHAR(255),
                encrypted_access_token TEXT,
                encrypted_refresh_token TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR(255) PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Bảng lưu gmail_id đã xử lý — dùng cho Bộ lọc Tier 1 (deduplication)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                user_id  UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                gmail_id VARCHAR(255) NOT NULL,
                PRIMARY KEY (user_id, gmail_id)
            );
        """)

        # Bảng lưu các cuộc hẹn đang chờ xác nhận từ người dùng
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_events (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title         TEXT NOT NULL,
                participants  TEXT[],
                proposed_time TIMESTAMP WITH TIME ZONE,
                status        VARCHAR(50) NOT NULL DEFAULT 'pending',
                note          TEXT,
                weather_dependent BOOLEAN DEFAULT FALSE,
                created_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Add columns if they do not exist (for smooth migration)
        # Note: postgresql 9.6+ supports IF NOT EXISTS for ADD COLUMN
        await conn.execute("""
            ALTER TABLE pending_events 
            ADD COLUMN IF NOT EXISTS note TEXT,
            ADD COLUMN IF NOT EXISTS weather_dependent BOOLEAN DEFAULT FALSE;
        """)

        # Bảng lưu các đề xuất email đang chờ người dùng phản hồi
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_proposals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                gmail_id VARCHAR(255),
                payload JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)


async def create_guest_user() -> str:
    """Tạo guest user và trả về UUID."""
    pool = await get_db_pool()
    user_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (id, role) VALUES ($1::uuid, 'guest')",
            user_id
        )
    return user_id

async def create_session(user_id: str) -> str:
    """Tạo session ID mới cho user, valid trong 30 ngày."""
    pool = await get_db_pool()
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at) VALUES ($1, $2::uuid, $3)",
            session_id, user_id, expires_at
        )
    return session_id

async def get_user_from_session(session_id: str) -> str:
    """Lấy user_id từ session_id nếu session còn hợp lệ."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT user_id, expires_at 
            FROM sessions 
            WHERE session_id = $1
        """, session_id)
        
        if row and row['expires_at'] > datetime.utcnow().astimezone(row['expires_at'].tzinfo):
            return str(row['user_id'])
    return None

async def get_user_info(user_id: str) -> dict:
    """Lấy thông tin role và email của user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT role, email FROM users WHERE id = $1::uuid", user_id)
        return dict(row) if row else None

async def link_google_account(user_id: str, google_id: str, email: str, encrypted_access: str, encrypted_refresh: str):
    """Nâng cấp guest lên member và lưu Google credentials."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users 
            SET role = 'member', 
                google_id = $1, 
                email = $2, 
                encrypted_access_token = $3, 
                encrypted_refresh_token = $4 
            WHERE id = $5::uuid
        """, google_id, email, encrypted_access, encrypted_refresh, user_id)

async def get_google_credentials(user_id: str) -> dict:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT encrypted_access_token, encrypted_refresh_token FROM users WHERE id = $1::uuid",
            user_id
        )
        return dict(row) if row else None

async def update_google_credentials(user_id: str, encrypted_access: str, encrypted_refresh: str):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET encrypted_access_token = $1, encrypted_refresh_token = $2 WHERE id = $3::uuid",
            encrypted_access, encrypted_refresh, user_id
        )


# ---------------------------------------------------------------------------
# processed_emails helpers — Bộ lọc Tier 1
# ---------------------------------------------------------------------------

async def add_processed_email(user_id: str, gmail_id: str) -> None:
    """Đánh dấu một gmail_id là đã xử lý cho user này."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO processed_emails (user_id, gmail_id)
            VALUES ($1::uuid, $2)
            ON CONFLICT DO NOTHING
            """,
            user_id, gmail_id,
        )


async def is_email_processed(user_id: str, gmail_id: str) -> bool:
    """Kiểm tra xem gmail_id đã được xử lý chưa (Tier 1 filter)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM processed_emails WHERE user_id = $1::uuid AND gmail_id = $2",
            user_id, gmail_id,
        )
        return row is not None


async def get_processed_email_ids(user_id: str) -> set[str]:
    """Trả về tập hợp tất cả gmail_id đã xử lý của user (một lần truy vấn cho Tier 1)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT gmail_id FROM processed_emails WHERE user_id = $1::uuid",
            user_id,
        )
        return {row["gmail_id"] for row in rows}


# ---------------------------------------------------------------------------
# pending_events helpers — Hàng đợi cuộc hẹn
# ---------------------------------------------------------------------------

async def create_pending_event(
    user_id: str,
    title: str,
    participants: list[str],
    proposed_time: datetime | None = None,
    status: str = "pending",
    note: str | None = None,
    weather_dependent: bool = False,
) -> str:
    """Tạo một pending event và trả về UUID của nó."""
    pool = await get_db_pool()
    event_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pending_events (id, user_id, title, participants, proposed_time, status, note, weather_dependent)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8)
            """,
            event_id, user_id, title, participants, proposed_time, status, note, weather_dependent
        )
    return event_id

async def get_user_events(user_id: str) -> list[dict]:
    """Lấy danh sách các cuộc hẹn của user (status = 'confirmed' hoặc 'pending')."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, participants, proposed_time, status, note, weather_dependent, created_at 
            FROM pending_events 
            WHERE user_id = $1::uuid 
            ORDER BY proposed_time ASC NULLS LAST
            """,
            user_id
        )
        return [dict(row) for row in rows]


async def update_event_status(event_id: str, status: str) -> None:
    """Cập nhật trạng thái của một pending event (vd: 'confirmed', 'cancelled')."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE pending_events SET status = $1 WHERE id = $2::uuid",
            status, event_id,
        )

# ---------------------------------------------------------------------------
# pending_proposals helpers — Đề xuất AI Thư Ký
# ---------------------------------------------------------------------------

async def create_pending_proposal(user_id: str, gmail_id: str, payload: dict) -> str:
    """Tạo pending proposal mới và trả về UUID ID."""
    pool = await get_db_pool()
    proposal_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO pending_proposals (id, user_id, gmail_id, payload)
            VALUES ($1::uuid, $2::uuid, $3, $4::jsonb)
            """,
            proposal_id, user_id, gmail_id, json.dumps(payload, ensure_ascii=False),
        )
    return proposal_id

async def get_pending_proposals(user_id: str) -> list[dict]:
    """Lấy danh sách các proposal đang chờ của user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, payload FROM pending_proposals WHERE user_id = $1::uuid ORDER BY created_at ASC",
            user_id,
        )
        return [{"id": str(r["id"]), "payload": json.loads(r["payload"])} for r in rows]

async def delete_pending_proposal(proposal_id: str, user_id: str) -> bool:
    """Xóa một proposal đang chờ (sau khi user đã phản hồi hoặc bỏ qua)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM pending_proposals WHERE id = $1::uuid AND user_id = $2::uuid",
            proposal_id, user_id,
        )
        return "1" in result # 'DELETE 1'



# ---------------------------------------------------------------------------
# User enumeration helper — dùng cho Celery batch task
# ---------------------------------------------------------------------------

async def get_all_authorized_users() -> list[str]:
    """
    Trả về danh sách user_id đã lưu Gmail refresh token (đã cấp phép).
    Dùng bởi gmail_watch để đăng ký watch cho tất cả users khi khởi động.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT id::text
            FROM users
            WHERE encrypted_refresh_token IS NOT NULL
            """
        )
        return [str(row["id"]) for row in rows]


async def get_user_id_by_email(email: str) -> str | None:
    """
    Tìm user_id theo địa chỉ email Google đã link.
    Dùng bởi Gmail Watch listener để xác định notification thuộc user nào.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id::text FROM users WHERE email = $1",
            email,
        )
        return row["id"] if row else None

