"""
user_context.py - Quản lý ngữ cảnh người dùng
Lưu trữ và truy xuất profile, sở thích, lịch sử tương tác
"""

from memory.vector_store import get_user_memory_store
from typing import Optional
import json


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
            query_text=f"Thông tin về người dùng {user_id}",
            top_k=5,
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
    - Sở thích: {', '.join(profile.get('interests', []))}
    - Nguồn tin ưa thích: {', '.join(profile.get('preferred_news_sources', []))}
    - Phong cách làm việc: {profile.get('work_style', 'Chưa rõ')}
    """

    return update_user_context(user_id, profile_text.strip())


def _get_default_context() -> str:
    """Trả về ngữ cảnh mặc định khi chưa có thông tin người dùng"""
    return "Chưa có thông tin người dùng. Đây là cuộc trò chuyện mới."
