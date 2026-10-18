# Gemini-AI-Service
## Hướng dẫn cách chạy 
1. Đăng nhập vào google studio để tạo và lấy key sau đó quay về thư mục code
3. Tạo biến môi trường:
- python -m venv .venv
- .venv\Scripts\activate.bat
4. Cài đặt các thư viện sau: pip install google-genai fastapi uvicorn httpx python-multipart python-dotenv
2. Tạo 3 bảng terminal
3. Terminal đầu tiên gõ lệnh sau để khởi tạo database: **python dp.py**
4. Terminal thứ hai gõ:
- Vào thư mục .env dán key lúc này vào : **GEMINI_API_KEY=key_cua_ban**
- Tiếp đó gõ lệnh sau để khỏi tạo AI Service: **uvicorn ai_service:app --port 8001**
5. Terminal thứ ba gõ lệnh sau để khởi tạo Blog Serivce: **uvicorn blog_service:app --port 8000**
6. Chạy file **frontend.html**