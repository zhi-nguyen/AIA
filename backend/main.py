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
                            msg_type = data.get("type", "")
                            if user_id:
                                if msg_type == "agent_command":
                                    # Lệnh dành cho Agent cục bộ (tạo Excel, Word, ...)
                                    await manager.send_to_agent(user_id, data)
                                else:
                                    # Gửi cho Web client
                                    success = await manager.send_to_web(user_id, data)
                                    if not success and msg_type in ["NEW_PROPOSAL", "WEATHER_ALERT", "NOTIFICATION"]:
                                        # Người dùng offline -> Cho vào hàng đợi (Offline Queue)
                                        # Đính kèm thời gian tạo để AI có cơ sở đánh giá quá hạn sau này
                                        from datetime import datetime
                                        data["created_timestamp"] = datetime.now().isoformat()
                                        await client.lpush(f"offline_queue:{user_id}", json.dumps(data, ensure_ascii=False))
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
        SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "openid", "https://www.googleapis.com/auth/userinfo.email"]
        from config import get_base_path
        creds_path = os.path.join(get_base_path(), 'credentials.json')
        
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
        
        from services.db_service import link_google_account, add_user_account, get_user_accounts
        real_user_id = await link_google_account(user_id, google_id, email, enc_access, enc_refresh)
        
        # Lưu vào bảng user_accounts (multi-email)
        existing_accounts = await get_user_accounts(real_user_id)
        is_primary = len(existing_accounts) == 0  # Account đầu tiên là primary
        await add_user_account(real_user_id, google_id, email, enc_access, enc_refresh, is_primary)
            
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
        from fastapi.responses import HTMLResponse
        return HTMLResponse("""
        <html><body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f8fafc">
        <div style="text-align:center"><h1 style="color:#ef4444">❌ Đăng nhập thất bại</h1><p>Vui lòng thử lại.</p></div>
        </body></html>""", status_code=200)
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(f"""
    <html>
    <head><title>Đăng nhập thành công</title></head>
    <body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:linear-gradient(135deg,#f8fafc,#e0e7ff)">
      <div style="text-align:center;background:white;padding:48px 64px;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,0.08)">
        <div style="font-size:64px;margin-bottom:16px">✅</div>
        <h1 style="color:#1e1e2d;margin:0 0 8px">Đăng nhập thành công!</h1>
        <p style="color:#6366f1;font-weight:600;font-size:18px;margin:0 0 8px">{email}</p>
        <p style="color:#64748b;margin:0 0 24px">Tài khoản đã được liên kết. Bạn có thể đóng tab này.</p>
        <button onclick="window.close()" style="background:#6366f1;color:white;border:none;padding:14px 32px;border-radius:14px;font-size:15px;font-weight:700;cursor:pointer">
          Đóng tab & Quay lại ứng dụng
        </button>
        <p style="color:#94a3b8;font-size:12px;margin-top:16px">Tab sẽ tự đóng sau 5 giây...</p>
      </div>
      <script>setTimeout(()=>window.close(), 5000);</script>
    </body>
    </html>
    """, status_code=200)

# === Import routes (sẽ mở rộng dần) ===
from api.routes import router as api_router
from api.websocket import router as ws_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    import socket
    
    def find_free_port(start_port=8000, max_port=8020):
        for port in range(start_port, max_port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) != 0:
                    return port
        return start_port
        
    port = find_free_port(8000, 8020)
    print("===========================================================")
    print(f"[AIA Backend] Starting Server at http://127.0.0.1:{port}")
    print("===========================================================")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
