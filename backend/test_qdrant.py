import asyncio
from qdrant_client import QdrantClient
from app.core.config import settings

def test_qdrant():
    try:
        qdrant = QdrantClient(url=settings.QDRANT_URL)
        cols = qdrant.get_collections()
        print(f"Collections: {cols}")
        for c in cols.collections:
            info = qdrant.get_collection(c.name)
            print(f"Collection {c.name}: {info.points_count} points")
            if info.points_count > 0:
                # get some points
                res = qdrant.scroll(collection_name=c.name, limit=1)
                print(f"Sample point payload: {res[0][0].payload}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_qdrant()
