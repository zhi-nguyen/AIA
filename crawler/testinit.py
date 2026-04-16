# test_task.py
from crawler_tasks import auto_ingest_news

if __name__ == "__main__":
    print("🚀 Đang khởi động Agent cào tin tức bằng tay...")
    # Gọi trực tiếp hàm như một hàm Python bình thường (Không có chữ .delay())
    # Cách này sẽ chạy đồng bộ, in toàn bộ log ra Terminal hiện tại cho muội dễ bắt lỗi
    auto_ingest_news()
    print("✅ Hoàn tất!")