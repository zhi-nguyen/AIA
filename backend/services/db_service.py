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
            ADD COLUMN IF NOT EXISTS weather_dependent BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS weather_alerted BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS weather_task_id TEXT;
        """)

        # Add address + geocoding columns to users
        await conn.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS address TEXT,
            ADD COLUMN IF NOT EXISTS address_lat DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS address_lon DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS address_province TEXT;
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

        # Bảng lưu dữ liệu thời tiết từ WeatherAPI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS weather_data (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                location_name TEXT NOT NULL,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                data JSONB NOT NULL,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Bảng lưu nhiều tài khoản Google cho 1 user (multi-email)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_accounts (
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
        """)

        # Bảng lưu số liệu Token
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                period VARCHAR(7) NOT NULL,
                tokens_in BIGINT DEFAULT 0,
                tokens_out BIGINT DEFAULT 0,
                PRIMARY KEY (user_id, period)
            );
        """)

        # --- CHAT HISTORY TABLES ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id VARCHAR(255) PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE cascade,
                title VARCHAR(255),
                is_temporary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id VARCHAR(255) NOT NULL REFERENCES chat_sessions(id) ON DELETE cascade,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration: copy dữ liệu từ bảng users cũ sang user_accounts (1 lần)
        await conn.execute("""
            INSERT INTO user_accounts (user_id, google_id, email, encrypted_access_token, encrypted_refresh_token, is_primary)
            SELECT id, google_id, email, encrypted_access_token, encrypted_refresh_token, TRUE
            FROM users
            WHERE google_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM user_accounts ua WHERE ua.user_id = users.id AND ua.google_id = users.google_id
              )
        """)


# ---------------------------------------------------------------------------
# user_accounts helpers — Multi-email management
# ---------------------------------------------------------------------------

async def add_user_account(
    user_id: str, google_id: str, email: str,
    encrypted_access: str, encrypted_refresh: str | None,
    is_primary: bool = False,
) -> str:
    """Thêm một tài khoản Google vào user. Nếu đã tồn tại thì cập nhật token."""
    pool = await get_db_pool()
    account_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        # UPSERT: nếu (user_id, google_id) đã tồn tại thì cập nhật token
        await conn.execute(
            """
            INSERT INTO user_accounts (id, user_id, google_id, email, encrypted_access_token, encrypted_refresh_token, is_primary)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id, google_id) DO UPDATE
            SET encrypted_access_token = EXCLUDED.encrypted_access_token,
                encrypted_refresh_token = COALESCE(EXCLUDED.encrypted_refresh_token, user_accounts.encrypted_refresh_token),
                email = EXCLUDED.email
            """,
            account_id, user_id, google_id, email,
            encrypted_access, encrypted_refresh, is_primary,
        )
    return account_id


async def get_user_accounts(user_id: str) -> list[dict]:
    """Lấy danh sách tất cả tài khoản email đã liên kết của user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, email, is_primary, created_at
            FROM user_accounts
            WHERE user_id = $1::uuid
            ORDER BY is_primary DESC, created_at ASC
            """,
            user_id,
        )
        return [dict(r) for r in rows]


async def delete_user_account(account_id: str, user_id: str) -> bool:
    """Xoá một tài khoản email đã liên kết. Cho phép xoá bất kỳ, kể cả primary."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Kiểm tra account có tồn tại và lấy info
        row = await conn.fetchrow(
            "SELECT is_primary, email FROM user_accounts WHERE id = $1::uuid AND user_id = $2::uuid",
            account_id, user_id,
        )
        if not row:
            return False

        was_primary = row["is_primary"]

        # Xoá account
        await conn.execute(
            "DELETE FROM user_accounts WHERE id = $1::uuid AND user_id = $2::uuid",
            account_id, user_id,
        )

        # Nếu xoá primary → xoá credentials khỏi bảng users
        if was_primary:
            await conn.execute(
                """UPDATE users SET encrypted_access_token = NULL, encrypted_refresh_token = NULL,
                   google_id = NULL, email = NULL WHERE id = $1::uuid""",
                user_id,
            )
            # Nếu còn account khác → promote account cũ nhất thành primary
            next_acc = await conn.fetchrow(
                """SELECT id, email, google_id, encrypted_access_token, encrypted_refresh_token
                   FROM user_accounts WHERE user_id = $1::uuid ORDER BY created_at ASC LIMIT 1""",
                user_id,
            )
            if next_acc:
                await conn.execute(
                    "UPDATE user_accounts SET is_primary = TRUE WHERE id = $1::uuid",
                    next_acc["id"],
                )
                # Đồng bộ credentials sang bảng users
                await conn.execute(
                    """UPDATE users SET email = $1, google_id = $2,
                       encrypted_access_token = $3, encrypted_refresh_token = $4
                       WHERE id = $5::uuid""",
                    next_acc["email"], next_acc["google_id"],
                    next_acc["encrypted_access_token"], next_acc["encrypted_refresh_token"],
                    user_id,
                )

        return True


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

async def link_google_account(user_id: str, google_id: str, email: str, encrypted_access: str, encrypted_refresh: str) -> str:
    """
    Nâng cấp guest lên member và lưu Google credentials.
    Nếu google_id đã tồn tại ở user khác (re-login từ session mới),
    cập nhật token cho user cũ và trả về user_id thực tế.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Kiểm tra xem google_id đã thuộc user nào chưa
        existing = await conn.fetchrow(
            "SELECT id::text FROM users WHERE google_id = $1",
            google_id,
        )

        if existing and str(existing["id"]) != user_id:
            # Google account đã link với user khác → cập nhật token cho user đó
            real_user_id = str(existing["id"])
            await conn.execute("""
                UPDATE users 
                SET encrypted_access_token = $1, 
                    encrypted_refresh_token = $2 
                WHERE id = $3::uuid
            """, encrypted_access, encrypted_refresh, real_user_id)
            
            # Chuyển session hiện tại sang user cũ
            await conn.execute(
                "UPDATE sessions SET user_id = $1::uuid WHERE user_id = $2::uuid",
                real_user_id, user_id,
            )
            print(f"[DB] Re-linked Google {email} → existing user {real_user_id[:8]}…")
            return real_user_id
        else:
            # Lần đầu link hoặc đúng user → update bình thường
            await conn.execute("""
                UPDATE users 
                SET role = 'member', 
                    google_id = $1, 
                    email = $2, 
                    encrypted_access_token = $3, 
                    encrypted_refresh_token = $4 
                WHERE id = $5::uuid
            """, google_id, email, encrypted_access, encrypted_refresh, user_id)
            return user_id

async def get_google_credentials(user_id: str) -> dict:
    """Lấy credentials ưu tiên từ users, fallback sang user_accounts (primary)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT encrypted_access_token, encrypted_refresh_token FROM users WHERE id = $1::uuid",
            user_id
        )
        if row and row.get("encrypted_access_token"):
            return dict(row)
        
        # Fallback: lấy từ user_accounts (ưu tiên primary)
        row = await conn.fetchrow(
            """SELECT encrypted_access_token, encrypted_refresh_token 
               FROM user_accounts 
               WHERE user_id = $1::uuid 
               ORDER BY is_primary DESC, created_at ASC 
               LIMIT 1""",
            user_id
        )
        return dict(row) if row else None


async def get_credentials_for_email(email: str) -> dict | None:
    """Lấy credentials cho một email cụ thể (dùng cho multi-email gmail_watch)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Tìm trong user_accounts trước
        row = await conn.fetchrow(
            """SELECT user_id::text, encrypted_access_token, encrypted_refresh_token 
               FROM user_accounts WHERE email = $1""",
            email
        )
        if row:
            return dict(row)
        # Fallback bảng users
        row = await conn.fetchrow(
            """SELECT id::text AS user_id, encrypted_access_token, encrypted_refresh_token 
               FROM users WHERE email = $1""",
            email
        )
        return dict(row) if row else None


async def update_google_credentials(user_id: str, encrypted_access: str, encrypted_refresh: str):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET encrypted_access_token = $1, encrypted_refresh_token = $2 WHERE id = $3::uuid",
            encrypted_access, encrypted_refresh, user_id
        )
        # Đồng bộ cập nhật token cho tất cả accounts của user trong user_accounts
        await conn.execute(
            """UPDATE user_accounts SET encrypted_access_token = $1, encrypted_refresh_token = $2 
               WHERE user_id = $3::uuid AND is_primary = TRUE""",
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
            WHERE user_id = $1::uuid AND status != 'cancelled'
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

async def update_pending_event_details(
    event_id: str,
    title: str,
    participants: list[str],
    proposed_time: datetime | None,
    note: str | None,
    weather_dependent: bool
) -> None:
    """Cập nhật chi tiết nội dung sự kiện."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE pending_events 
            SET title = $1, participants = $2, proposed_time = $3, note = $4, weather_dependent = $5
            WHERE id = $6::uuid
            """,
            title, participants, proposed_time, note, weather_dependent, event_id
        )

async def delete_pending_event(event_id: str) -> None:
    """Xóa hẳn một sự kiện khỏi cơ sở dữ liệu."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM pending_events WHERE id = $1::uuid",
            event_id
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
    Tìm trong cả bảng users (primary) và user_accounts (multi-email).
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Tìm trong bảng users trước (primary email)
        row = await conn.fetchrow(
            "SELECT id::text FROM users WHERE email = $1",
            email,
        )
        if row:
            return row["id"]
        
        # Fallback: tìm trong bảng user_accounts (multi-email)
        row = await conn.fetchrow(
            "SELECT user_id::text AS id FROM user_accounts WHERE email = $1",
            email,
        )
        return row["id"] if row else None


# ---------------------------------------------------------------------------
# Address + Weather helpers
# ---------------------------------------------------------------------------

async def update_user_address(
    user_id: str,
    address: str,
    lat: float,
    lon: float,
    province: str,
) -> None:
    """Lưu địa chỉ + tọa độ (cấp tỉnh/thành phố) cho user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE users
            SET address = $1,
                address_lat = $2,
                address_lon = $3,
                address_province = $4
            WHERE id = $5::uuid
            """,
            address, lat, lon, province, user_id,
        )


async def get_user_address(user_id: str) -> dict | None:
    """Lấy thông tin địa chỉ + tọa độ của user."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT address, address_lat, address_lon, address_province FROM users WHERE id = $1::uuid",
            user_id,
        )
        if row and row["address"]:
            return dict(row)
        return None


async def get_weather_dependent_locations() -> list[dict]:
    """
    Lấy danh sách unique (lat, lon, province) của các user có lịch hẹn
    weather_dependent=true. Gộp user cùng tỉnh/thành phố để chỉ call API 1 lần.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT u.address_lat AS lat,
                            u.address_lon AS lon,
                            u.address_province AS province
            FROM pending_events pe
            JOIN users u ON u.id = pe.user_id
            WHERE pe.weather_dependent = true
              AND pe.status IN ('pending', 'confirmed')
              AND u.address_lat IS NOT NULL
              AND u.address_lon IS NOT NULL
            """
        )
        return [dict(r) for r in rows]


async def save_weather_data(
    location_name: str,
    lat: float,
    lon: float,
    data: dict,
) -> str:
    """Lưu response từ WeatherAPI vào DB."""
    pool = await get_db_pool()
    weather_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO weather_data (id, location_name, latitude, longitude, data)
            VALUES ($1::uuid, $2, $3, $4, $5::jsonb)
            """,
            weather_id, location_name, lat, lon, json.dumps(data, ensure_ascii=False),
        )
    return weather_id


async def get_latest_weather_for_user(user_id: str) -> dict | None:
    """
    Lấy dữ liệu thời tiết mới nhất cho vị trí của user.
    Match bằng address_province.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT wd.location_name, wd.latitude, wd.longitude, wd.data, wd.fetched_at
            FROM weather_data wd
            JOIN users u ON u.address_province = wd.location_name
            WHERE u.id = $1::uuid
            ORDER BY wd.fetched_at DESC
            LIMIT 1
            """,
            user_id,
        )
        if row:
            result = dict(row)
            result["data"] = json.loads(result["data"]) if isinstance(result["data"], str) else result["data"]
            return result
        return None


async def get_events_in_bad_weather_window(
    bad_hours: list[str],
    province: str,
) -> list[dict]:
    """
    Tìm events có weather_dependent=true, chưa bị cảnh báo,
    có proposed_time nằm trong các khung giờ thời tiết xấu.
    bad_hours: list of "YYYY-MM-DD HH:00" strings.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT pe.id, pe.user_id::text AS user_id, pe.title, pe.participants,
                   pe.proposed_time, pe.note, pe.weather_dependent,
                   u.email, u.address_province, u.address_lat, u.address_lon
            FROM pending_events pe
            JOIN users u ON u.id = pe.user_id
            WHERE pe.weather_dependent = true
              AND pe.status IN ('pending', 'confirmed')
              AND pe.weather_alerted = false
              AND u.address_province = $1
              AND to_char(pe.proposed_time AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM-DD HH24:00') = ANY($2::text[])
            """,
            province, bad_hours,
        )
        return [dict(r) for r in rows]


async def mark_event_weather_alerted(event_id: str, task_id: str | None = None) -> None:
    """Đánh dấu event đã gửi cảnh báo thời tiết."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if task_id:
            await conn.execute(
                "UPDATE pending_events SET weather_alerted = true, weather_task_id = $2 WHERE id = $1::uuid",
                event_id, task_id,
            )
        else:
            await conn.execute(
                "UPDATE pending_events SET weather_alerted = true WHERE id = $1::uuid",
                event_id,
            )


async def save_event_weather_task_id(event_id: str, task_id: str) -> None:
    """Lưu Celery task ID vào event để revoke khi cần."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE pending_events SET weather_task_id = $1 WHERE id = $2::uuid",
            task_id, event_id,
        )


async def get_event_by_id(event_id: str) -> dict | None:
    """Lấy thông tin 1 event theo ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT pe.id, pe.user_id::text AS user_id, pe.title, pe.participants,
                   pe.proposed_time, pe.status, pe.note, pe.weather_dependent,
                   pe.weather_alerted, pe.weather_task_id
            FROM pending_events pe
            WHERE pe.id = $1::uuid
            """,
            event_id,
        )
        return dict(row) if row else None


async def get_weather_data_for_location(province: str, max_age_hours: int = 2) -> dict | None:
    """
    Lấy weather_data mới nhất (< max_age_hours) cho 1 location.
    Trả về parsed JSON data hoặc None.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT data, fetched_at
            FROM weather_data
            WHERE location_name = $1
              AND fetched_at > NOW() - INTERVAL '1 hour' * $2
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            province, max_age_hours,
        )
        if row:
            data = row["data"]
            return json.loads(data) if isinstance(data, str) else data
        return None

async def get_token_usage(user_id: str, period: str) -> dict:
    """
    Lấy số liệu token của user trong 1 chu kỳ (YYYY-MM).
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT tokens_in, tokens_out 
            FROM token_usage
            WHERE user_id = $1::uuid AND period = $2
            """,
            user_id, period
        )
        if row:
            return {"tokens_in": row["tokens_in"], "tokens_out": row["tokens_out"]}
        return {"tokens_in": 0, "tokens_out": 0}

async def add_token_usage(user_id: str, period: str, tokens_in: int, tokens_out: int) -> None:
    """
    Cộng dồn số lượng token_in và token_out cho một User trong kỳ (YYYY-MM).
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO token_usage (user_id, period, tokens_in, tokens_out)
            VALUES ($1::uuid, $2, $3, $4)
            ON CONFLICT (user_id, period) DO UPDATE 
            SET tokens_in = token_usage.tokens_in + EXCLUDED.tokens_in,
                tokens_out = token_usage.tokens_out + EXCLUDED.tokens_out
            """,
            user_id, period, tokens_in, tokens_out
        )
