"""Typed response models returned by the SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

JsonDict = Dict[str, Any]


@dataclass
class Notebook:
    id: str
    name: str
    icon: str = ""
    sort: int = 0
    closed: bool = False
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: JsonDict) -> "Notebook":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            icon=str(data.get("icon", "")),
            sort=int(data.get("sort", 0) or 0),
            closed=bool(data.get("closed", False)),
            raw=dict(data),
        )


@dataclass
class Note:
    id: str
    notebook: str
    title: str
    content: str
    path: str = ""
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_doc_api(cls, data: JsonDict, title: str = "") -> "Note":
        return cls(
            id=str(data.get("id", "")),
            notebook=str(data.get("box", "")),
            title=title,
            content=str(data.get("content", "")),
            path=str(data.get("path", "")),
            raw=dict(data),
        )


@dataclass
class SearchResult:
    blocks: List[JsonDict]
    matched_block_count: int = 0
    matched_root_count: int = 0
    page_count: int = 0
    doc_mode: bool = False
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: JsonDict) -> "SearchResult":
        blocks = data.get("blocks", [])
        return cls(
            blocks=list(blocks) if isinstance(blocks, list) else [],
            matched_block_count=int(data.get("matchedBlockCount", 0) or 0),
            matched_root_count=int(data.get("matchedRootCount", 0) or 0),
            page_count=int(data.get("pageCount", 0) or 0),
            doc_mode=bool(data.get("docMode", False)),
            raw=dict(data),
        )


@dataclass
class GraphNode:
    id: str
    label: str = ""
    path: str = ""
    notebook: str = ""
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: JsonDict) -> "GraphNode":
        return cls(
            id=str(data.get("id", "")),
            label=str(data.get("label", data.get("name", data.get("content", "")))),
            path=str(data.get("path", "")),
            notebook=str(data.get("box", "")),
            raw=dict(data),
        )


@dataclass
class GraphLink:
    source: str
    target: str
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: JsonDict) -> "GraphLink":
        source = data.get("source", data.get("from", data.get("fromID", "")))
        target = data.get("target", data.get("to", data.get("toID", "")))
        return cls(source=str(source), target=str(target), raw=dict(data))


@dataclass
class Graph:
    nodes: List[GraphNode]
    links: List[GraphLink]
    notebook: str = ""
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: JsonDict) -> "Graph":
        nodes = data.get("nodes", [])
        links = data.get("links", [])
        return cls(
            nodes=[GraphNode.from_api(node) for node in nodes if isinstance(node, dict)],
            links=[GraphLink.from_api(link) for link in links if isinstance(link, dict)],
            notebook=str(data.get("box", "")),
            raw=dict(data),
        )


@dataclass
class BacklinkResult:
    backlinks: List[JsonDict]
    backmentions: List[JsonDict]
    link_refs_count: int = 0
    mentions_count: int = 0
    notebook: str = ""
    raw: JsonDict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: JsonDict) -> "BacklinkResult":
        backlinks = data.get("backlinks", [])
        backmentions = data.get("backmentions", [])
        return cls(
            backlinks=list(backlinks) if isinstance(backlinks, list) else [],
            backmentions=list(backmentions) if isinstance(backmentions, list) else [],
            link_refs_count=int(data.get("linkRefsCount", 0) or 0),
            mentions_count=int(data.get("mentionsCount", 0) or 0),
            notebook=str(data.get("box", "")),
            raw=dict(data),
        )

