"""
gemini_client.py - Wrapper cho Google Gemini API
Sử dụng google-genai SDK mới (thay thế google-generativeai)
Hỗ trợ cả Gemini 1.5 Pro (suy luận sâu) và Gemini 1.5 Flash (xử lý nhanh)
"""

from google import genai
from google.genai import types
from typing import Optional
from config import get_settings


class GeminiClient:
    """
    Client wrapper cho Google Gemini API (google-genai SDK).
    
    - generate_pro(): Dùng Gemini 1.5 Pro cho tác vụ phức tạp (routing, tóm tắt sâu)
    - generate_flash(): Dùng Gemini 1.5 Flash cho tác vụ nhanh (trích xuất, phân tích)
    - stream_pro(): Streaming response từ Gemini Pro
    """

    def __init__(self):
        self.settings = get_settings()
        self._client = genai.Client(
            vertexai=True,
            project=self.settings.vertex_project_id,
            location=self.settings.vertex_location
        )

    def generate_pro(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Gọi Gemini 1.5 Pro cho tác vụ phức tạp.
        Dùng cho: Router Agent, tóm tắt email phức tạp, suy luận sâu.
        """
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=4096,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        response = self._client.models.generate_content(
            model=self.settings.gemini_pro_model,
            contents=prompt,
            config=config,
        )
        return response.text

    def generate_flash(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Gọi Gemini 1.5 Flash cho tác vụ nhanh.
        Dùng cho: Trích xuất dữ liệu, thu thập tin tức, phân tích yêu cầu.
        """
        config = types.GenerateContentConfig(
            temperature=0.3,
            top_p=0.9,
            max_output_tokens=2048,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        response = self._client.models.generate_content(
            model=self.settings.gemini_flash_model,
            contents=prompt,
            config=config,
        )
        return response.text

    def stream_pro(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ):
        """
        Streaming response từ Gemini Pro.
        Trả về generator để gửi từng chunk qua WebSocket.
        """
        config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            max_output_tokens=4096,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        for chunk in self._client.models.generate_content_stream(
            model=self.settings.gemini_pro_model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text

    def stream_flash(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ):
        """
        Streaming response từ Gemini Flash.
        """
        config = types.GenerateContentConfig(
            temperature=0.3,
            top_p=0.9,
            max_output_tokens=2048,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        for chunk in self._client.models.generate_content_stream(
            model=self.settings.gemini_flash_model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text


# === Singleton instance ===
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Lấy singleton GeminiClient instance"""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
