"""HTTP client for the Tripp.Mind API gateway."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Mapping, Optional

import requests

from .exceptions import ApiError, AuthenticationError, AuthorizationError, RateLimitError, TransportError
from .models import BacklinkResult, Graph, JsonDict, Note, Notebook, SearchResult


class TrippMindClient:
    """Client for the JWT-protected Tripp.Mind API gateway."""

    _TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: str,
        jwt_token: str,
        *,
        timeout: float = 30.0,
        retries: int = 3,
        backoff_factor: float = 0.25,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not jwt_token:
            raise ValueError("jwt_token is required")
        if retries < 0:
            raise ValueError("retries must be greater than or equal to 0")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
                "User-Agent": "tripp-mind-sdk-python/0.1.0",
            }
        )

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "TrippMindClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def create_notebook(self, name: str) -> Notebook:
        data = self._post("/api/notebook/createNotebook", {"name": name})
        notebook = data.get("notebook", {}) if isinstance(data, dict) else {}
        return Notebook.from_api(notebook)

    def create_note(self, notebook: str, title: str, content: str) -> Note:
        path = self._note_path(title)
        data = self._post(
            "/api/filetree/createDocWithMd",
            {"notebook": notebook, "path": path, "markdown": content},
        )
        return Note(id=str(data), notebook=notebook, title=title, content=content, path=path, raw={"data": data})

    def search(self, query: str) -> SearchResult:
        data = self._post(
            "/api/search/fullTextSearchBlock",
            {
                "query": query,
                "page": 1,
                "pageSize": 32,
                "paths": [],
                "boxes": [],
                "types": {},
                "subTypes": {},
                "method": 0,
                "orderBy": 0,
                "groupBy": 0,
            },
        )
        return SearchResult.from_api(data if isinstance(data, dict) else {})

    def query_sql(self, sql: str) -> List[JsonDict]:
        data = self._post("/api/query/sql", {"stmt": sql})
        return list(data) if isinstance(data, list) else []

    def get_graph(self) -> Graph:
        data = self._post("/api/graph/getGraph", {"k": "", "conf": {}, "reqId": None})
        return Graph.from_api(data if isinstance(data, dict) else {})

    def get_backlinks(self, block_id: str) -> BacklinkResult:
        data = self._post(
            "/api/ref/getBacklink",
            {"id": block_id, "k": "", "mk": "", "beforeLen": 12, "containChildren": True},
        )
        return BacklinkResult.from_api(data if isinstance(data, dict) else {})

    def get_note(self, note_id: str) -> Note:
        data = self._post(
            "/api/filetree/getDoc",
            {"id": note_id, "mode": 0, "size": 102400, "highlight": True},
        )
        return Note.from_doc_api(data if isinstance(data, dict) else {})

    def update_note(self, note_id: str, content: str) -> JsonDict:
        data = self._post(
            "/api/block/updateBlock",
            {"id": note_id, "dataType": "markdown", "data": content},
        )
        return {"operations": data}

    def delete_note(self, note_id: str) -> None:
        self._post("/api/filetree/removeDocByID", {"id": note_id})

    def _post(self, path: str, payload: Mapping[str, Any]) -> Any:
        return self._request("POST", path, json=dict(payload))

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        last_error: Optional[BaseException] = None

        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.retries:
                    self._sleep(attempt)
                    continue
                raise TransportError(f"Request failed: {exc}") from exc

            if response.status_code in self._TRANSIENT_STATUS_CODES and attempt < self.retries:
                self._sleep(attempt, response=response)
                continue

            return self._handle_response(response)

        raise TransportError(f"Request failed: {last_error}")

    def _handle_response(self, response: requests.Response) -> Any:
        body = self._json_body(response)

        if response.status_code == 401:
            raise AuthenticationError("Authentication failed", status_code=response.status_code, data=body)
        if response.status_code == 403:
            raise AuthorizationError("Endpoint is not allowed for this token", status_code=response.status_code, data=body)
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded", status_code=response.status_code, data=body)
        if response.status_code >= 400:
            message = self._error_message(body) or f"HTTP {response.status_code}"
            raise ApiError(message, status_code=response.status_code, data=body)

        if isinstance(body, dict) and "code" in body:
            code = int(body.get("code", 0) or 0)
            if code != 0:
                message = str(body.get("msg") or f"Tripp.Mind API error {code}")
                raise ApiError(message, code=code, status_code=response.status_code, data=body.get("data"))
            return body.get("data")

        return body

    def _json_body(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _sleep(self, attempt: int, *, response: Optional[requests.Response] = None) -> None:
        retry_after = self._retry_after(response)
        delay = retry_after if retry_after is not None else self.backoff_factor * (2**attempt)
        if delay > 0:
            time.sleep(delay)

    def _retry_after(self, response: Optional[requests.Response]) -> Optional[float]:
        if response is None:
            return None
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            return None

    def _error_message(self, body: Any) -> str:
        if isinstance(body, dict):
            value = body.get("message") or body.get("msg") or body.get("error")
            return str(value) if value else ""
        return str(body) if body else ""

    def _note_path(self, title: str) -> str:
        cleaned = title.strip().strip("/")
        if not cleaned:
            raise ValueError("title is required")
        return f"/{cleaned}"

