import asyncio
import httpx
import json

async def test():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Cari informasi di internet menggunakan mesin pencari.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Kata kunci pencarian internet."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]
    messages = [
        {"role": "user", "content": "coba cari lagi berapa nilai tukar rupiah dengan usd saat ini?"}
    ]
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("Sending initial request...")
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "qwen2.5-coder:7b",
                "messages": messages,
                "stream": False,
                "tools": tools,
            }
        )
        data = resp.json()
        print("Response 1:", json.dumps(data, indent=2))
        msg = data.get("message", {})
        
        if msg.get("tool_calls"):
            messages.append(msg)
            messages.append({
                "role": "tool",
                "content": "- 1 USD = 15,000 IDR (Data simulasi)"
            })
            
            print("Sending tool response back to model...")
            resp2 = await client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "qwen2.5-coder:7b",
                    "messages": messages,
                    "stream": False,
                }
            )
            print("Response 2 (status):", resp2.status_code)
            try:
                print("Response 2 (json):", json.dumps(resp2.json(), indent=2))
            except Exception as e:
                print("Failed to decode json:", e)

asyncio.run(test())
