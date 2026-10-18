import sqlite3
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Blog Core Microservice")

# Cho phép Frontend gọi tới Service này
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class KeywordRequest(BaseModel):
    keyword: str
    use_cache: bool = True

@app.post("/api/create-post")
async def create_post(request: KeywordRequest):
    try:
        # Gọi sang AI Microservice bằng HTTPX
        async with httpx.AsyncClient(timeout=30.0) as client:
            ai_response = await client.post(
                "http://localhost:8001/ai-service/generate",
                json={"keyword": request.keyword, "use_cache": request.use_cache}
            )
            ai_data = ai_response.json()

        if ai_data.get("status") != "success":
            raise HTTPException(status_code=500, detail="Lỗi từ AI Service: " + ai_data.get("message", ""))

        article = ai_data["data"]
        meta = ai_data.get("meta", {})

        # Lưu dữ liệu vào SQLite
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO blog_posts (title, seo_description, html_content, tags)
            VALUES (?, ?, ?, ?)
            """, 
            (article['title'], article['seo_description'], article['html_content'], article['tags'])
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": "Đã tạo và lưu bài viết thành công!",
            "meta": meta
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/create-post-from-doc")
async def create_post_from_doc(
    file: UploadFile = File(...),
    prompt: str = Form(default=""),
    use_cache: bool = Form(default=True)
):
    try:
        file_bytes = await file.read()
        
        files = {'file': (file.filename, file_bytes, file.content_type)}
        data = {'prompt_addition': prompt, 'use_cache': str(use_cache).lower()}

        # Gọi sang AI Microservice bằng HTTPX
        async with httpx.AsyncClient(timeout=60.0) as client:
            ai_response = await client.post("http://localhost:8001/ai-service/generate-from-doc", files=files, data=data)
            ai_data = ai_response.json()

        if ai_data.get("status") != "success":
            raise HTTPException(status_code=500, detail="Lỗi từ AI Service: " + ai_data.get("message", ""))

        article = ai_data["data"]
        meta = ai_data.get("meta", {})

        # Lưu dữ liệu vào SQLite
        conn = sqlite3.connect('blog.db')
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO blog_posts (title, seo_description, html_content, tags)
            VALUES (?, ?, ?, ?)
            """, 
            (article['title'], article['seo_description'], article['html_content'], article['tags'])
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "message": "Đã tạo và lưu bài viết thành công!",
            "meta": meta
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/cache-stats")
async def get_cache_stats():
    """Lấy thống kê Cache & Token từ AI Microservice"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get("http://localhost:8001/ai-service/cache-stats")
            return res.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/cache-clear")
async def clear_cache():
    """Gửi lệnh xóa Cache sang AI Microservice"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.delete("http://localhost:8001/ai-service/cache-clear")
            return res.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/posts")
async def get_posts():
    """Lấy danh sách bài viết để hiển thị lên Blog"""
    try:
        conn = sqlite3.connect('blog.db')
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blog_posts ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return {"status": "success", "posts": [dict(row) for row in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}