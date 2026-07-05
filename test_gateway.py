import urllib.request, json

TOKEN = "eyJhbG...6Rzg"
GATEWAY = "http://tripp-mind-gateway-1:3000"

def api_call(method, path, data=None):
    url = GATEWAY + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

# Test health
print("=== HEALTH ===")
print(api_call("GET", "/api/health"))

# Test create notebook
print("\n=== CREATE NOTEBOOK ===")
print(api_call("POST", "/api/notebook/createNotebook", {"name": "fleet-knowledge"}))

# Test list notebooks
print("\n=== LIST NOTEBOOKS ===")
print(api_call("POST", "/api/notebook/lsNotebooks"))

# Test create note
print("\n=== CREATE NOTE ===")
print(api_call("POST", "/api/filetree/createDocWithMd", {
    "notebook": "fleet-knowledge",
    "path": "/test-note",
    "markdown": "# Hello from Cyony\n\nThis is a test note created via the Tripp.Mind API gateway."
}))

# Test search
print("\n=== SEARCH ===")
print(api_call("POST", "/api/search/fullTextSearchBlock", {"query": "Hello", "page": 1}))

print("\n=== ALL TESTS COMPLETE ===")
