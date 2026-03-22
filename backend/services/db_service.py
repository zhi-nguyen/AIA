"""
db_service.py - Quản lý CSDL cho Authentication
Sử dụng asyncpg để thao tác với users và sessions.
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
    """Tạo bảng users và sessions nếu chưa có."""
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
