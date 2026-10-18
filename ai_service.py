import os
import io
import time
import hashlib
from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from fastapi import FastAPI, UploadFile, File, Form

load_dotenv()

app = FastAPI(title="Gemini AI Microservice (with Caching)")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

RESPONSE_CACHE = {}

FILE_CACHE = {}

CACHE_METRICS = {
    "total_requests": 0,
    "response_cache_hits": 0,
    "file_cache_hits": 0,
    "gemini_api_calls": 0,
    "total_tokens_used": 0,
    "total_tokens_saved": 0,
}


def extract_token_usage(interaction, input_text: str, output_text: str) -> dict:
    """Trích xuất chính xác số lượng token (bao gồm cả Google Implicit Cache) từ interaction.usage."""
    usage = getattr(interaction, "usage", None) or getattr(interaction, "usage_metadata", None)
    input_tokens = 0
    output_tokens = 0
    cached_tokens = 0
    total_tokens = 0

    if usage:
        input_tokens = (
            getattr(usage, "total_input_tokens", 0)
            or getattr(usage, "input_tokens", 0)
            or getattr(usage, "prompt_token_count", 0)
            or 0
        )
        output_tokens = (
            getattr(usage, "total_output_tokens", 0)
            or getattr(usage, "output_tokens", 0)
            or getattr(usage, "candidates_token_count", 0)
            or 0
        )
        cached_tokens = (
            getattr(usage, "total_cached_tokens", 0)
            or getattr(usage, "cached_tokens", 0)
            or getattr(usage, "cached_content_token_count", 0)
            or 0
        )
        total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)

    if input_tokens == 0 and output_tokens == 0:
        input_tokens = max(1, len(input_text) // 4)
        output_tokens = max(1, len(output_text) // 4)
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
    }


class BlogPostSchema(BaseModel):
    title: str
    seo_description: str
    html_content: str
    tags: str


class KeywordRequest(BaseModel):
    keyword: str
    use_cache: bool = True


@app.post("/ai-service/generate")
async def generate_content(request: KeywordRequest):
    start_time = time.perf_counter()
    CACHE_METRICS["total_requests"] += 1

    try:
        # Tạo Cache Key chuẩn hóa từ keyword
        normalized_keyword = request.keyword.strip().lower()
        cache_key = f"text:{ hashlib.sha256(normalized_keyword.encode('utf-8')).hexdigest() }"

        # 1. KIỂM TRA RESPONSE CACHE (Nếu bật use_cache)
        if request.use_cache and cache_key in RESPONSE_CACHE:
            cached_entry = RESPONSE_CACHE[cache_key]
            CACHE_METRICS["response_cache_hits"] += 1
            saved_tokens = cached_entry["token_usage"]["total_tokens"]
            CACHE_METRICS["total_tokens_saved"] += saved_tokens
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return {
                "status": "success",
                "data": cached_entry["data"],
                "meta": {
                    "cache_status": "HIT",
                    "cache_type": "Response Cache (Tiết kiệm 100% API & Token)",
                    "model": "gemini-3.5-flash-lite",
                    "latency_ms": latency_ms,
                    "tokens_used": 0,
                    "tokens_saved": saved_tokens,
                    "token_detail": cached_entry["token_usage"],
                },
            }

        # 2. CACHE MISS -> GỌI GEMINI API 
        prompt = """Bạn là Copywriter. Viết một bài blog chuẩn SEO. 
        Nội dung (html_content) phải dùng thẻ HTML cơ bản (<h2>, <p>, <ul>...)."""
        full_input = f"{prompt}\nChủ đề: {request.keyword}"

        interaction = client.interactions.create(
            model="gemini-3.5-flash-lite",
            input=full_input,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": BlogPostSchema.model_json_schema()
            }
        )

        blog_data = BlogPostSchema.model_validate_json(interaction.output_text)
        result_dict = blog_data.model_dump()

        # Tính toán Token & Lưu vào Cache
        token_usage = extract_token_usage(interaction, full_input, interaction.output_text)
        CACHE_METRICS["gemini_api_calls"] += 1
        CACHE_METRICS["total_tokens_used"] += token_usage["total_tokens"]

        RESPONSE_CACHE[cache_key] = {
            "keyword": request.keyword,
            "data": result_dict,
            "token_usage": token_usage,
            "created_at": time.strftime("%H:%M:%S"),
        }

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "status": "success",
            "data": result_dict,
            "meta": {
                "cache_status": "MISS",
                "cache_type": "Gọi trực tiếp Gemini API (Đã lưu vào Cache cho lần sau)",
                "model": "gemini-3.5-flash-lite",
                "latency_ms": latency_ms,
                "tokens_used": token_usage["total_tokens"],
                "tokens_saved": 0,
                "token_detail": token_usage,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/ai-service/generate-from-doc")
async def generate_from_doc(
    file: UploadFile = File(...),
    prompt_addition: str = Form(default=""),
    use_cache: bool = Form(default=True),
):
    start_time = time.perf_counter()
    CACHE_METRICS["total_requests"] += 1

    try:
        file_mime_type = file.content_type
        file_bytes = await file.read()

        # Tính mã băm SHA-256 của nội dung file và prompt_addition
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        normalized_prompt = prompt_addition.strip().lower()
        response_cache_key = f"doc:{file_hash}:{hashlib.sha256(normalized_prompt.encode('utf-8')).hexdigest()}"

        # 1. KIỂM TRA RESPONSE CACHE (Cùng file + cùng yêu cầu thêm)
        if use_cache and response_cache_key in RESPONSE_CACHE:
            cached_entry = RESPONSE_CACHE[response_cache_key]
            CACHE_METRICS["response_cache_hits"] += 1
            saved_tokens = cached_entry["token_usage"]["total_tokens"]
            CACHE_METRICS["total_tokens_saved"] += saved_tokens
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return {
                "status": "success",
                "data": cached_entry["data"],
                "meta": {
                    "cache_status": "HIT",
                    "cache_type": "Document Response Cache (Không cần upload & gọi lại Gemini)",
                    "file_cache_status": "HIT",
                    "model": "gemini-3.5-flash",
                    "latency_ms": latency_ms,
                    "tokens_used": 0,
                    "tokens_saved": saved_tokens,
                    "token_detail": cached_entry["token_usage"],
                },
            }

        # 2. KIỂM TRA FILE UPLOAD CACHE (Cùng file tài liệu nhưng yêu cầu/prompt khác)
        #    Giúp tái sử dụng URI trên Gemini mà không phải upload lại file tốn băng thông & API
        if use_cache and file_hash in FILE_CACHE:
            cached_file_info = FILE_CACHE[file_hash]
            uploaded_file_uri = cached_file_info["uri"]
            uploaded_file_mime = cached_file_info["mime_type"]
            file_cache_status = "HIT (Tái sử dụng File URI trên Gemini)"
            CACHE_METRICS["file_cache_hits"] += 1
        else:
            # Upload file lên Gemini (Giữ nguyên cú pháp cũ)
            file_stream = io.BytesIO(file_bytes)
            uploaded_file = client.files.upload(
                file=file_stream,
                config=dict(
                    mime_type=file_mime_type
                )
            )
            uploaded_file_uri = uploaded_file.uri
            uploaded_file_mime = uploaded_file.mime_type
            file_cache_status = "MISS (Đã upload mới & lưu URI vào File Cache)"

            FILE_CACHE[file_hash] = {
                "filename": file.filename,
                "uri": uploaded_file_uri,
                "mime_type": uploaded_file_mime,
                "size_bytes": len(file_bytes),
                "uploaded_at": time.strftime("%H:%M:%S"),
            }

        system_prompt = """Bạn là một Copywriter chuyên nghiệp. Hãy đọc file tài liệu được cung cấp và viết một bài blog chuẩn SEO. 
        Nội dung (html_content) phải dùng thẻ HTML cơ bản (<h2>, <p>, <ul>...). Trả về định dạng JSON đúng chuẩn Schema."""

        # Gọi Gemini Interactions API
        interaction = client.interactions.create(
            model="gemini-3.5-flash",
            input=[
                {
                    "type": "document",
                    "uri": uploaded_file_uri,
                    "mime_type": uploaded_file_mime
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
        result_dict = blog_data.model_dump()

        # Ước lượng/Trích xuất token (bao gồm cả total_cached_tokens từ Google Implicit Cache nếu file > 4,600 tokens)
        doc_estimated_chars = max(len(file_bytes) // 2, 500)
        token_usage = extract_token_usage(
            interaction,
            " " * doc_estimated_chars + system_prompt + prompt_addition,
            interaction.output_text,
        )
        google_implicit_cached = token_usage.get("cached_tokens", 0)
        # Nếu Google Implicit Cache kích hoạt (cached_tokens > 0) hoặc File URI được tái sử dụng từ Cache
        estimated_doc_tokens_saved = (
            google_implicit_cached
            if google_implicit_cached > 0
            else ((doc_estimated_chars // 4) if "HIT" in file_cache_status else 0)
        )
        if google_implicit_cached > 0:
            file_cache_status = f"HIT (File URI Cache + Google Implicit Cache: {google_implicit_cached} tokens)"

        CACHE_METRICS["gemini_api_calls"] += 1
        CACHE_METRICS["total_tokens_used"] += token_usage["total_tokens"]
        CACHE_METRICS["total_tokens_saved"] += estimated_doc_tokens_saved

        RESPONSE_CACHE[response_cache_key] = {
            "keyword": f"[Doc: {file.filename}] {prompt_addition or 'Mặc định'}",
            "data": result_dict,
            "token_usage": token_usage,
            "created_at": time.strftime("%H:%M:%S"),
        }

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "status": "success",
            "data": result_dict,
            "meta": {
                "cache_status": "PARTIAL_HIT" if "HIT" in file_cache_status else "MISS",
                "cache_type": file_cache_status,
                "file_cache_status": file_cache_status,
                "model": "gemini-3.5-flash",
                "latency_ms": latency_ms,
                "tokens_used": token_usage["total_tokens"],
                "tokens_saved": estimated_doc_tokens_saved,
                "token_detail": token_usage,
            },
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
        


@app.get("/ai-service/cache-stats")
async def get_cache_stats():
    """Endpoint cung cấp thống kê Cache & Token cho Dashboard Demo"""
    return {
        "status": "success",
        "metrics": CACHE_METRICS,
        "cached_responses_count": len(RESPONSE_CACHE),
        "cached_files_count": len(FILE_CACHE),
        "cached_items": [
            {
                "topic": item["keyword"],
                "title": item["data"]["title"],
                "tokens": item["token_usage"]["total_tokens"],
                "created_at": item["created_at"],
            }
            for item in RESPONSE_CACHE.values()
        ],
        "cached_files": [
            {
                "filename": f["filename"],
                "uri": f["uri"],
                "uploaded_at": f["uploaded_at"],
            }
            for f in FILE_CACHE.values()
        ],
    }


@app.delete("/ai-service/cache-clear")
async def clear_cache():
    """Xóa toàn bộ bộ nhớ đệm để phục vụ test/demo lại từ đầu"""
    RESPONSE_CACHE.clear()
    FILE_CACHE.clear()
    for k in CACHE_METRICS:
        CACHE_METRICS[k] = 0
    return {"status": "success", "message": "Đã xóa toàn bộ AI Cache và đặt lại bộ đếm Token!"}
