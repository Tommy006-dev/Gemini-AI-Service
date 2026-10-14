import os
from pydantic import BaseModel
from google import genai
from fastapi import FastAPI

app = FastAPI()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class BlogPostSchema(BaseModel):
    title: str
    seo_description: str
    html_content: str
    tags: str

class KeywordRequest(BaseModel):
    keyword: str

@app.post("/internal/generate")
async def generate_content(request: KeywordRequest):
    try:
        prompt = """Bạn là Copywriter. Viết một bài blog chuẩn SEO. 
        Nội dung (html_content) phải dùng thẻ HTML cơ bản (<h2>, <p>, <ul>...)."""
        
        # Sử dụng logic interactions.create như đoạn code mẫu cuối file
        interaction = client.interactions.create(
            model="gemini-3.5-flash-lite",
            input=f"{prompt}\nChủ đề: {request.keyword}",
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": BlogPostSchema.model_json_schema()
            }
        )
        
        # Parse chuỗi JSON trả về thành object
        blog_data = BlogPostSchema.model_validate_json(interaction.output_text)
        
        return {"status": "success", "data": blog_data.model_dump()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


