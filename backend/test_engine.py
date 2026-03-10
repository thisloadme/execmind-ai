import asyncio
from app.services.rag.query_engine import RAGQueryEngine

async def test_engine():
    engine = RAGQueryEngine()
    print("Testing simple_chat with tool (web search)")
    
    # "siapa presiden indonesia" should trigger web search or be answered quickly
    async for chunk in engine.query_streaming(
        "Tolong gunakan mesin pencari internet untuk 'Prabowo Subianto Presiden Indonesia 2024'",
        collection_name="fake",
        collection_id="fake_id"
    ):
        if chunk.get("type") == "token":
            print(chunk.get("content", ""), end="", flush=True)
            
    print("\n\nDone.")

if __name__ == "__main__":
    asyncio.run(test_engine())
