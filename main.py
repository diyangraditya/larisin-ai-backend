import os
import json
import uuid
import base64
import requests

from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
from pydantic import BaseModel
from typing import List, Optional
from larisin_pkg.db.cosmos import save_history
from larisin_pkg.db.blob import upload_image


app = FastAPI(title="Larisin AI API")

# CORS Middleware — set ALLOWED_ORIGINS env var in production (comma-separated)
# Ex: ALLOWED_ORIGINS=https://larisin-frontend.azurestaticapps.net,https://larisin.vercel.app
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# setup azure client — lazy-init to avoid crash if env vars are missing at startup
AZURE_OPENAI_API_KEY = os.getenv("OPENAI_AZURE_API")
AZURE_OPENAI_ENDPOINT = os.getenv("ENDPOINT_AZURE_OPENAI")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_IMAGE_API_KEY = os.getenv("AZURE_OPENAI_IMAGE_API")
ENDPOINT_AZURE_OPENAI_IMAGE = os.getenv("ENDPOINT_AZURE_OPENAI_IMAGE")
AZURE_OPENAI_API_IMAGE_VERSION = os.getenv("AZURE_OPENAI_API_IMAGE_VERSION")
AZURE_OPENAI_IMAGE_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT_NAME")

_client = None
_photo_client = None

def get_client():
    """Get or create the caption/text AzureOpenAI client."""
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )
    return _client

def get_photo_client():
    """Get or create the image generation AzureOpenAI client."""
    global _photo_client
    if _photo_client is None:
        _photo_client = AzureOpenAI(
            azure_endpoint=ENDPOINT_AZURE_OPENAI_IMAGE,
            api_key=AZURE_OPENAI_IMAGE_API_KEY,
            api_version=AZURE_OPENAI_API_IMAGE_VERSION,
        )
    return _photo_client

# setup pydactic models ---
class CaptionRequest(BaseModel):
    image_url: str
    fokus_promosi: str
    business_jenis: str
    business_target: str
    business_gaya_promosi: str
    business_platform: List[str]

@app.get("/")
async def read_root():
    return {"message": "the backend is running"}

@app.post("/api/v1/ai/generate-image")
async def generate_image(
    file: UploadFile = File(...),
    ukuran_rasio: str = Form(...),
    fungsi_edit: str = Form(...),
    business_jenis: str = Form(...),
    business_target: str = Form(...),
    business_warna: str = Form(...),
    business_gaya_promosi: str = Form(...),
    instruksi_tambahan: Optional[str] = Form(None)
):
    # Read File and Upload Original Photo to Blob
    file_bytes = await file.read()
    try:
        original_image_url = upload_image(
            image_bytes=file_bytes,
            filename=f"originals/{file.filename}",
            content_type=file.content_type
        )
        print(f"Foto asli berhasil diupload: {original_image_url}")
    except Exception as e:
        print(f"Gagal upload foto asli ke Blob: {e}")
        original_image_url = None

    # Construct Image Prompt
    image_prompt = (
        f"Buatkan foto studio yang aesthetic dan profesional untuk sebuah {business_jenis} business. "
        f"Tema warna harus seperti ini {business_warna}. "
        f"Vibe/Style: {business_gaya_promosi}. Target audience: {business_target}. "
        f"Additional request: {instruksi_tambahan if instruksi_tambahan else 'Make it aesthetic and hyper-realistic'}."
    )

    # Call Azure gpt-image-1.5
    try:
        response = get_photo_client().images.generate(
            model=os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT_NAME", "gpt-image-1.5"),
            prompt=image_prompt,
            n=1
        )
        # gpt-image-1 series always returns base64, decode and upload to Blob
        image_base64 = response.data[0].b64_json
        image_bytes = base64.b64decode(image_base64)
        result_image_url = upload_image(
            image_bytes=image_bytes,
            filename=f"generated/{uuid.uuid4()}.png",
            content_type="image/png"
        )
        
        # Response to Frontend
        return {
            "job_id": "job-12345",
            "original_image_url": original_image_url, # FE could use this for comparison Before/After
            "result_image_url": result_image_url,     # URL image from gpt-image-1.5
            "message": "Gambar berhasil diproses"
        }
        
    except Exception as e:
        print(f"Error generating image: {e}")                                                                     
        raise HTTPException(status_code=500, detail=f"AI gagal memproses gambar: {str(e)}") 

@app.post("/api/v1/ai/generate-caption")
async def generate_caption(request: CaptionRequest):
    
    # SETUP SYSTEM PROMPT
    system_prompt = (
        f"Kamu adalah seorang Social Media Manager dan Copywriter pro. "
        f"Target audiens adalah: {request.business_target}. "
        f"Gaya promosi yang diinginkan: {request.business_gaya_promosi}. "
        f"Platform yang dituju: {', '.join(request.business_platform)}. "
        f"Tugasmu adalah membuat 3 variasi caption yang natural, tidak kaku, dan menggunakan "
        f"bahasa/slang lokal Indonesia yang sesuai dengan target audiens. "
        f"Output harus HANYA dalam format JSON dengan struktur yang tepat seperti ini: "
        f"{{\"captions\": [\"opsi 1\", \"opsi 2\", \"opsi 3\"], \"hashtags\": [\"#tag1\", \"#tag2\", \"#tag3\", \"#tag4\", \"#tag5\"]}}"
    )

    user_prompt = f"Buatkan caption untuk mempromosikan {request.business_jenis} dengan fokus pada {request.fokus_promosi}."

    # CALL LLM
    try:
        response = get_client().chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={ "type": "json_object" },
            temperature=0.7
        )
        
        # Parsing JSON dari response text AI
        ai_content = response.choices[0].message.content
        ai_result = json.loads(ai_content)
        
        captions = ai_result.get("captions", [])
        hashtags = ai_result.get("hashtags", [])

        # Emergency Validation: If AI fails to return list of captions
        if not captions:
            raise ValueError("AI gagal menghasilkan caption yang valid.")

    except Exception as e:
        # If AI fails (ex: timeout or out of tokens), return 500 error to Frontend
        print(f"Error dari AI Engine: {e}")
        raise HTTPException(status_code=500, detail=f"AI gagal memproses: {str(e)}")

    # STORE TO AZURE COSMOS DB
    history_data = {
        "id": str(uuid.uuid4()),               # Document Primary Key
        "user_id": "demo-user-123",            # Partition Key (Temporarily Hardcoded)
        "timestamp": datetime.utcnow().isoformat() + "Z", # standar ISO time format
        "input_metadata": request.model_dump(),      # store any input from the user
        "result_captions": captions,           # output AI
        "result_hashtags": hashtags
    }

    try:
        # Memanggil fungsi save_history yang sudah kita buat sebelumnya
        save_history(history_data)
        print(f"[SUCCESS] History tersimpan di Cosmos DB dengan ID: {history_data['id']}")
    except Exception as db_error:
        print(f"[WARNING] Gagal simpan ke Cosmos DB (Non-fatal): {db_error}")

    return {
        "status": "success",
        "job_id": history_data["id"], # Berguna jika FE mau manggil ID ini lagi
        "captions": captions,
        "hashtags": hashtags
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
