# backend/services/tts_service.py
"""
tts_service.py - Text-to-Speech Service
Sử dụng Gemini TTS (gemini-2-5-flash-tts) với giọng Leda (Female, Vietnamese)
"""

import re
import io
import wave
import struct
from typing import Optional
from google import genai
from google.genai import types
from config import get_settings


def _strip_markdown(text: str) -> str:
    """
    Loại bỏ markdown formatting khỏi text trước khi synthesis.
    Giữ lại nội dung thuần túy để TTS đọc tự nhiên.
    """
    if not text:
        return ""

    # Loại bỏ headers (# ## ###)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Loại bỏ bold/italic (**bold**, *italic*, __bold__, _italic_)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", text)
    # Loại bỏ inline code (`code`)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    # Loại bỏ code blocks (```...```)
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Loại bỏ links [text](url) → giữ lại text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Loại bỏ images ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", "", text)
    # Loại bỏ horizontal rules (---, ***)
    text = re.sub(r"^[\-\*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Loại bỏ list markers (- item, * item, 1. item)
    text = re.sub(r"^\s*[\-\*\+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Loại bỏ blockquote markers (>)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    # Collapse multiple whitespace/newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _create_silent_wav(duration_ms: int = 100) -> bytes:
    """Tạo file WAV im lặng (dùng cho trường hợp text rỗng)."""
    sample_rate = 24000
    num_samples = int(sample_rate * duration_ms / 1000)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{num_samples}h", *([0] * num_samples)))
    return buffer.getvalue()


def synthesize_speech(text: str, voice: Optional[str] = None, language: Optional[str] = None) -> bytes:
    """
    Chuyển đổi text thành audio (WAV bytes) sử dụng Gemini TTS.

    Args:
        text: Văn bản cần chuyển thành giọng nói
        voice: Tên giọng (mặc định: Leda)
        language: Mã ngôn ngữ (mặc định: vi-VN)

    Returns:
        bytes: Dữ liệu audio WAV
    """
    settings = get_settings()
    voice = voice or settings.tts_voice
    language = language or settings.tts_language

    # Xử lý text rỗng
    clean_text = _strip_markdown(text)
    if not clean_text:
        return _create_silent_wav()

    # Giới hạn độ dài text (tránh quá tải API)
    max_chars = 5000
    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars] + "..."

    # Khởi tạo Gemini client
    client = genai.Client(
        vertexai=True,
        project=settings.vertex_project_id,
        location=settings.vertex_location,
    )

    # Gọi Gemini TTS API
    response = client.models.generate_content(
        model=settings.tts_model,
        contents=clean_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice,
                    )
                )
            ),
        ),
    )

    # Trích xuất audio data từ response
    audio_data = response.candidates[0].content.parts[0].inline_data.data

    # Tạo WAV file từ raw PCM data
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(24000)  # 24kHz sample rate
        wf.writeframes(audio_data)

    return buffer.getvalue()
