import os 
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey, exceptions

load_dotenv()

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("DB_NAME")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")

client = CosmosClient(COSMOS_URI, COSMOS_KEY)
# container = client.get_database_client(DATABASE_NAME).get_container_client(CONTAINER_NAME)

# create db if not exist
try:
    database = client.create_database_if_not_exists(id=DATABASE_NAME)
    # create container if no exist (partition_key sangat penting untuk performa)
    container = database.create_container_if_not_exists(
        id=CONTAINER_NAME, 
        partition_key=PartitionKey(path="/user_id"),
        offer_throughput=400 
    )
except exceptions.CosmosHttpResponseError as e:
    print(f"Error Database: {e}")

# store history
async def save_history(data: dict):
    # Cosmos DB butuh field "id" sebagai string unik
    if "id" not in data:
        import uuid
        data["id"] = str(uuid.uuid4())
    
    container.upsert_item(data)
    return data