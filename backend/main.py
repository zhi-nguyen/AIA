"""
main.py - FastAPI Application Entry Point
Khởi tạo FastAPI app, CORS middleware, và health check endpoint
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings

settings = get_settings()

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


# === Import routes (sẽ mở rộng dần) ===
from api.routes import router as api_router

app.include_router(api_router, prefix="/api/v1")
