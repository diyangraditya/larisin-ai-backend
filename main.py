import os
import json
import uuid
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


app = FastAPI(title="Larisin AI API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# setup azure client
main_api = os.getenv("OPENAI_AZURE_API")
secondary_api = os.getenv("SECONDARY_OPENAI_AZURE_API")
the_azure_endpoint = os.getenv("ENDPOINT_AZURE_OPENAI")

client = AzureOpenAI(
    azure_endpoint=the_azure_endpoint,
    api_key=main_api,
    api_version="2024-05-01-preview",
)

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
async def generate_image(file: UploadFile = File(...),
    ukuran_rasio: str = Form(...),
    fungsi_edit: str = Form(...),
    business_jenis: str = Form(...),
    business_target: str = Form(...),
    business_warna: str = Form(...),
    business_gaya_promosi: str = Form(...),
    instruksi_tambahan: Optional[str] = Form(None)
):
    # bisa proses file.read() untuk dikirim ke Azure atau di-save ke Blob Storage
    # Karena DALL-E 3 di Azure OpenAI generasinya via Text-to-Image, kamu perlu merakit prompt gambar.
    
    image_prompt = (
        f"Buatkan foto studio yang aesthetic dan profesional untuk sebuah {business_jenis} business. "
        f"Tema warna harus seperti ini {business_warna}. "
        f"Vibe/Style: {business_gaya_promosi}. Target audience: {business_target}. "
        f"Additional request: {instruksi_tambahan if instruksi_tambahan else 'Make it aesthetic and hyper-realistic'}."
    )

    try:
        # Panggilan ke Azure DALL-E (Pastikan deployment name DALL-E kamu benar)
        # response = client.images.generate(
        #     model="dall-e-3", # ganti dengan nama deployment DALL-E di Azure kamu
        #     prompt=image_prompt,
        #     n=1
        # )
        # result_image_url = response.data[0].url
        
        # --- DUMMY RESPONSE SEMENTARA AGAR FE BISA JALAN ---
        result_image_url = "https://dummyimage.com/600x800/000/fff&text=Hasil+Generate+AI"
        
        return {
            "job_id": "job-12345",
            "result_image_url": result_image_url,
            "message": "Gambar berhasil diproses"
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/v1/ai/generate-caption")
async def generate_caption(request: CaptionRequest):
    
    # --- 1. SETUP SYSTEM PROMPT ---
    # Saya perjelas struktur JSON di prompt agar AI tidak "berhalusinasi" saat nge-return data
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

    # --- 2. PANGGIL API AI ---
    try:
        response = client.chat.completions.create(
            # model=os.getenv("AZURE_MODEL", "gpt-4"),
            model="openai/gpt-oss-120b:free",
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

        # Validasi darurat: Jika AI aneh dan tidak membalas list caption
        if not captions:
            raise ValueError("AI gagal menghasilkan caption yang valid.")

    except Exception as e:
        # Jika AI gagal (misal: timeout atau kuota habis), kembalikan error 500 ke Frontend
        print(f"Error dari AI Engine: {e}")
        raise HTTPException(status_code=500, detail=f"AI gagal memproses: {str(e)}")

    # --- 3. SIMPAN KE AZURE COSMOS DB ---
    # Kita siapkan data dictionary-nya terlebih dahulu
    history_data = {
        "id": str(uuid.uuid4()),               # UUID Unik sebagai Primary Key Dokumen
        "user_id": "demo-user-123",            # Partition Key (Hardcoded sementara)
        "timestamp": datetime.utcnow().isoformat() + "Z", # Format waktu standar ISO
        "input_metadata": request.dict(),      # Menyimpan apa saja yang diminta user
        "result_captions": captions,           # Hasil output AI
        "result_hashtags": hashtags
    }

    try:
        # Memanggil fungsi save_history yang sudah kita buat sebelumnya
        await save_history(history_data)
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
