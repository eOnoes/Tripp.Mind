import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
from unittest.mock import Mock

import pytest
import requests

from tripp_mind_sdk import TrippMindClient


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def sign_jwt(payload, secret):
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url_encode(signature)}"


def verify_jwt(token, secret, issuer=None, audience=None):
    encoded_header, encoded_payload, encoded_signature = token.split(".")
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(encoded_signature)
    assert hmac.compare_digest(expected, actual)

    payload = json.loads(_b64url_decode(encoded_payload))
    now = int(time.time())
    assert payload.get("exp", now + 1) > now
    if issuer:
        assert payload["iss"] == issuer
    if audience:
        assert payload["aud"] == audience
    return payload


def test_jwt_token_generation_and_validation():
    secret = "integration-test-secret"
    payload = {
        "sub": "pytest",
        "roles": ["writer", "reader"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "iss": "tripp-mind",
        "aud": "tripp-fleet",
    }

    token = sign_jwt(payload, secret)
    decoded = verify_jwt(token, secret, issuer="tripp-mind", audience="tripp-fleet")

    assert decoded["sub"] == "pytest"
    assert decoded["roles"] == ["writer", "reader"]


def test_sdk_client_connects_to_gateway_contract():
    session = requests.Session()
    session.request = Mock(return_value=_response({"code": 0, "msg": "", "data": {"notebooks": []}}))

    client = TrippMindClient("http://gateway.example.test", "jwt-token", session=session, retries=0)
    rows = client.query_sql("select * from blocks limit 1")

    assert rows == []
    assert session.headers["Authorization"] == "Bearer jwt-token"


def test_create_notebook_note_search_backlinks_flow_contract():
    session = requests.Session()
    session.request = Mock(
        side_effect=[
            _response({"code": 0, "msg": "", "data": {"notebook": {"id": "nb1", "name": "Fleet"}}}),
            _response({"code": 0, "msg": "", "data": "doc1"}),
            _response({"code": 0, "msg": "", "data": {"blocks": [{"id": "doc1", "content": "Tripp"}], "matchedBlockCount": 1}}),
            _response({"code": 0, "msg": "", "data": {"backlinks": [{"id": "ref1"}], "backmentions": []}}),
        ]
    )
    client = TrippMindClient("http://gateway.example.test", "jwt-token", session=session, retries=0)

    notebook = client.create_notebook("Fleet")
    note = client.create_note(notebook.id, "Integration Note", "# Tripp")
    search = client.search("Tripp")
    backlinks = client.get_backlinks(note.id)

    assert notebook.id == "nb1"
    assert note.id == "doc1"
    assert search.matched_block_count == 1
    assert backlinks.backlinks == [{"id": "ref1"}]


def test_gateway_health_check_live():
    if os.getenv("RUN_LIVE_INTEGRATION") != "1":
        pytest.skip("set RUN_LIVE_INTEGRATION=1 with docker compose stack running")

    response = requests.get(f"{_gateway_url()}/api/health", timeout=10)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_note_pipeline_live():
    if os.getenv("RUN_LIVE_INTEGRATION") != "1":
        pytest.skip("set RUN_LIVE_INTEGRATION=1 with docker compose stack running")

    client = TrippMindClient(_gateway_url(), _gateway_token(), retries=1)
    notebook = client.create_notebook(f"pytest-{int(time.time())}")
    note = client.create_note(notebook.id, "Production Pipeline", "# Production Pipeline\n\nTripp.Mind live test")
    search = client.search("Production Pipeline")
    backlinks = client.get_backlinks(note.id)

    assert notebook.id
    assert note.id
    assert search.matched_block_count >= 0
    assert backlinks.link_refs_count >= 0


def test_event_bridge_and_bot_handlers_contract():
    result = subprocess.run(
        [
            "node",
            "-e",
            "const f=require('./lib/bot-format');"
            "console.log(f.formatRemember({title:'Fleet Note',id:'n1'}));"
            "console.log('---');"
            "console.log(f.formatSearch({blocks:[{hPath:'/Fleet',content:'Memory'}],matchedBlockCount:1}));",
        ],
        cwd=os.getcwd(),
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    )

    assert "Saved: Fleet Note" in result.stdout
    assert "Found 1 matching block" in result.stdout


def _response(payload, status_code=200):
    class Response:
        text = json.dumps(payload)
        headers = {}

        def __init__(self):
            self.status_code = status_code

        def json(self):
            return payload

    return Response()


def _gateway_url():
    return os.getenv("SIYUAN_GATEWAY_URL", "http://localhost:3000").rstrip("/")


def _gateway_token():
    token = os.getenv("SIYUAN_GATEWAY_TOKEN")
    if not token:
        pytest.skip("SIYUAN_GATEWAY_TOKEN is required for live integration")
    return token
