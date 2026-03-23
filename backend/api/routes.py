"""
routes.py - REST API Endpoints
Định nghĩa các endpoint cho frontend gọi
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from agents.graph import get_compiled_graph
from memory.user_context import initialize_user_profile, get_user_profile
from langchain_core.messages import HumanMessage
import traceback
import io

router = APIRouter()

# In-memory document storage (per user_id)
_document_store: dict[str, dict] = {}


# === Dependencies ===

async def get_current_user_id(request: Request) -> str:
    from services.db_service import get_user_from_session
    session_id = request.cookies.get("session_id")
    if session_id:
        user_id = await get_user_from_session(session_id)
        if user_id:
            return user_id
    return "default_user"


# === Auth Sessions ===

@router.get("/auth/session")
async def get_session(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    user_id = None
    role = "guest"
    
    from services.db_service import get_user_from_session, create_guest_user, create_session, get_user_info
    
    if session_id:
        user_id = await get_user_from_session(session_id)
        if user_id:
            info = await get_user_info(user_id)
            if info:
                role = info["role"]
                
    if not user_id:
        user_id = await create_guest_user()
        session_id = await create_session(user_id)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=30 * 24 * 60 * 60,
            samesite="lax",
            path="/"
        )
    
    return {"status": "ok", "user_id": user_id, "role": role}


# === Request/Response Models ===

class ChatRequest(BaseModel):
    """Request body cho chat endpoint"""
    message: str
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    """Response body cho chat endpoint"""
    response: str
    route: Optional[str] = None
    route_reasoning: Optional[str] = None


class UserProfileRequest(BaseModel):
    """Request body cho user profile initialization"""
    name: str
    occupation: str = ""
    interests: list[str] = []
    preferred_news_sources: list[str] = []
    work_style: str = ""


class TTSRequest(BaseModel):
    """Request body cho TTS endpoint"""
    text: str


# === Chat Endpoint ===

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    """
    Endpoint chính để giao tiếp với AI.
    """
    try:
        graph = get_compiled_graph()

        # Khởi tạo state ban đầu (dùng empty string thay vì None)
        user_store = _document_store.get(user_id, {})
        doc_context = user_store.get("text", "")
        image_context = user_store.get("image_context", "")
        combined_context = doc_context
        if image_context:
            combined_context += f"\n\n[Ảnh đã upload: {user_store.get('image_filename', 'ảnh')}]\n{image_context}"

        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": user_id,
            "user_context": "",
            "route": "",
            "route_reasoning": "",
            "tool_results": "",
            "final_response": "",
            "document_context": combined_context,
            "error": "",
        }

        # Chạy graph
        print(f"[API] Invoking graph with message: {request.message[:100]}")
        result = await graph.ainvoke(initial_state)
        print(f"[API] Graph result keys: {list(result.keys())}")

        return ChatResponse(
            response=result.get("final_response", "Xin lỗi, tôi không thể xử lý yêu cầu này.") or "Xin lỗi, tôi không thể xử lý.",
            route=result.get("route") or None,
            route_reasoning=result.get("route_reasoning") or None,
        )

    except Exception as e:
        print(f"[API] Lỗi chat: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")


# === Document Upload Endpoints ===

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    """
    Upload và parse file document.
    Hỗ trợ: PDF, DOCX, DOC, CSV, XLSX, XLS.
    """
    try:
        from services.file_parser import parse_file, get_supported_extensions

        # Validate extension
        filename = file.filename or "unknown"
        ext = "." + filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        supported = get_supported_extensions()
        if ext not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Định dạng '{ext}' không hỗ trợ. Hỗ trợ: {', '.join(supported)}",
            )

        # Đọc file
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="File rỗng")

        # Parse file
        result = parse_file(filename, file_bytes)

        # Lưu vào memory store
        _document_store[user_id] = result
        print(f"[API] Document uploaded: {filename} ({result['char_count']} chars) for user {user_id}")

        return {
            "success": True,
            "filename": result["filename"],
            "format": result["format"],
            "char_count": result["char_count"],
            "truncated": result["truncated"],
            "preview": result["text"][:300] + "..." if len(result["text"]) > 300 else result["text"],
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] Lỗi upload: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý file: {str(e)}")


@router.delete("/upload")
async def clear_document(user_id: str = Depends(get_current_user_id)):
    """Xóa document đã upload cho user."""
    if user_id in _document_store:
        del _document_store[user_id]
    return {"success": True, "message": "Đã xóa tài liệu"}


@router.get("/upload/status")
async def upload_status(user_id: str = Depends(get_current_user_id)):
    """Kiểm tra trạng thái document đã upload."""
    doc = _document_store.get(user_id)
    if doc:
        return {
            "has_document": True,
            "filename": doc["filename"],
            "format": doc["format"],
            "char_count": doc["char_count"],
        }
    return {"has_document": False}


# === Image Upload Endpoint ===

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    """
    Upload ảnh và dùng Gemini Flash Vision mô tả nội dung.
    Hỗ trợ: PNG, JPG, JPEG, GIF, WEBP.
    """
    try:
        filename = file.filename or "unknown"
        ext = "." + filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Định dạng '{ext}' không hỗ trợ. Hỗ trợ: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}",
            )

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="File ảnh rỗng")

        # Dùng Gemini Flash Vision mô tả ảnh
        from llm.gemini_client import get_gemini_client
        from google.genai import types as genai_types
        import base64

        client = get_gemini_client()
        mime_type = file.content_type or f"image/{ext.lstrip('.')}"

        # Encode image to base64 for inline data
        b64_data = base64.b64encode(image_bytes).decode("utf-8")

        description = client.generate_flash(
            prompt="Mô tả chi tiết nội dung bức ảnh này bằng tiếng Việt. Bao gồm: chủ thể chính, bối cảnh, màu sắc, và bất kỳ văn bản nào có trong ảnh.",
            image_data={"mime_type": mime_type, "data": b64_data},
        )

        # Lưu image context
        if user_id not in _document_store:
            _document_store[user_id] = {
                "text": "",
                "filename": "",
                "format": "",
                "char_count": 0,
                "truncated": False,
            }
        _document_store[user_id]["image_context"] = description
        _document_store[user_id]["image_filename"] = filename

        print(f"[API] Image uploaded: {filename} for user {user_id}")

        return {
            "success": True,
            "filename": filename,
            "description": description[:500],
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Lỗi upload image: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý ảnh: {str(e)}")


# === Voice Endpoints (TTS & STT) ===

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    Chuyển đổi text thành audio (WAV).
    Sử dụng Gemini TTS với giọng Leda (Female, Vietnamese).
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text không được để trống")

    try:
        from services.tts_service import synthesize_speech

        audio_bytes = synthesize_speech(request.text)

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=tts_output.wav",
                "Content-Length": str(len(audio_bytes)),
            },
        )

    except Exception as e:
        print(f"[API] Lỗi TTS: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi TTS: {str(e)}")


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """
    Chuyển đổi audio thành text.
    Hỗ trợ: audio/webm, audio/ogg, audio/wav, audio/mp3.
    """
    try:
        from services.stt_service import transcribe_audio

        # Đọc file audio
        audio_bytes = await file.read()

        if not audio_bytes:
            raise HTTPException(status_code=400, detail="File audio rỗng")

        # Lấy MIME type
        mime_type = file.content_type or "audio/webm"

        # Nhận dạng giọng nói
        transcript = transcribe_audio(audio_bytes, mime_type=mime_type)

        return {
            "text": transcript,
            "success": bool(transcript),
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Lỗi STT: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi STT: {str(e)}")


# === User Profile Endpoints ===

@router.get("/user/profile")
async def get_profile(user_id: str = Depends(get_current_user_id)):
    """Lấy profile người dùng đã lưu từ pgvector"""
    try:
        profile = get_user_profile(user_id)
        if profile:
            return {"status": "ok", "profile": profile}
        return {
            "status": "ok",
            "profile": None,
            "message": "Chưa có profile. Hãy thiết lập thông tin cá nhân.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/profile")
async def create_user_profile(request: UserProfileRequest, user_id: str = Depends(get_current_user_id)):
    """Khởi tạo hoặc cập nhật profile người dùng"""
    try:
        success = initialize_user_profile(
            user_id=user_id,
            profile={
                "name": request.name,
                "occupation": request.occupation,
                "interests": request.interests,
                "preferred_news_sources": request.preferred_news_sources,
                "work_style": request.work_style,
            },
        )

        if success:
            return {"status": "ok", "message": f"Đã lưu profile cho {request.name}"}
        else:
            raise HTTPException(status_code=500, detail="Không thể lưu profile")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Google Auth Login ===

@router.get("/auth/google/login")
async def get_google_auth_url(user_id: str = Depends(get_current_user_id)):
    """Lấy URL đăng nhập Google OAuth."""
    import os
    from google_auth_oauthlib.flow import Flow
    from fastapi import HTTPException
    
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "openid", "https://www.googleapis.com/auth/userinfo.email"]
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    creds_path = os.path.join(script_dir, 'credentials.json')
    
    if not os.path.exists(creds_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy credentials.json")
    
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
    flow = Flow.from_client_secrets_file(
        creds_path,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/auth/callback'
    )
    
    import base64
    import hashlib
    # Generate PKCE verifier and challenge
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).decode('utf-8').rstrip('=')
    
    auth_url, _ = flow.authorization_url(
        prompt='consent', 
        state=user_id, 
        access_type='offline',
        code_challenge=code_challenge,
        code_challenge_method='S256'
    )
    
    try:
        from main import OAUTH_STORE
        OAUTH_STORE[user_id] = code_verifier
    except ImportError:
        pass
    
    return {"status": "ok", "url": auth_url}


# === Gmail Status ===

@router.get("/gmail/status")
async def gmail_status(user_id: str = Depends(get_current_user_id)):
    """Kiểm tra trạng thái Gmail API"""
    from tools.email_tools import check_gmail_configured, check_gmail_authorized
    authorized = await check_gmail_authorized(user_id)
    return {
        "configured": check_gmail_configured(),
        "authorized": authorized,
    }


# === Graph Info ===

@router.get("/graph/info")
async def graph_info():
    """Thông tin về cấu trúc graph hiện tại"""
    return {
        "nodes": ["memory_injector", "router", "email_node", "news_node", "general_node"],
        "flow": "START → memory_injector → router → [email|news|general] → END",
        "version": "Phase 5 - Voice (TTS & STT)",
    }
