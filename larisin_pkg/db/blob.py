import os
import uuid
from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

load_dotenv()

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
AZURE_STORAGE_CONTAINER_URL = os.getenv("AZURE_STORAGE_CONTAINER_URL")

# Lazy-init: don't crash at import time if env vars are missing
blob_service_client = None
container_client = None

def _get_blob_client():
    """Initialize blob client on first use (not at module load)."""
    global blob_service_client, container_client
    if blob_service_client is None:
        if not AZURE_STORAGE_CONNECTION_STRING:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not set!")
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        try:
            container_client = blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER_NAME)
            if not container_client.exists():
                container_client.create_container()
                print(f"[BLOB] Container '{AZURE_STORAGE_CONTAINER_NAME}' created.")
        except Exception as e:
            print(f"[BLOB] Error initializing container: {e}")
    return blob_service_client


def upload_image(image_bytes: bytes, filename: str = None, content_type: str = "image/png") -> str:
    """
    Upload raw image bytes to Azure Blob Storage.

    Args:
        image_bytes:  Raw bytes of the image to upload.
        filename:     Blob name (e.g. "originals/photo.jpg" or auto-generated UUID path).
        content_type: MIME type of the image (default: image/png).

    Returns:
        Public URL of the uploaded blob.
    """
    if filename is None:
        filename = f"generated/{uuid.uuid4()}.png"

    client = _get_blob_client()
    blob_client = client.get_blob_client(
        container=AZURE_STORAGE_CONTAINER_NAME,
        blob=filename,
    )

    blob_client.upload_blob(
        image_bytes,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )

    # Build public URL from container URL base
    public_url = f"{AZURE_STORAGE_CONTAINER_URL.rstrip('/')}/{filename}"
    print(f"[BLOB] Image uploaded: {public_url}")
    return public_url
