"""Quick test of Tripp.Mind SDK against live gateway."""
import sys, os
sys.path.insert(0, "/opt/data/tripp-mind-sdk")

# Fake package for relative imports
import types
pkg = types.ModuleType('tripp_mind_sdk')
pkg.__path__ = ['/opt/data/tripp-mind_sdk']
sys.modules['tripp_mind_sdk'] = pkg

# Import and patch
from exceptions import ApiError, AuthenticationError, RateLimitError, TransportError
import client as client_mod
client_mod.ApiError = ApiError
client_mod.AuthenticationError = AuthenticationError
client_mod.RateLimitError = RateLimitError
client_mod.TransportError = TransportError

TrippMindClient = client_mod.TrippMindClient

# Test
client = TrippMindClient(
    gateway_url="http://tripp-mind-gateway-1:3000",
    token="eyJhbG...tS2w"
)

try:
    result = client._request("GET", "/api/health")
    print("HEALTH:", result)
except Exception as e:
    print("HEALTH_ERROR:", type(e).__name__, str(e)[:100])
