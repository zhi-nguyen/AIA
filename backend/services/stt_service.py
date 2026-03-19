# backend/services/stt_service.py
"""
stt_service.py - Speech-to-Text Service
Sử dụng Google Cloud Speech-to-Text v2 cho tiếng Việt (vi-VN)
"""

from typing import Optional
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from config import get_settings


# Danh sách các MIME types hỗ trợ
_SUPPORTED_MIME_TYPES: list[str] = [
    "audio/webm",
    "audio/webm;codecs=opus",
    "audio/ogg",
    "audio/ogg;codecs=opus",
    "audio/wav",
    "audio/x-wav",
    "audio/mp3",
    "audio/mpeg",
]


def get_supported_mime_types() -> list[str]:
    """Trả về danh sách các MIME types được hỗ trợ."""
    return list(_SUPPORTED_MIME_TYPES)


def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/webm",
    language: Optional[str] = None,
) -> str:
    """
    Chuyển đổi audio thành text sử dụng Google Cloud Speech-to-Text v2.

    Args:
        audio_bytes: Dữ liệu audio dạng bytes
        mime_type: MIME type của audio (mặc định: audio/webm)
        language: Mã ngôn ngữ (mặc định: vi-VN)

    Returns:
        str: Văn bản được nhận dạng, hoặc chuỗi rỗng nếu thất bại
    """
    settings = get_settings()
    language = language or settings.stt_language

    # Kiểm tra input rỗng
    if not audio_bytes or len(audio_bytes) < 100:
        print("[STT] Audio data quá ngắn hoặc rỗng")
        return ""

    try:
        # Khởi tạo Speech client
        client = SpeechClient()

        # Cấu hình recognition — dùng auto_decoding_config để tự detect format
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[language],
            model="long",
        )

        # Tạo request
        request = cloud_speech.RecognizeRequest(
            recognizer=f"projects/{settings.vertex_project_id}/locations/global/recognizers/_",
            config=config,
            content=audio_bytes,
        )

        # Gọi API
        response = client.recognize(request=request)

        # Trích xuất text từ kết quả
        transcript_parts: list[str] = []
        for result in response.results:
            if result.alternatives:
                transcript_parts.append(result.alternatives[0].transcript)

        transcript = " ".join(transcript_parts).strip()
        print(f"[STT] Nhận dạng thành công: {transcript[:100]}...")
        return transcript

    except Exception as e:
        print(f"[STT] Lỗi nhận dạng: {e}")
        return ""
