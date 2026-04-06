"""
user_context.py - Quản lý ngữ cảnh người dùng
Lưu trữ và truy xuất profile, sở thích, lịch sử tương tác
"""

from memory.vector_store import get_user_memory_store
from typing import Optional
import json
import re


def retrieve_user_context(user_id: str) -> str:
    """
    Truy xuất ngữ cảnh người dùng từ pgvector.
    
    Args:
        user_id: ID của người dùng
        
    Returns:
        Chuỗi text chứa thông tin ngữ cảnh người dùng
    """
    store = get_user_memory_store()
    try:
        result = store.query(
            query_text="Thông tin cá nhân, sở thích, và ngữ cảnh hiện tại",
            top_k=5,
            filters={"user_id": user_id}
        )
        return result if result and result != "Empty Response" else _get_default_context()
    except Exception as e:
        print(f"[Memory] Lỗi khi truy xuất context cho {user_id}: {e}")
        return _get_default_context()


def update_user_context(user_id: str, new_info: str) -> bool:
    """
    Cập nhật ngữ cảnh người dùng vào pgvector.
    
    Args:
        user_id: ID của người dùng
        new_info: Thông tin mới cần lưu
        
    Returns:
        True nếu thành công
    """
    store = get_user_memory_store()
    try:
        from sqlalchemy import text
        if hasattr(store._vector_store, "_session"):
            session_maker = store._vector_store._session
            with session_maker() as session:
                session.execute(
                    text("DELETE FROM data_aia_user_memory WHERE metadata_->>'user_id' = :uid AND metadata_->>'type' = 'user_profile'"),
                    {"uid": user_id}
                )
                session.commit()
    except Exception as e:
        print(f"[Memory] Could not clean old user profile (ignoring): {e}")

    try:
        store.add_documents(
            texts=[new_info],
            metadata_list=[{
                "user_id": user_id,
                "type": "user_profile",
            }],
        )
        print(f"[Memory] Đã cập nhật context cho user: {user_id}")
        return True
    except Exception as e:
        print(f"[Memory] Lỗi khi cập nhật context cho {user_id}: {e}")
        return False


def initialize_user_profile(user_id: str, profile: dict) -> bool:
    """
    Khởi tạo profile người dùng lần đầu.
    
    Args:
        user_id: ID người dùng
        profile: Dict chứa thông tin profile
            - name: Tên người dùng
            - occupation: Nghề nghiệp
            - interests: Danh sách sở thích
            - preferred_news_sources: Nguồn tin ưa thích
            - work_style: Phong cách làm việc
    """
    profile_text = f"""
    Thông tin người dùng (User ID: {user_id}):
    - Tên: {profile.get('name', 'Chưa đặt')}
    - Nghề nghiệp: {profile.get('occupation', 'Chưa rõ')}
    - Địa chỉ: {profile.get('address', 'Chưa rõ')}
    - Sở thích: {', '.join(profile.get('interests', []))}
    - Nguồn tin ưa thích: {', '.join(profile.get('preferred_news_sources', []))}
    - Phong cách làm việc: {profile.get('work_style', 'Chưa rõ')}
    """

    return update_user_context(user_id, profile_text.strip())


def _get_default_context() -> str:
    """Trả về ngữ cảnh mặc định khi chưa có thông tin người dùng"""
    return "Chưa có thông tin người dùng. Đây là cuộc trò chuyện mới."


def get_user_profile(user_id: str) -> Optional[dict]:
    """
    Truy xuất profile đã lưu của người dùng từ pgvector.
    Parse text đã lưu thành dict có cấu trúc.

    Args:
        user_id: ID của người dùng

    Returns:
        Dict chứa profile hoặc None nếu chưa có
    """
    store = get_user_memory_store()
    try:
        result = store.query(
            query_text="Thông tin chi tiết hồ sơ profile",
            top_k=1,
            filters={"user_id": user_id, "type": "user_profile"}
        )

        if not result or result == "Empty Response":
            return None

        # Parse structured text back to dict
        profile: dict = {"user_id": user_id}

        name_match = re.search(r"- Tên:\s*(.*?)(?=\s*- \w|$)", result, re.DOTALL)
        if name_match:
            profile["name"] = name_match.group(1).strip()

        occ_match = re.search(r"- Nghề nghiệp:\s*(.*?)(?=\s*- \w|$)", result, re.DOTALL)
        if occ_match:
            profile["occupation"] = occ_match.group(1).strip()

        addr_match = re.search(r"- Địa chỉ:\s*(.*?)(?=\s*- \w|$)", result, re.DOTALL)
        if addr_match:
            profile["address"] = addr_match.group(1).strip()

        interests_match = re.search(r"- Sở thích:\s*(.*?)(?=\s*- \w|$)", result, re.DOTALL)
        if interests_match:
            raw = interests_match.group(1).strip()
            profile["interests"] = [s.strip() for s in raw.split(",") if s.strip()] if raw else []

        news_match = re.search(r"- Nguồn tin ưa thích:\s*(.*?)(?=\s*- \w|$)", result, re.DOTALL)
        if news_match:
            raw = news_match.group(1).strip()
            profile["preferred_news_sources"] = [s.strip() for s in raw.split(",") if s.strip()] if raw else []

        style_match = re.search(r"- Phong cách làm việc:\s*(.*?)(?=\s*- \w|$)", result, re.DOTALL)
        if style_match:
            profile["work_style"] = style_match.group(1).strip()

        # Chỉ trả về nếu có ít nhất trường name
        if "name" in profile and profile["name"] != "Chưa đặt":
            return profile

        return None

    except Exception as e:
        print(f"[Memory] Lỗi khi lấy profile cho {user_id}: {e}")
        return None

