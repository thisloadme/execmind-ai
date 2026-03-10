import asyncio
from qdrant_client import QdrantClient
from app.core.config import settings
from app.services.rag.embedder import OllamaEmbedder

async def test_search():
    try:
        qdrant = QdrantClient(url=settings.QDRANT_URL)
        embedder = OllamaEmbedder()
        
        query = "Coba sebutkan NPWP yang ada"
        collection_name = "kb_profil_perusahaan_73f135c0"
        collection_id = "2f4ebb64-d7c1-4233-81a6-a5b4ea188cb3"
        
        query_embedding = await embedder.embed_text(query)
        print(f"Embedding length: {len(query_embedding)}")
        
        import httpx
        
        url = f"{settings.QDRANT_URL}/collections/{collection_name}/points/search"
        payload = {
            "vector": query_embedding,
            "limit": 5,
            "filter": {
                "must": [
                    {
                        "key": "collection_id",
                        "match": {"value": collection_id}
                    }
                ]
            },
            "with_payload": True
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            print(resp.status_code)
            data = resp.json()
            
        print(f"Results: {len(data.get('result', []))}")
        for r in data.get('result', []):
            print(f"- Score: {r['score']}, Payload: {r['payload'].get('text')[:100]}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())
