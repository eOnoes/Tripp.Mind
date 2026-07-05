import urllib.request, json, subprocess

# Get token from gateway container
result = subprocess.run(
    ["docker", "exec", "tripp-mind-gateway-1", "node", "-e",
     "const jwt=require('jsonwebtoken');process.stdout.write(jwt.sign({sub:'cyony',roles:['writer']},process.env.JWT_SECRET,{expiresIn:'365d'}))"],
    capture_output=True, text=True, timeout=10
)
TOKEN = result.stdout.strip()
GATEWAY = "http://tripp-mind-gateway-1:3000"

print(f"Token length: {len(TOKEN)}")

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
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
    except Exception as e:
        return {"error": str(e)}

print("\n=== HEALTH ===")
print(api_call("GET", "/api/health"))

print("\n=== CREATE NOTEBOOK ===")
print(api_call("POST", "/api/notebook/createNotebook", {"name": "fleet-knowledge"}))

print("\n=== LIST NOTEBOOKS ===")
result = api_call("POST", "/api/notebook/lsNotebooks")
if "data" in result:
    for nb in result["data"]:
        print(f"  - {nb.get('name', 'unknown')} ({nb.get('id', 'no-id')})")
else:
    print(result)

print("\n=== CREATE NOTE ===")
print(api_call("POST", "/api/filetree/createDocWithMd", {
    "notebook": "fleet-knowledge",
    "path": "/test-note",
    "markdown": "# Hello from Cyony\n\nTest note via Tripp.Mind gateway."
}))

print("\n=== SEARCH ===")
print(api_call("POST", "/api/search/fullTextSearchBlock", {"query": "Hello", "page": 1}))

print("\n=== ALL TESTS COMPLETE ===")
