from unittest.mock import Mock

import pytest
import requests

from tripp_mind_sdk import (
    ApiError,
    AuthenticationError,
    BacklinkResult,
    Graph,
    Note,
    Notebook,
    SearchResult,
    TransportError,
    TrippMindClient,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


@pytest.fixture
def session():
    return requests.Session()


def make_client(session, **kwargs):
    return TrippMindClient(
        "https://gateway.example.test",
        "jwt-token",
        session=session,
        retries=kwargs.pop("retries", 0),
        backoff_factor=0,
        **kwargs,
    )


def test_create_notebook_uses_jwt_and_returns_model(session):
    session.request = Mock(
        return_value=FakeResponse(
            payload={
                "code": 0,
                "msg": "",
                "data": {
                    "notebook": {
                        "id": "nb1",
                        "name": "Research",
                        "icon": "1f4d3",
                        "sort": 3,
                        "closed": False,
                    }
                },
            }
        )
    )

    client = make_client(session)
    notebook = client.create_notebook("Research")

    assert session.headers["Authorization"] == "Bearer jwt-token"
    assert notebook == Notebook(id="nb1", name="Research", icon="1f4d3", sort=3, closed=False, raw=notebook.raw)
    session.request.assert_called_once_with(
        "POST",
        "https://gateway.example.test/api/notebook/createNotebook",
        timeout=30.0,
        json={"name": "Research"},
    )


def test_create_note_posts_markdown_and_returns_note(session):
    session.request = Mock(return_value=FakeResponse(payload={"code": 0, "msg": "", "data": "doc1"}))

    note = make_client(session).create_note("nb1", "Projects/Plan", "# Plan")

    assert note == Note(id="doc1", notebook="nb1", title="Projects/Plan", content="# Plan", path="/Projects/Plan", raw=note.raw)
    session.request.assert_called_once_with(
        "POST",
        "https://gateway.example.test/api/filetree/createDocWithMd",
        timeout=30.0,
        json={"notebook": "nb1", "path": "/Projects/Plan", "markdown": "# Plan"},
    )


def test_search_returns_search_result(session):
    session.request = Mock(
        return_value=FakeResponse(
            payload={
                "code": 0,
                "msg": "",
                "data": {
                    "blocks": [{"id": "b1", "content": "hello"}],
                    "matchedBlockCount": 1,
                    "matchedRootCount": 1,
                    "pageCount": 1,
                },
            }
        )
    )

    result = make_client(session).search("hello")

    assert isinstance(result, SearchResult)
    assert result.blocks == [{"id": "b1", "content": "hello"}]
    assert result.matched_block_count == 1


def test_query_sql_returns_rows(session):
    session.request = Mock(return_value=FakeResponse(payload={"code": 0, "msg": "", "data": [{"id": "b1"}]}))

    rows = make_client(session).query_sql("select * from blocks limit 1")

    assert rows == [{"id": "b1"}]
    assert session.request.call_args.kwargs["json"] == {"stmt": "select * from blocks limit 1"}


def test_get_graph_returns_graph(session):
    session.request = Mock(
        return_value=FakeResponse(
            payload={
                "code": 0,
                "msg": "",
                "data": {
                    "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                    "links": [{"source": "a", "target": "b"}],
                    "box": "nb1",
                },
            }
        )
    )

    graph = make_client(session).get_graph()

    assert isinstance(graph, Graph)
    assert [node.id for node in graph.nodes] == ["a", "b"]
    assert graph.links[0].source == "a"
    assert graph.links[0].target == "b"


def test_get_backlinks_returns_backlink_result(session):
    session.request = Mock(
        return_value=FakeResponse(
            payload={
                "code": 0,
                "msg": "",
                "data": {
                    "backlinks": [{"id": "b1"}],
                    "backmentions": [{"id": "m1"}],
                    "linkRefsCount": 1,
                    "mentionsCount": 1,
                    "box": "nb1",
                },
            }
        )
    )

    backlinks = make_client(session).get_backlinks("doc1")

    assert isinstance(backlinks, BacklinkResult)
    assert backlinks.backlinks == [{"id": "b1"}]
    assert session.request.call_args.kwargs["json"]["id"] == "doc1"


def test_get_note_returns_note_content(session):
    session.request = Mock(
        return_value=FakeResponse(
            payload={
                "code": 0,
                "msg": "",
                "data": {
                    "id": "doc1",
                    "box": "nb1",
                    "path": "/Plan.sy",
                    "content": "<div>Plan</div>",
                },
            }
        )
    )

    note = make_client(session).get_note("doc1")

    assert note.id == "doc1"
    assert note.notebook == "nb1"
    assert note.content == "<div>Plan</div>"


def test_update_note_returns_operations(session):
    operations = [{"doOperations": [{"action": "update"}]}]
    session.request = Mock(return_value=FakeResponse(payload={"code": 0, "msg": "", "data": operations}))

    result = make_client(session).update_note("doc1", "updated")

    assert result == {"operations": operations}
    assert session.request.call_args.kwargs["json"] == {
        "id": "doc1",
        "dataType": "markdown",
        "data": "updated",
    }


def test_delete_note_uses_remove_doc_by_id(session):
    session.request = Mock(return_value=FakeResponse(payload={"code": 0, "msg": "", "data": None}))

    assert make_client(session).delete_note("doc1") is None
    session.request.assert_called_once_with(
        "POST",
        "https://gateway.example.test/api/filetree/removeDocByID",
        timeout=30.0,
        json={"id": "doc1"},
    )


def test_api_code_error_raises_api_error(session):
    session.request = Mock(return_value=FakeResponse(payload={"code": -1, "msg": "bad request", "data": None}))

    with pytest.raises(ApiError) as error:
        make_client(session).query_sql("bad sql")

    assert "bad request" in str(error.value)
    assert error.value.code == -1


def test_authentication_error_for_401(session):
    session.request = Mock(return_value=FakeResponse(status_code=401, payload={"error": "invalid_token"}))

    with pytest.raises(AuthenticationError):
        make_client(session).search("x")


def test_retries_transient_status_then_succeeds(session):
    session.request = Mock(
        side_effect=[
            FakeResponse(status_code=503, payload={"error": "unavailable"}),
            FakeResponse(payload={"code": 0, "msg": "", "data": [{"ok": True}]}),
        ]
    )

    rows = make_client(session, retries=1).query_sql("select 1")

    assert rows == [{"ok": True}]
    assert session.request.call_count == 2


def test_transport_error_after_retries(session):
    session.request = Mock(side_effect=requests.ConnectionError("network down"))

    with pytest.raises(TransportError):
        make_client(session, retries=1).query_sql("select 1")

    assert session.request.call_count == 2

