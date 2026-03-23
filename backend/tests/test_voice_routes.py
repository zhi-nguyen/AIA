# backend/tests/test_voice_routes.py
"""
Unit tests cho Voice API Endpoints (TTS & STT).
Kiểm tra các endpoint /api/v1/tts và /api/v1/stt
sử dụng FastAPI TestClient.
"""

import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _get_test_client() -> TestClient:
    """Tạo TestClient với mocking cho các module nặng."""
    # Mock các module cần database/external services trước khi import app
    with patch("agents.graph.get_compiled_graph"), \
         patch("memory.user_context.initialize_user_profile"), \
         patch("memory.user_context.get_user_profile"):
        from main import app
        return TestClient(app)


# ============================================================
# TTS ENDPOINT TESTS
# ============================================================

class TestTTSEndpoint:
    """Kiểm tra endpoint POST /api/v1/tts."""

    @patch("services.tts_service.synthesize_speech")
    def test_tts_success(self, mock_synthesize):
        """POST /tts với text hợp lệ phải trả về audio/wav."""
        # Mock TTS trả về WAV data
        mock_synthesize.return_value = b"RIFF" + b"\x00" * 100

        client = _get_test_client()
        response = client.post("/api/v1/tts", json={"text": "Xin chào"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content[:4] == b"RIFF"

    def test_tts_empty_text_returns_400(self):
        """POST /tts với text rỗng phải trả về 400."""
        client = _get_test_client()
        response = client.post("/api/v1/tts", json={"text": ""})

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_tts_whitespace_only_returns_400(self):
        """POST /tts với chỉ whitespace phải trả về 400."""
        client = _get_test_client()
        response = client.post("/api/v1/tts", json={"text": "   "})

        assert response.status_code == 400

    def test_tts_missing_text_field_returns_422(self):
        """POST /tts thiếu field 'text' phải trả về 422."""
        client = _get_test_client()
        response = client.post("/api/v1/tts", json={})

        assert response.status_code == 422

    @patch("services.tts_service.synthesize_speech")
    def test_tts_long_text_accepted(self, mock_synthesize):
        """POST /tts với text dài vẫn được chấp nhận."""
        mock_synthesize.return_value = b"RIFF" + b"\x00" * 100

        client = _get_test_client()
        long_text = "Xin chào " * 500  # ~4500 chars
        response = client.post("/api/v1/tts", json={"text": long_text})

        assert response.status_code == 200

    @patch("services.tts_service.synthesize_speech")
    def test_tts_vietnamese_chars_accepted(self, mock_synthesize):
        """POST /tts với ký tự tiếng Việt vẫn hoạt động."""
        mock_synthesize.return_value = b"RIFF" + b"\x00" * 100

        client = _get_test_client()
        response = client.post("/api/v1/tts", json={"text": "Việt Nam đất nước tươi đẹp ơi"})

        assert response.status_code == 200
        mock_synthesize.assert_called_once()


# ============================================================
# STT ENDPOINT TESTS
# ============================================================

class TestSTTEndpoint:
    """Kiểm tra endpoint POST /api/v1/stt."""

    @patch("services.stt_service.transcribe_audio")
    def test_stt_success(self, mock_transcribe):
        """POST /stt với audio file hợp lệ phải trả về text."""
        mock_transcribe.return_value = "Xin chào Việt Nam"

        client = _get_test_client()

        # Tạo fake audio file
        audio_data = b"\x00" * 1000
        response = client.post(
            "/api/v1/stt",
            files={"file": ("recording.webm", io.BytesIO(audio_data), "audio/webm")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Xin chào Việt Nam"
        assert data["success"] is True

    @patch("services.stt_service.transcribe_audio")
    def test_stt_empty_result(self, mock_transcribe):
        """POST /stt khi không nhận dạng được phải trả về success=False."""
        mock_transcribe.return_value = ""

        client = _get_test_client()

        audio_data = b"\x00" * 1000
        response = client.post(
            "/api/v1/stt",
            files={"file": ("recording.webm", io.BytesIO(audio_data), "audio/webm")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == ""
        assert data["success"] is False

    def test_stt_no_file_returns_422(self):
        """POST /stt thiếu file phải trả về 422."""
        client = _get_test_client()
        response = client.post("/api/v1/stt")

        assert response.status_code == 422

    @patch("services.stt_service.transcribe_audio")
    def test_stt_wav_file_accepted(self, mock_transcribe):
        """POST /stt với file WAV phải được chấp nhận."""
        mock_transcribe.return_value = "Test"

        client = _get_test_client()

        audio_data = b"RIFF" + b"\x00" * 1000
        response = client.post(
            "/api/v1/stt",
            files={"file": ("recording.wav", io.BytesIO(audio_data), "audio/wav")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
