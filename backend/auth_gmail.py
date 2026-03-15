import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

# Cho phép dùng http://localhost thay vì bắt buộc https://
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def main():
    creds = None
    
    # Đặt script dir làm thư mục gốc để luôn tìm đúng file backend/credentials.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(script_dir, 'token.json')
    creds_path = os.path.join(script_dir, 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                print(f"Lỗi: Không tìm thấy file {creds_path}")
                print("Vui lòng tải từ Google Cloud Console và đặt tên là credentials.json")
                return
            
            # Khởi tạo Flow thủ công thay vì local server
            flow = Flow.from_client_secrets_file(
                creds_path,
                scopes=SCOPES,
                redirect_uri='http://localhost:8000/auth/callback'
            )
            
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            print("="*80)
            print("VÌ BẠN ĐANG DÙNG WEB APP CREDENTIALS, HÃY LÀM THEO CÁC BƯỚC SAU:")
            print("\n1. Nhấn giữ Ctrl và Click vào link này để mở trình duyệt:")
            print(f">>> {auth_url} <<<")
            print("\n2. Đăng nhập Google, bấm 'Allow/Cho phép' quyền đọc email.")
            print("   (Nếu hiện cảnh báo chưa xác minh, chọn 'Advanced' -> 'Go to...')")
            print("\n3. Trình duyệt sẽ chuyển hướng về lỗi hoặc trang trắng (không sao cả!).")
            print("4. HÃY COPY TOÀN BỘ ĐƯỜNG DẪN (URL) TRÊN THANH ĐỊA CHỈ LÚC ĐÓ DÁN XUỐNG DƯỚI.")
            print("="*80 + "\n")
            
            redirect_response = input("Dán toàn bộ Link URL vừa copy vào đây và bấm Enter: ").strip()
            
            try:
                flow.fetch_token(authorization_response=redirect_response)
                creds = flow.credentials
            except Exception as e:
                print(f"\n[Lỗi] Không thể sinh token: {e}")
                print("Đảm bảo bạn dán đúng cái link dài ngoằng có chứa chữ 'code='...")
                return
            
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())
            print("\n🎉 XONG! Đã tạo file token.json thành công!")
            
if __name__ == '__main__':
    main()
