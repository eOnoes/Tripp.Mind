import urllib.request, json

TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjeW9ueSIsInJvbGVzIjpbIndyaXRlciJdLCJpYXQiOjE3ODI4NzU4MTIsImV4cCI6MTgxNDQxMTgxMn0.Y0oMwbFHEt1NC0EovDLiDterKvLXIenBY0FYNh3MACI"
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

print("=== HEALTH ===")
print(api_call("GET", "/api/health"))

print("\n=== CREATE NOTEBOOK ===")
print(api_call("POST", "/api/notebook/createNotebook", {"name": "fleet-knowledge"}))

print("\n=== LIST NOTEBOOKS ===")
result = api_call("POST", "/api/notebook/lsNotebooks")
if "data" in result:
    for nb in result["data"]:
        print(f"  - {nb.get('name', 'unknown')} ({nb.get('id', 'no-id')})")

print("\n=== CREATE NOTE ===")
print(api_call("POST", "/api/filetree/createDocWithMd", {
    "notebook": "fleet-knowledge",
    "path": "/test-note",
    "markdown": "# Hello from Cyony\n\nTest note via Tripp.Mind gateway."
}))

print("\n=== SEARCH ===")
print(api_call("POST", "/api/search/fullTextSearchBlock", {"query": "Hello", "page": 1}))

print("\n=== ALL TESTS COMPLETE ===")
