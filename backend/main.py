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
        await link_google_account(user_id, google_id, email, enc_access, enc_refresh)
            
        print(f"[Auth] Đã link Google account {email} cho session member!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Auth Error] Lỗi khi tạo token: {e}")
        
    return RedirectResponse("http://localhost:3000/")

# === Import routes (sẽ mở rộng dần) ===
from api.routes import router as api_router

app.include_router(api_router, prefix="/api/v1")
