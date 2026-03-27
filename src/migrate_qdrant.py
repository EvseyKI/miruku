from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
import os
import time

load_dotenv()

COLLECTION = "anime_storage"
BATCH_SIZE = 20

local = QdrantClient(host="localhost", port=6333)
cloud = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"],
)

info = local.get_collection(COLLECTION)
vector_size = info.config.params.vectors.size
distance = info.config.params.vectors.distance

print(f"Collection: {COLLECTION}, vector size: {vector_size}, distance: {distance}")

if not cloud.collection_exists(COLLECTION):
    cloud.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=distance),
    )
    print("Collection created in cloud.")
else:
    print("Collection already exists in cloud, continuing migration.")

offset = None
total = 0

while True:
    result = local.scroll(
        collection_name=COLLECTION,
        offset=offset,
        limit=BATCH_SIZE,
        with_vectors=True,
        with_payload=True,
    )
    points, offset = result

    if not points:
        break

    structs = [
        PointStruct(id=p.id, vector=p.vector, payload=p.payload)
        for p in points
    ]
    for attempt in range(3):
        try:
            cloud.upsert(collection_name=COLLECTION, points=structs)
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"Retry {attempt + 1} after error: {e}")
            time.sleep(5)
    total += len(points)
    print(f"Migrated {total} points...")

    if offset is None:
        break

print(f"Done! Total migrated: {total} points.")
