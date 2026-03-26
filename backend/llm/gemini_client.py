"""
gemini_client.py - Wrapper cho Google Gemini API
Sử dụng google-genai SDK mới (thay thế google-generativeai)
Hỗ trợ cả Gemini 1.5 Pro (suy luận sâu) và Gemini 1.5 Flash (xử lý nhanh)
"""

from google import genai
from google.genai import types
from typing import Optional
from config import get_settings

DEFAULT_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]


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
            safety_settings=DEFAULT_SAFETY_SETTINGS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        response = self._client.models.generate_content(
            model=self.settings.gemini_pro_model,
            contents=prompt,
            config=config,
        )
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            u = response.usage_metadata
            print(f"[Tokens Pro] In: {getattr(u, 'prompt_token_count', 0)} | Out: {getattr(u, 'candidates_token_count', 0)} | Total: {getattr(u, 'total_token_count', 0)}")
        return response.text

    def generate_flash(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        image_data: Optional[dict] = None,
        response_mime_type: Optional[str] = None,
    ) -> str:
        """
        Gọi Gemini 1.5 Flash cho tác vụ nhanh.
        Dùng cho: Trích xuất dữ liệu, thu thập tin tức, phân tích yêu cầu.
        Hỗ trợ Vision: truyền image_data={"mime_type": "...", "data": "<base64>"}.
        """
        config = types.GenerateContentConfig(
            temperature=0.3,
            top_p=0.9,
            max_output_tokens=8192,
            response_mime_type=response_mime_type,
            safety_settings=DEFAULT_SAFETY_SETTINGS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        # Build contents — text-only hoặc multimodal (text + image)
        if image_data:
            contents = [
                types.Part.from_bytes(
                    data=__import__("base64").b64decode(image_data["data"]),
                    mime_type=image_data["mime_type"],
                ),
                prompt,
            ]
        else:
            contents = prompt

        response = self._client.models.generate_content(
            model=self.settings.gemini_flash_model,
            contents=contents,
            config=config,
        )
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            u = response.usage_metadata
            print(f"[Tokens Flash] In: {getattr(u, 'prompt_token_count', 0)} | Out: {getattr(u, 'candidates_token_count', 0)} | Total: {getattr(u, 'total_token_count', 0)}")
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
            safety_settings=DEFAULT_SAFETY_SETTINGS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        for chunk in self._client.models.generate_content_stream(
            model=self.settings.gemini_pro_model,
            contents=prompt,
            config=config,
        ):
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                u = chunk.usage_metadata
                print(f"[Tokens Pro Stream] In: {getattr(u, 'prompt_token_count', 0)} | Out: {getattr(u, 'candidates_token_count', 0)} | Total: {getattr(u, 'total_token_count', 0)}")
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
            max_output_tokens=8192,
            safety_settings=DEFAULT_SAFETY_SETTINGS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        for chunk in self._client.models.generate_content_stream(
            model=self.settings.gemini_flash_model,
            contents=prompt,
            config=config,
        ):
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                u = chunk.usage_metadata
                print(f"[Tokens Flash Stream] In: {getattr(u, 'prompt_token_count', 0)} | Out: {getattr(u, 'candidates_token_count', 0)} | Total: {getattr(u, 'total_token_count', 0)}")
            if chunk.text:
                yield chunk.text

    def generate_search_grounded(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Gọi Gemini Flash với Google Search Grounding.
        Dùng cho: Tìm kiếm tin tức real-time, fact-checking với dữ liệu web mới nhất.
        """
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(
            tools=[google_search_tool],
            temperature=0.3,
            top_p=0.9,
            max_output_tokens=8192,
            safety_settings=DEFAULT_SAFETY_SETTINGS,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        response = self._client.models.generate_content(
            model=self.settings.gemini_flash_model,
            contents=prompt,
            config=config,
        )
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            u = response.usage_metadata
            print(f"[Tokens Search Grounded] In: {getattr(u, 'prompt_token_count', 0)} | Out: {getattr(u, 'candidates_token_count', 0)} | Total: {getattr(u, 'total_token_count', 0)}")
        return response.text


# === Singleton instance ===
_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Lấy singleton GeminiClient instance"""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
