"""
routes.py - REST API Endpoints
Định nghĩa các endpoint cho frontend gọi
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Response, Depends, BackgroundTasks
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


class TaskResponse(BaseModel):
    task_id: str
    status: str


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


@router.post("/chat", response_model=TaskResponse)
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    """
    Endpoint chính để giao tiếp với AI. Offloaded to Celery.
    """
    try:
        user_store = _document_store.get(user_id, {})
        doc_context = user_store.get("text", "")
        image_context = user_store.get("image_context", "")
        image_filename = user_store.get('image_filename', 'ảnh')

        from tasks import process_chat
        print(f"[API] Dispatching chat task for message: {request.message[:100]}")
        task = process_chat.delay(user_id, request.message, doc_context, image_context, image_filename)
        
        return TaskResponse(task_id=task.id, status="processing")

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

@router.post("/tts", response_model=TaskResponse)
async def text_to_speech(request: TTSRequest, user_id: str = Depends(get_current_user_id)):
    """
    Chuyển đổi text thành audio (WAV) via Celery.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text không được để trống")

    try:
        from tasks import generate_tts
        task = generate_tts.delay(user_id, request.text)
        return TaskResponse(task_id=task.id, status="processing")

    except Exception as e:
        print(f"[API] Lỗi TTS: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi TTS: {str(e)}")

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Kiểm tra trạng thái Celery task."""
    from celery.result import AsyncResult
    from celery_app import celery_app
    
    res = AsyncResult(task_id, app=celery_app)
    if res.state == 'SUCCESS':
        return {"status": "completed", "result": res.result}
    elif res.state == 'FAILURE':
        return {"status": "failed", "error": str(res.info)}
    else:
        return {"status": "processing"}


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
    
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send", "openid", "https://www.googleapis.com/auth/userinfo.email"]
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

# === Agent Client Endpoints ===

from fastapi.responses import StreamingResponse

@router.post("/agent/token")
async def provision_agent_token(user_id: str = Depends(get_current_user_id)):
    """Tạo và cấp mới token cho Local Agent"""
    import uuid
    from api.websocket import manager
    token = str(uuid.uuid4())
    manager.agent_tokens[user_id] = token
    return {"status": "ok", "token": token}

@router.get("/agent/download")
async def download_agent_script(user_id: str = Depends(get_current_user_id)) -> StreamingResponse:
    """
    Tạo và tải xuống agent bundle (ZIP) bao gồm AIA_Agent.exe và config.json cho user.
    """
    import os
    import uuid
    import io
    import json
    import zipfile
    from api.websocket import manager

    # Generate a unique token for this session
    token = str(uuid.uuid4())
    manager.agent_tokens[user_id] = token

    # Check if the compiled executable exists
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe_path = os.path.join(script_dir, "static", "AIA_Agent.exe")
    
    if not os.path.exists(exe_path):
        raise HTTPException(status_code=404, detail="AIA_Agent.exe not found on server")
        
    # Generate config.json content
    config_dict = {
        "user_id": user_id,
        "user_token": token,
        "server_url": "ws://localhost:8000/api/v1/ws/agent"
    }
    config_json = json.dumps(config_dict, indent=4)

    # Create ZIP archive in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # Write config.json
        zip_file.writestr("config.json", config_json)
        # Add the agent executable
        zip_file.write(exe_path, "AIA_Agent.exe")

    zip_buffer.seek(0)

    # Return as downloadable ZIP archive
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="AIA_Setup.zip"'
        }
    )

# === Proposal Execution Endpoint ===

class ExecuteProposalRequest(BaseModel):
    """Request body cho execute-proposal endpoint (Phase 4)"""
    subject: str
    body: str
    recipients: list[str]
    # AI Secretary fields (optional — sent when action_type == create_event / reply_email)
    event_id: Optional[str] = None          # gmail_id của email gốc
    proposed_time: Optional[str] = None     # ISO 8601 datetime (from suggested_actions payload)
    participants: Optional[list[str]] = None  # sẽ ghi vào pending_events.participants
    note: Optional[str] = None
    weather_dependent: Optional[bool] = False


@router.post("/execute-proposal")
async def execute_proposal(
    request: ExecuteProposalRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    """
    Thực thi proposal:
    1. Gửi email ngay lập tức qua Gmail API
    2. Nếu có proposed_time → BackgroundTask: lưu vào pending_events table (status='confirmed')
    """
    from tools.email_tools import send_email

    if not request.recipients:
        raise HTTPException(status_code=400, detail="Danh sách người nhận trống")

    # ── 1. Gửi email (blocking, cần biết kết quả ngay) ──────────────────────
    result = await send_email(
        user_id=user_id,
        subject=request.subject,
        body=request.body,
        recipients=request.recipients,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Lỗi gửi email"))

    new_event_id: Optional[str] = None

    # ── 2. BackgroundTask: lưu lịch hẹn vào pending_events ─────────────────
    if request.proposed_time:
        async def _save_event():
            from services.db_service import create_pending_event
            eid = await create_pending_event(
                user_id=user_id,
                title=request.subject,
                participants=list(set((request.participants or []) + request.recipients)),
                proposed_time=request.proposed_time,
                status="confirmed",
                note=request.note,
                weather_dependent=request.weather_dependent,
            )
            print(f"[ExecuteProposal] Saved pending_event id={eid} for user={user_id}")

        background_tasks.add_task(_save_event)

    return {
        "status": "success",
        "message_id": result.get("message_id"),
        "event_id": new_event_id,
    }


# === Proposal & Event Endpoints ===

@router.get("/events")
async def get_events(user_id: str = Depends(get_current_user_id)):
    """Trả về danh sách 50 kiện (appointments) gần nhất/sắp tới."""
    from services.db_service import get_user_events
    events = await get_user_events(user_id)
    # Xử lý format datetime về chuỗi ISO để qua API
    for e in events:
        if isinstance(e.get("proposed_time"), datetime):
            e["proposed_time"] = e["proposed_time"].isoformat()
        if isinstance(e.get("created_at"), datetime):
            e["created_at"] = e["created_at"].isoformat()
    return events
@router.get("/proposals")
async def get_proposals(user_id: str = Depends(get_current_user_id)):
    """Lấy danh sách các đề xuất AI thư ký (pending proposal) của user"""
    from services.db_service import get_pending_proposals
    try:
        proposals = await get_pending_proposals(user_id)
        return {"status": "ok", "proposals": proposals}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/proposals/{proposal_id}")
async def delete_proposal(proposal_id: str, user_id: str = Depends(get_current_user_id)):
    """Xóa một đề xuất sau khi xử lý (đồng ý / bỏ qua)"""
    from services.db_service import delete_pending_proposal
    try:
        success = await delete_pending_proposal(proposal_id, user_id)
        return {"status": "ok", "deleted": success}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

