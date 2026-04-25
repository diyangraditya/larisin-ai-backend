import os
import requests

from dotenv import load_dotenv

from fastapi import FastAPI
from openai import AzureOpenAI

app = FastAPI()

load_dotenv()

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.post("/api/v1/generate")
async def generate():
    client = AzureOpenAI(
        azure_endpoint=os.getenv("ENDPOINT_AZURE_OPENAI"),
        api_key=os.getenv("OPENAI_AZURE_API"),
        api_version="2024-05-01-preview",
    )
    response = client.chat.completions.create(
        model=os.getenv("AZURE_MODEL"),
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ],
    )
    return {"Content": response.choices[0].message.content}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="[IP_ADDRESS]", port=8000)
