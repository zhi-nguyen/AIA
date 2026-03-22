# backend/tests/test_stt_service.py
"""
Unit tests cho STT Service.
Kiểm tra chất lượng input (xử lý audio rỗng, format không hợp lệ)
và output (cấu hình language, kết quả transcription).
Sử dụng mock để không gọi API thực.
"""

import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# INPUT QUALITY TESTS
# ============================================================

class TestSTTInputValidation:
    """Kiểm tra xử lý input của STT service."""

    def test_empty_audio_returns_empty_string(self):
        """Audio bytes rỗng phải trả về chuỗi rỗng, không crash."""
        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"")
        assert result == ""

    def test_short_audio_returns_empty_string(self):
        """Audio data quá ngắn (<100 bytes) phải trả về chuỗi rỗng."""
        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"x" * 50)
        assert result == ""

    @patch("services.stt_service.SpeechClient")
    def test_invalid_audio_format_no_crash(self, mock_speech_client):
        """Dữ liệu không phải audio phải xử lý gracefully."""
        mock_client = MagicMock()
        mock_speech_client.return_value = mock_client
        # Simulate API error for invalid audio
        mock_client.recognize.side_effect = Exception("Invalid audio data")

        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"this is not audio data" * 10, mime_type="audio/webm")
        assert result == ""

    def test_supported_mime_types_list(self):
        """Danh sách MIME types hỗ trợ phải đầy đủ."""
        from services.stt_service import get_supported_mime_types
        supported = get_supported_mime_types()
        assert "audio/webm" in supported
        assert "audio/wav" in supported
        assert "audio/ogg" in supported


# ============================================================
# OUTPUT QUALITY TESTS
# ============================================================

class TestSTTOutput:
    """Kiểm tra chất lượng output từ STT service."""

    @patch("services.stt_service.SpeechClient")
    def test_transcription_returns_string(self, mock_speech_client):
        """Kết quả transcription phải là string hợp lệ."""
        mock_client = MagicMock()
        mock_speech_client.return_value = mock_client

        # Mock successful response
        mock_alternative = MagicMock()
        mock_alternative.transcript = "Xin chào Việt Nam"
        mock_result = MagicMock()
        mock_result.alternatives = [mock_alternative]
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.recognize.return_value = mock_response

        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"x" * 200, mime_type="audio/webm")

        assert isinstance(result, str)
        assert result == "Xin chào Việt Nam"

    @patch("services.stt_service.SpeechClient")
    def test_multiple_results_concatenated(self, mock_speech_client):
        """Nhiều kết quả phải được ghép nối thành một câu."""
        mock_client = MagicMock()
        mock_speech_client.return_value = mock_client

        # Mock response with multiple results
        mock_alt1 = MagicMock()
        mock_alt1.transcript = "Hôm nay"
        mock_result1 = MagicMock()
        mock_result1.alternatives = [mock_alt1]

        mock_alt2 = MagicMock()
        mock_alt2.transcript = "trời đẹp quá"
        mock_result2 = MagicMock()
        mock_result2.alternatives = [mock_alt2]

        mock_response = MagicMock()
        mock_response.results = [mock_result1, mock_result2]
        mock_client.recognize.return_value = mock_response

        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"x" * 200, mime_type="audio/webm")

        assert "Hôm nay" in result
        assert "trời đẹp quá" in result

    @patch("services.stt_service.SpeechClient")
    def test_empty_results_returns_empty(self, mock_speech_client):
        """Response không có kết quả phải trả về chuỗi rỗng."""
        mock_client = MagicMock()
        mock_speech_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = []
        mock_client.recognize.return_value = mock_response

        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"x" * 200, mime_type="audio/webm")

        assert result == ""

    @patch("services.stt_service.SpeechClient")
    def test_vietnamese_language_config(self, mock_speech_client):
        """Kiểm tra ngôn ngữ vi-VN được cấu hình trong API call."""
        mock_client = MagicMock()
        mock_speech_client.return_value = mock_client

        mock_response = MagicMock()
        mock_response.results = []
        mock_client.recognize.return_value = mock_response

        from services.stt_service import transcribe_audio
        transcribe_audio(b"x" * 200, mime_type="audio/webm")

        # Verify recognize was called
        assert mock_client.recognize.called
        call_args = mock_client.recognize.call_args
        request = call_args.kwargs.get("request") or call_args[0][0]

        # Verify language config
        assert "vi-VN" in request.config.language_codes

    @patch("services.stt_service.SpeechClient")
    def test_api_error_returns_empty(self, mock_speech_client):
        """Lỗi API phải trả về chuỗi rỗng, không raise exception."""
        mock_client = MagicMock()
        mock_speech_client.return_value = mock_client
        mock_client.recognize.side_effect = Exception("API Error")

        from services.stt_service import transcribe_audio
        result = transcribe_audio(b"x" * 200, mime_type="audio/webm")

        assert result == ""
