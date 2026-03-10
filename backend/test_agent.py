import asyncio
import httpx
import json

async def test_agent():
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "qwen2.5-coder:7b",
        "messages": [
            {"role": "user", "content": "Siapa presiden Indonesia saat ini menurut berita?"}
        ],
        "stream": True,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Cari informasi di internet jika butuh berita terkini.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    print(line)

if __name__ == "__main__":
    asyncio.run(test_agent())
