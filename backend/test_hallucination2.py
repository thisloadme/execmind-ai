import asyncio
import os
from dotenv import load_dotenv

load_dotenv()
ollama_api_key = os.getenv("OLLAMA_API_KEY")

from ollama import AsyncClient

async def run():
    client_kwargs = {"host": "http://localhost:11434"}
    if ollama_api_key:
        client_kwargs["headers"] = {"Authorization": f"Bearer {ollama_api_key}"}
    client = AsyncClient(**client_kwargs)
    
    search_q = "Presiden ketiga Indonesia"
    response = await client.web_search(search_q, max_results=3)
    
    search_str = ""
    if hasattr(response, 'results') and response.results:
        search_str = "\n".join([f"- {r.get('title', 'Unknown') if isinstance(r, dict) else r.title}:\n{(r.get('content', '') if isinstance(r, dict) else r.content)[:1500]}" for r in response.results])
        
    context_prompt = (
        f"Gunakan informasi dari hasil pencarian internet berikut untuk '{search_q}':\n\n"
        f"<search_results>\n{search_str}\n</search_results>\n\n"
        "Kamu WAJIB menjawab berdasarkan informasi di atas, tulis dengan ringkas dan terstruktur."
    )
    
    messages = [
        {"role": "system", "content": "Kamu adalah ExecMind, asisten AI yang cerdas dan membantu. Jawab dengan Bahasa Indonesia yang formal dan profesional."},
        {"role": "user", "content": "siapa presiden ketiga indonesia?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "function": {
                    "name": "web_search",
                    "arguments": {"query": search_q}
                }
            }]
        },
        {"role": "tool", "content": context_prompt}
    ]
    
    resp = await client.chat(
        model="qwen2.5-coder:7b",
        messages=messages,
        options={"temperature": 0.1, "num_ctx": 4096}
    )
    print("====== LLM RESPONSE ======")
    print(resp['message']['content'])
    print("==========================\n")

asyncio.run(run())
