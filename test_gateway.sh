#!/bin/bash
# Test Tripp.Mind gateway from Cyony's container
TOKEN="eyJhbG...pR4E"

# Test health
echo "=== HEALTH ==="
curl -s http://tripp-mind-gateway-1:3000/api/health

# Test create notebook
echo -e "\n=== CREATE NOTEBOOK ==="
curl -s -X POST http://tripp-mind-gateway-1:3000/api/notebook/createNotebook \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "fleet-knowledge"}'

# Test create note
echo -e "\n=== CREATE NOTE ==="
curl -s -X POST http://tripp-mind-gateway-1:3000/api/filetree/createDocWithMd \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notebook": "fleet-knowledge", "path": "/test-note", "markdown": "# Hello from Cyony\nThis is a test note created via the API gateway."}'

# Test search
echo -e "\n=== SEARCH ==="
curl -s -X POST http://tripp-mind-gateway-1:3000/api/search/fullTextSearchBlock \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello", "page": 1}'

echo -e "\n=== DONE ==="
