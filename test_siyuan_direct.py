import urllib.request, json

# Use the SiYuan auth token directly (simpler for testing)
SIYUAN_TOKEN = "8ca5566ca90d3c3a681b69aa8583d0d1"
GATEWAY = "http://tripp-mind-gateway-1:3000"

# For now, test SiYuan directly (bypass gateway) to verify it works
SIYUAN = "http://tripp-mind-siyuan-1:6806"

def siyuan_call(path, data=None):
    url = SIYUAN + path
    headers = {
        "Authorization": f"Token {SIYUAN_TOKEN}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)[:200]}

print("=== SIYUAN VERSION ===")
print(siyuan_call("/api/system/version"))

print("\n=== CREATE NOTEBOOK ===")
print(siyuan_call("/api/notebook/createNotebook", {"name": "fleet-knowledge"}))

print("\n=== LIST NOTEBOOKS ===")
result = siyuan_call("/api/notebook/lsNotebooks")
if "data" in result:
    for nb in result["data"]:
        print(f"  - {nb.get('name', 'unknown')} ({nb.get('id', 'no-id')})")

print("\n=== CREATE NOTE ===")
print(siyuan_call("/api/filetree/createDocWithMd", {
    "notebook": "fleet-knowledge",
    "path": "/test-note",
    "markdown": "# Hello from Cyony\n\nTest note created via SiYuan API."
}))

print("\n=== SEARCH ===")
print(siyuan_call("/api/search/fullTextSearchBlock", {"query": "Hello", "page": 1}))

print("\n=== ALL TESTS COMPLETE ===")
