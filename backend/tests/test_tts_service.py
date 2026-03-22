# backend/tests/test_tts_service.py
"""
Unit tests cho TTS Service.
Kiểm tra chất lượng input (markdown stripping, xử lý edge cases)
và output (format WAV, kích thước, cấu hình voice).
Sử dụng mock để không gọi API thực.
"""

import struct
import io
import wave
import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# INPUT QUALITY TESTS
# ============================================================

class TestMarkdownStripping:
    """Kiểm tra việc loại bỏ markdown trước khi gửi TTS."""

    def test_strip_headers(self):
        from services.tts_service import _strip_markdown
        assert _strip_markdown("# Tiêu đề") == "Tiêu đề"
        assert _strip_markdown("## Tiêu đề con") == "Tiêu đề con"
        assert _strip_markdown("### Heading 3") == "Heading 3"

    def test_strip_bold_italic(self):
        from services.tts_service import _strip_markdown
        assert _strip_markdown("**đậm**") == "đậm"
        assert _strip_markdown("*nghiêng*") == "nghiêng"
        assert _strip_markdown("***cả hai***") == "cả hai"

    def test_strip_inline_code(self):
        from services.tts_service import _strip_markdown
        assert _strip_markdown("dùng `print()` để in") == "dùng print() để in"

    def test_strip_code_blocks(self):
        from services.tts_service import _strip_markdown
        text = "Trước\n```python\nprint('hello')\n```\nSau"
        result = _strip_markdown(text)
        assert "```" not in result
        assert "Trước" in result
        assert "Sau" in result

    def test_strip_links(self):
        from services.tts_service import _strip_markdown
        assert _strip_markdown("[Google](https://google.com)") == "Google"

    def test_strip_images(self):
        from services.tts_service import _strip_markdown
        result = _strip_markdown("![ảnh](https://img.com/a.png)")
        assert "![" not in result
        assert "https://" not in result

    def test_strip_list_markers(self):
        from services.tts_service import _strip_markdown
        text = "- Mục 1\n- Mục 2\n* Mục 3"
        result = _strip_markdown(text)
        assert "Mục 1" in result
        assert "- " not in result
        assert "* " not in result

    def test_strip_ordered_list(self):
        from services.tts_service import _strip_markdown
        text = "1. Bước một\n2. Bước hai"
        result = _strip_markdown(text)
        assert "Bước một" in result
        assert "1. " not in result

    def test_strip_blockquotes(self):
        from services.tts_service import _strip_markdown
        assert _strip_markdown("> Trích dẫn") == "Trích dẫn"

    def test_strip_horizontal_rules(self):
        from services.tts_service import _strip_markdown
        result = _strip_markdown("Trước\n---\nSau")
        assert "---" not in result
        assert "Trước" in result

    def test_plain_text_unchanged(self):
        from services.tts_service import _strip_markdown
        text = "Xin chào, tôi là AIA. Hôm nay trời đẹp quá!"
        assert _strip_markdown(text) == text

    def test_vietnamese_diacritics_preserved(self):
        from services.tts_service import _strip_markdown
        text = "Việt Nam có nhiều **danh lam** thắng cảnh đẹp"
        result = _strip_markdown(text)
        assert "Việt Nam" in result
        assert "danh lam" in result
        assert "**" not in result


class TestInputEdgeCases:
    """Kiểm tra xử lý các trường hợp đặc biệt của input."""

    def test_empty_text_returns_valid_wav(self):
        from services.tts_service import _strip_markdown, _create_silent_wav
        assert _strip_markdown("") == ""
        assert _strip_markdown("   ") == ""
        # Silent WAV should still be valid
        wav_bytes = _create_silent_wav()
        assert wav_bytes[:4] == b"RIFF"

    def test_whitespace_only_returns_valid_wav(self):
        from services.tts_service import _strip_markdown, _create_silent_wav
        assert _strip_markdown("  \n\n  \t  ") == ""
        wav_bytes = _create_silent_wav()
        assert len(wav_bytes) > 44  # WAV header is 44 bytes

    def test_long_text_handling(self):
        """Text quá dài (>5000 chars) phải được cắt bớt."""
        from services.tts_service import _strip_markdown
        long_text = "A" * 6000
        clean = _strip_markdown(long_text)
        # _strip_markdown không cắt, nhưng synthesize_speech sẽ cắt ở 5000
        assert len(clean) == 6000  # strip chỉ format, không cắt

    def test_special_characters(self):
        from services.tts_service import _strip_markdown
        text = "Giá: 100.000đ — nhỏ hơn $50 & €45"
        result = _strip_markdown(text)
        assert "100.000đ" in result
        assert "$50" in result

    def test_mixed_content(self):
        from services.tts_service import _strip_markdown
        text = """# Báo cáo
**Doanh thu**: 100 triệu
- Sản phẩm A: *tốt*
- Sản phẩm B: `bình thường`
> Kết luận: Cần cải thiện"""
        result = _strip_markdown(text)
        assert "#" not in result
        assert "**" not in result
        assert "*" not in result.replace("Cần", "")  # avoid false positive
        assert "`" not in result
        assert ">" not in result
        assert "Báo cáo" in result
        assert "Doanh thu" in result


# ============================================================
# OUTPUT QUALITY TESTS
# ============================================================

class TestTTSOutput:
    """Kiểm tra chất lượng output từ TTS service."""

    def _create_mock_audio_data(self, num_samples: int = 24000) -> bytes:
        """Tạo dữ liệu PCM giả lập cho test."""
        return struct.pack(f"<{num_samples}h", *([1000] * num_samples))

    @patch("services.tts_service.genai")
    def test_audio_output_is_wav(self, mock_genai):
        """Output phải là file WAV hợp lệ (bắt đầu bằng RIFF header)."""
        # Mock response
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.inline_data.data = self._create_mock_audio_data()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        from services.tts_service import synthesize_speech
        result = synthesize_speech("Xin chào Việt Nam")

        # Verify WAV format
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WAVE"

    @patch("services.tts_service.genai")
    def test_audio_minimum_length(self, mock_genai):
        """Output cho text không rỗng phải có kích thước tối thiểu (>1KB)."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.inline_data.data = self._create_mock_audio_data(48000)  # 2 seconds
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        from services.tts_service import synthesize_speech
        result = synthesize_speech("Hôm nay thời tiết rất đẹp")

        assert len(result) > 1024  # > 1KB

    @patch("services.tts_service.genai")
    def test_wav_is_parseable(self, mock_genai):
        """Output WAV phải parse được bằng wave module."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.inline_data.data = self._create_mock_audio_data()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        from services.tts_service import synthesize_speech
        result = synthesize_speech("Test")

        # Parse WAV
        buffer = io.BytesIO(result)
        with wave.open(buffer, "rb") as wf:
            assert wf.getnchannels() == 1  # Mono
            assert wf.getsampwidth() == 2  # 16-bit
            assert wf.getframerate() == 24000  # 24kHz

    @patch("services.tts_service.genai")
    def test_voice_config_applied(self, mock_genai):
        """Kiểm tra voice name (Leda) và config đúng trong API call."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.inline_data.data = self._create_mock_audio_data()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        from services.tts_service import synthesize_speech
        synthesize_speech("Test voice config")

        # Verify API was called with correct config
        call_args = mock_client.models.generate_content.call_args
        config = call_args.kwargs.get("config") or call_args[1].get("config")

        assert config is not None
        assert config.response_modalities == ["AUDIO"]
        voice_name = config.speech_config.voice_config.prebuilt_voice_config.voice_name
        assert voice_name == "Leda"

    def test_silent_wav_for_empty_input(self):
        """Text rỗng phải trả về WAV im lặng, không gọi API."""
        from services.tts_service import synthesize_speech

        # Không cần mock vì text rỗng sẽ không gọi API
        result = synthesize_speech("")
        assert result[:4] == b"RIFF"
        assert len(result) > 44  # Có data

    @patch("services.tts_service.genai")
    def test_text_truncation_at_5000_chars(self, mock_genai):
        """Text >5000 ký tự phải bị cắt trước khi gửi API."""
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client

        mock_part = MagicMock()
        mock_part.inline_data.data = self._create_mock_audio_data()
        mock_candidate = MagicMock()
        mock_candidate.content.parts = [mock_part]
        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        from services.tts_service import synthesize_speech
        long_text = "A" * 6000
        synthesize_speech(long_text)

        # Verify truncated text was sent
        call_args = mock_client.models.generate_content.call_args
        sent_text = call_args.kwargs.get("contents") or call_args[1].get("contents")
        assert len(sent_text) <= 5003  # 5000 + "..."
