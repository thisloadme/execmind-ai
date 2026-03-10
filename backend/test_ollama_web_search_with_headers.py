import asyncio
from app.core.config import settings
from ollama import AsyncClient

async def test_search():
    client_kwargs = {"host": settings.OLLAMA_URL}
    if settings.OLLAMA_API_KEY:
        client_kwargs["headers"] = {"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"}
        
    client = AsyncClient(**client_kwargs)
    try:
        print("Using headers:", client_kwargs.get("headers"))
        response = await client.web_search("What is Ollama?", max_results=3)
        print("Search successful, response type:", type(response))
        if isinstance(response, list):
            for res in response:
                print(f"- {res.get('title')}")
        elif hasattr(response, 'results') and response.results:
            for res in response.results:
                title = res.get('title', 'Unknown') if isinstance(res, dict) else res.title
                print(f"- {title}")
    except Exception as e:
        print("Error during search:", e)

asyncio.run(test_search())
