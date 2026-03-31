"""
main.py - FastAPI Application Entry Point
Khởi tạo FastAPI app, CORS middleware, và health check endpoint
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings

settings = get_settings()

# Store temporary code_verifier for PKCE OAuth flow
OAUTH_STORE = {}

# === Khởi tạo FastAPI App ===
app = FastAPI(
    title="AIA - AI Trợ Lý Cá Nhân",
    description="Multi-Agent AI Personal Assistant với LangGraph + Gemini",
    version="0.1.0",
)

# === CORS Middleware (cho phép Next.js frontend gọi API) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Redis Pub/Sub Link ===
@app.on_event("startup")
async def startup_event():
    import asyncio
    import json
    import redis.asyncio as aioredis
    from celery_app import redis_url
    from api.websocket import manager

    async def listen_to_redis():
        try:
            client = aioredis.from_url(redis_url)
            pubsub = client.pubsub()
            await pubsub.subscribe("aia_ws_messages")
            print("[Backend] Đã đăng ký lắng nghe Redis channel: aia_ws_messages")
            
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            user_id = data.get("user_id")
                            if user_id:
                                # Forward message to WebSocket clients
                                await manager.send_to_web(user_id, data)
                                await manager.send_to_agent(user_id, data)
                        except Exception as e:
                            print(f"[Redis Listener Parse Error] {e}")
                except Exception as e:
                    print(f"[Redis Get Message Error] {e}")
                
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[Redis Listener Connection Error] {e}")

    asyncio.create_task(listen_to_redis())

    # ── Gmail Push: Đăng ký watch + khởi động Pub/Sub listener ──
    async def _start_gmail_watch():
        """Đợi 5s cho DB pool sẵn sàng, rồi đăng ký watch + bật listener."""
        await asyncio.sleep(5)
        try:
            from services.gmail_watch import (
                register_all_users_watch,
                start_pubsub_listener,
                _renew_watch_loop,
            )
            # Đăng ký watch cho tất cả users đã cấp phép
            await register_all_users_watch()
            # Chạy listener pull Pub/Sub messages (vô hạn)
            asyncio.create_task(start_pubsub_listener())
            # Chạy renew watch mỗi 6 ngày
            asyncio.create_task(_renew_watch_loop())
            print("[Startup] ✅ Gmail Watch + Pub/Sub listener đã khởi động")
        except Exception as e:
            print(f"[Startup] ⚠️ Không thể khởi động Gmail Watch: {e}")
            import traceback
            traceback.print_exc()

    asyncio.create_task(_start_gmail_watch())



# === Health Check ===
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AIA Backend"}


# === Auth Google Callback ===
import os
from fastapi import Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "openid", "https://www.googleapis.com/auth/userinfo.email"]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.path.join(script_dir, 'credentials.json')
        
        user_id = request.query_params.get("state")
        if not user_id:
            print("[Auth Error] Không tìm thấy session state")
            return RedirectResponse("http://localhost:3000/")
            
        # Cho phép dùng http://localhost
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        
        flow = Flow.from_client_secrets_file(
            creds_path,
            scopes=SCOPES,
            redirect_uri='http://localhost:8000/auth/callback'
        )
        
        # Fetch token bằng full URL
        authorization_response = str(request.url)
        
        # Truy xuất PKCE verifier nếu có
        code_verifier = OAUTH_STORE.pop(user_id, None)
        kwargs = {}
        if code_verifier:
            kwargs["code_verifier"] = code_verifier
            
        flow.fetch_token(authorization_response=authorization_response, **kwargs)
        
        creds = flow.credentials
        
        # Gọi Google API lấy userinfo
        from googleapiclient.discovery import build
        service = build('oauth2', 'v2', credentials=creds)
        user_info = service.userinfo().get().execute()
        email = user_info.get("email", "")
        google_id = user_info.get("id", "")
        
        from services.crypto_service import encrypt_token
        enc_access = encrypt_token(creds.token)
        enc_refresh = encrypt_token(creds.refresh_token) if creds.refresh_token else None
        
        from services.db_service import link_google_account
        real_user_id = await link_google_account(user_id, google_id, email, enc_access, enc_refresh)
            
        print(f"[Auth] Đã link Google account {email} cho user {real_user_id[:8]}…")

        # Tự động đăng ký Gmail Watch cho user
        try:
            from services.gmail_watch import register_gmail_watch
            await register_gmail_watch(real_user_id)
        except Exception as watch_err:
            print(f"[Auth] Không thể đăng ký Gmail Watch: {watch_err}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Auth Error] Lỗi khi tạo token: {e}")
        
    return RedirectResponse("http://localhost:3000/")

# === Import routes (sẽ mở rộng dần) ===
from api.routes import router as api_router
from api.websocket import router as ws_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
