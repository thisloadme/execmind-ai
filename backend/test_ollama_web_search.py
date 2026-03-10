import ollama

try:
    response = ollama.web_search("What is Ollama?")
    print("Response type:", type(response))
    print("Content:", response)
except Exception as e:
    print("Error:", e)
