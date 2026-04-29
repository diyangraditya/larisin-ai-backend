import os 
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey, exceptions

load_dotenv()

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("DB_NAME")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")

# Lazy-init: don't crash at import time if env vars are missing
_cosmos_container = None

def _get_container():
    """Initialize Cosmos client and container on first use."""
    global _cosmos_container
    if _cosmos_container is None:
        if not COSMOS_URI or not COSMOS_KEY:
            raise RuntimeError("COSMOS_URI or COSMOS_KEY is not set!")
        client = CosmosClient(COSMOS_URI, COSMOS_KEY)
        try:
            database = client.create_database_if_not_exists(id=DATABASE_NAME)
            _cosmos_container = database.create_container_if_not_exists(
                id=CONTAINER_NAME, 
                partition_key=PartitionKey(path="/user_id"),
                offer_throughput=400 
            )
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error Database: {e}")
            raise
    return _cosmos_container


# store history
def save_history(data: dict):
    if "id" not in data:
        import uuid
        data["id"] = str(uuid.uuid4())
    
    container = _get_container()
    container.upsert_item(data)
    return data