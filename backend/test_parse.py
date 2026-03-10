import json

content = '{"name": "web_search", "arguments": {"query": "nilai tukar rupiah dengan usd saat ini"}}'

tool_calls = []
try:
    data = json.loads(content)
    if isinstance(data, dict) and "name" in data and "arguments" in data:
        tool_calls.append({
            "function": {
                "name": data["name"],
                "arguments": data["arguments"]
            }
        })
except Exception:
    pass

print("Tool calls:", tool_calls)
