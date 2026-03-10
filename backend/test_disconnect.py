import asyncio
import httpx
import json
import time

async def trigger():
    tools = [{
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Cari informasi di internet menggunakan mesin pencari. Gunakan ini JIKA DAN HANYA JIKA pengguna bertanya tentang informasi terkini/saat ini, kurs mata uang, atau data yang tidak Anda ketahui.",
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
    }]
    
    messages = [
        {"role": "system", "content": "Kamu adalah ExecMind, asisten AI yang cerdas dan membantu. Jawab dengan Bahasa Indonesia yang formal dan profesional."},
        {"role": "user", "content": "coba cari lagi berapa nilai tukar rupiah dengan usd saat ini?"}
    ]
    
    print("Sending POST request to localhost:11434 started...")
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "qwen2.5-coder:7b",
                    "messages": messages,
                    "stream": False,
                    "tools": tools,
                    "options": {"temperature": 0.1}
                }
            )
            print("Status:", resp.status_code)
            print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print("EXCEPTION RAISED:", type(e), e)
    
    print("Elapsed time:", time.time() - start_time)

asyncio.run(trigger())
