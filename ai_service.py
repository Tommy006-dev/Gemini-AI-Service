import os
from pydantic import BaseModel
from google import genai
from fastapi import FastAPI,UploadFile,File,Form

app = FastAPI()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class BlogPostSchema(BaseModel):
    title: str
    seo_description: str
    html_content: str
    tags: str

class KeywordRequest(BaseModel):
    keyword: str

@app.post("/ai-service/generate")
async def generate_content(request: KeywordRequest):
    try:
        prompt = """Bạn là Copywriter. Viết một bài blog chuẩn SEO. 
        Nội dung (html_content) phải dùng thẻ HTML cơ bản (<h2>, <p>, <ul>...)."""
        
        interaction = client.interactions.create(
            model="gemini-3.5-flash-lite",
            input=f"{prompt}\nChủ đề: {request.keyword}",
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": BlogPostSchema.model_json_schema()
            }
        )
        
        blog_data = BlogPostSchema.model_validate_json(interaction.output_text)
        
        return {"status": "success", "data": blog_data.model_dump()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/ai-service/generate-from-doc")
async def generate_from_doc(file: UploadFile = File(...), prompt_addition: str = Form(default="")):
    try:
        file_mime_type = file.content_type

        uploaded_file = client.files.upload(
            file=file.file,
            config=dict(
                mime_type=file_mime_type
            )
        )

        system_prompt = """Bạn là một Copywriter chuyên nghiệp. Hãy đọc tài liệu được cung cấp và viết một bài blog chuẩn SEO. 
        Nội dung (html_content) phải dùng thẻ HTML cơ bản (<h2>, <p>, <ul>...). Trả về định dạng JSON đúng chuẩn Schema."""

        interaction = client.interactions.create(
            model="gemini-3.5-flash",  
            input=[
                {
                    "type": "document", 
                    "uri": uploaded_file.uri,          
                    "mime_type": uploaded_file.mime_type
                }, 
                {
                    "type": "text", 
                    "text": f"{system_prompt}\nYêu cầu thêm: {prompt_addition}"
                }
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": BlogPostSchema.model_json_schema()
            }
        )
        
        blog_data = BlogPostSchema.model_validate_json(interaction.output_text)
        return {"status": "success", "data": blog_data.model_dump()}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}