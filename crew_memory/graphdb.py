"""Graph data-access layer — the ONLY module that speaks to the graph store.

Two backends implement one interface:

* ``FalkorDBBackend`` — the production backend. Real Cypher via the official
  ``falkordb`` Python client. Every value goes through query parameters;
  relationship types are validated against a whitelist before they are
  interpolated into a pattern (labels and rel types cannot be parameters in
  Cypher, so they come only from our own schema constants).
* ``MemoryBackend`` — a pure-Python in-memory graph used by the test-suite and
  for offline development ONLY. It can snapshot to / restore from a JSON file,
  which is what lets the two-session demo run on a machine with no FalkorDB
  server. It is labeled as a dev backend everywhere it surfaces (API status,
  UI banner). It is never presented as FalkorDB.

Node shape everywhere: ``{"uid": str, "label": str, "props": {..}}`` where
``props`` always contains ``uid`` too. Path shape:
``{"nodes": [node, ...], "rels": [rel_type, ...]}`` with len(rels) == len(nodes)-1.

Performance shape (2026-10-17 optimization pass): against a hosted graph the
dominant cost is round trips and payload, not scans at demo scale, so the
FalkorDB backend's reads each run ONE query that returns fully-hydrated rows
(no uid-then-hydrate second pass), traversals hydrate all their rows in a
single follow-up query, and counts use server-side ``count()`` aggregation
instead of materializing the whole graph. ``connect()`` also creates the
schema indexes (per-label ``uid`` — the lookup key every pattern filters
on — plus the two filtered-list properties) so the labeled patterns stay
index-served as graphs grow past demo size.
"""
from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)

# Relationship types allowed in traversal patterns (schema whitelist).
REL_TYPES = {
    "MEMBER_OF", "WORKS_ON", "OWNS", "AUTHORED", "HAS_DECISION", "MADE_BY",
    "DOCUMENTED_IN", "ABOUT", "KNOWS_ABOUT", "FOR_PROJECT", "ASSIGNED_TO",
    "RESOLVED_BY", "DISCUSSES", "REFERENCES", "DEPENDS_ON", "PART_OF",
    "WROTE", "IN_SESSION", "FROM_AGENT", "TO_AGENT", "HAS_STEP", "NEXT_STEP",
    "LEARNED_IN", "MENTIONS",
}

TEXT_PROPS = ("name", "title", "summary", "text", "goal")

# Labels the schema writes (ingest + memory layers). ``connect()`` indexes
# each label's ``uid`` property — every point lookup, merge, and traversal
# anchors on ``uid`` — plus the two properties the list endpoints filter on.
INDEXED_LABELS = (
    "Company", "Team", "Person", "Topic", "Project", "Document", "Decision",
    "Ticket", "ChatThread", "Agent", "Session", "Episode", "Fact",
    "Procedure", "Step", "Handoff",
)
INDEXED_PROPS = (("Handoff", "status"), ("Episode", "session"))


def _node(uid: str, label: str, props: dict) -> dict:
    p = dict(props)
    p["uid"] = uid
    return {"uid": uid, "label": label, "props": p}


class GraphBackend(ABC):
    """One graph (one tenant). Implementations must be interchangeable."""

    name = "abstract"

    # -- writes ---------------------------------------------------------
    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def merge_node(self, label: str, uid: str, props: dict) -> dict: ...

    @abstractmethod
    def merge_edge(self, src_uid: str, rel: str, dst_uid: str, props: dict | None = None) -> None: ...

    @abstractmethod
    def set_props(self, uid: str, props: dict) -> None: ...

    # -- reads ----------------------------------------------------------
    @abstractmethod
    def get_node(self, uid: str) -> dict | None: ...

    @abstractmethod
    def find_nodes(self, label: str | None = None, **filters) -> list[dict]: ...

    @abstractmethod
    def neighbors(self, uid: str, rel: str | None = None, direction: str = "out") -> list[tuple[dict, dict]]:
        """Return [(edge_props, node), ...] adjacent to uid."""

    @abstractmethod
    def traverse(self, start_uid: str, steps: list[tuple[str, str]]) -> list[dict]:
        """Follow steps = [(rel, direction), ...] from start; return paths."""

    @abstractmethod
    def all_nodes(self) -> list[dict]: ...

    @abstractmethod
    def all_edges(self) -> list[dict]:
        """Return [{"src": uid, "rel": str, "dst": uid, "props": {...}}]."""

    @abstractmethod
    def search_text(self, text: str, limit: int = 25) -> list[dict]: ...

    # -- helpers --------------------------------------------------------
    def node_count(self) -> int:
        return len(self.all_nodes())

    def edge_count(self) -> int:
        return len(self.all_edges())

    def traverse_uids(self, start_uid: str, steps: list[tuple[str, str]]) -> list[list[str]]:
        return [[n["uid"] for n in p["nodes"]] for p in self.traverse(start_uid, steps)]


# ----------------------------------------------------------------------
# FalkorDB backend (production)
# ----------------------------------------------------------------------
class FalkorDBBackend(GraphBackend):
    """Cypher-backed backend using the official ``falkordb`` client.

    ``graph`` is a FalkorDB graph object (has ``.query(cypher, params)``).
    Injecting it keeps this class unit-testable with a recording fake.
    """

    name = "falkordb"

    def __init__(self, graph):
        self.g = graph

    @classmethod
    def connect(cls, cfg, tenant: str) -> "FalkorDBBackend":
        from falkordb import FalkorDB  # imported lazily: only needed live

        db = FalkorDB(
            host=cfg.falkor_host,
            port=cfg.falkor_port,
            username=cfg.falkor_username,
            password=cfg.falkor_password,
        )
        be = cls(db.select_graph(cfg.graph_name(tenant)))
        be.ensure_indexes()
        return be

    def ensure_indexes(self) -> None:
        """Create the schema indexes (idempotent housekeeping).

        One round trip per index, once per connection. Failures are
        swallowed: an index that already exists (or a server that manages
        its own indexing) must never stop the app from connecting — the
        queries are correct with or without them, just slower at scale.
        """
        statements = [
            f"CREATE INDEX FOR (n:{label}) ON (n.uid)"
            for label in INDEXED_LABELS
        ] + [
            f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
            for label, prop in INDEXED_PROPS
        ]
        for stmt in statements:
            try:
                self.g.query(stmt)
            except Exception as exc:
                # Never break connect over index housekeeping — but never
                # fail silently either: a swallowed error here means the
                # deployment runs unindexed, which must be observable.
                log.debug("ensure_indexes: statement skipped (%s): %s",
                          stmt, exc)

    # Cypher builders are pure functions of their inputs -> unit-testable.
    @staticmethod
    def cypher_merge_node(label: str) -> str:
        return f"MERGE (n:{label} {{uid: $uid}}) SET n += $props RETURN n.uid"

    @staticmethod
    def cypher_merge_edge(rel: str) -> str:
        if rel not in REL_TYPES:
            raise ValueError(f"relationship type not in schema: {rel}")
        return (
            "MATCH (a {uid: $src}), (b {uid: $dst}) "
            f"MERGE (a)-[r:{rel}]->(b) SET r += $props RETURN type(r)"
        )

    @staticmethod
    def cypher_traverse(steps: list[tuple[str, str]]) -> str:
        parts = ["MATCH path = (n0 {uid: $start})"]
        for i, (rel, direction) in enumerate(steps):
            if rel not in REL_TYPES:
                raise ValueError(f"relationship type not in schema: {rel}")
            if direction == "out":
                parts.append(f"-[r{i}:{rel}]->(n{i + 1})")
            elif direction == "in":
                parts.append(f"<-[r{i}:{rel}]-(n{i + 1})")
            elif direction == "both":
                parts.append(f"-[r{i}:{rel}]-(n{i + 1})")
            else:
                raise ValueError(f"bad direction: {direction}")
        parts.append(
            "RETURN [x IN nodes(path) | x.uid] AS uids, "
            "[r IN relationships(path) | type(r)] AS rels"
        )
        return " ".join(parts)

    def _rows(self, cypher: str, params: dict | None = None) -> list[list]:
        res = self.g.query(cypher, params or {})
        return res.result_set or []

    def clear(self) -> None:
        self.g.query("MATCH (n) DETACH DELETE n")

    def merge_node(self, label: str, uid: str, props: dict) -> dict:
        p = dict(props)
        p["uid"] = uid
        self._rows(self.cypher_merge_node(label), {"uid": uid, "props": p})
        return _node(uid, label, p)

    def merge_edge(self, src_uid: str, rel: str, dst_uid: str, props: dict | None = None) -> None:
        self._rows(
            self.cypher_merge_edge(rel),
            {"src": src_uid, "dst": dst_uid, "props": props or {}},
        )

    def set_props(self, uid: str, props: dict) -> None:
        self._rows("MATCH (n {uid: $uid}) SET n += $props", {"uid": uid, "props": props})

    def get_node(self, uid: str) -> dict | None:
        rows = self._rows(
            "MATCH (n {uid: $uid}) RETURN labels(n)[0] AS label, properties(n) AS props",
            {"uid": uid},
        )
        if not rows:
            return None
        label, props = rows[0]
        return _node(uid, label, props)

    def node_count(self) -> int:
        # Server-side aggregation: one small reply instead of materializing
        # (and shipping) every node just to count them.
        rows = self._rows("MATCH (n) RETURN count(n) AS c")
        return int(rows[0][0])

    def edge_count(self) -> int:
        rows = self._rows("MATCH ()-[r]->() RETURN count(r) AS c")
        return int(rows[0][0])

    def _hydrate(self, uids: list[str]) -> dict[str, dict]:
        if not uids:
            return {}
        rows = self._rows(
            "MATCH (n) WHERE n.uid IN $uids RETURN n.uid AS uid, labels(n)[0] AS label, properties(n) AS props",
            {"uids": uids},
        )
        return {uid: _node(uid, label, props) for uid, label, props in rows}

    def find_nodes(self, label: str | None = None, **filters) -> list[dict]:
        lab = f":{label}" if label else ""
        where, params = [], {"f": filters}
        for k in filters:
            # Filter KEYS are interpolated (values stay $f.* parameters), so
            # keys are restricted to plain identifiers — callers are our own
            # code with constant keys; anything else is a programming error,
            # never something to interpolate into Cypher.
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
                raise ValueError(f"bad filter key: {k!r}")
            where.append(f"n.{k} = $f.{k}")
        cypher = f"MATCH (n{lab})"
        if where:
            cypher += " WHERE " + " AND ".join(where)
        # One query, fully hydrated rows (was: uid query + _hydrate query).
        rows = self._rows(
            cypher + " RETURN n.uid AS uid, labels(n)[0] AS label, "
            "properties(n) AS props",
            params,
        )
        return [_node(uid, label, props) for uid, label, props in rows]

    def neighbors(self, uid: str, rel: str | None = None, direction: str = "out") -> list[tuple[dict, dict]]:
        if rel and rel not in REL_TYPES:
            raise ValueError(f"relationship type not in schema: {rel}")
        r = f"[r:{rel}]" if rel else "[r]"
        if direction == "out":
            pattern = f"(a {{uid: $uid}})-{r}->(b)"
        elif direction == "in":
            pattern = f"(a {{uid: $uid}})<-{r}-(b)"
        else:
            pattern = f"(a {{uid: $uid}})-{r}-(b)"
        # One query: edge properties and the neighbor node arrive together
        # (was: edge query + _hydrate query).
        rows = self._rows(
            f"MATCH {pattern} RETURN properties(r) AS eprops, b.uid AS buid, "
            "labels(b)[0] AS blabel, properties(b) AS bprops",
            {"uid": uid},
        )
        return [
            (row[0] or {}, _node(row[1], row[2], row[3])) for row in rows
        ]

    def traverse(self, start_uid: str, steps: list[tuple[str, str]]) -> list[dict]:
        rows = self._rows(self.cypher_traverse(steps), {"start": start_uid})
        # Hydrate every path's nodes in ONE follow-up query (was: one
        # _hydrate query per result row — N+1 on multi-path traversals).
        all_uids = list(dict.fromkeys(u for uids, _ in rows for u in uids))
        hydrated = self._hydrate(all_uids)
        paths = []
        for uids, rels in rows:
            if all(u in hydrated for u in uids):
                paths.append({"nodes": [hydrated[u] for u in uids], "rels": list(rels)})
        return paths

    def all_nodes(self) -> list[dict]:
        rows = self._rows(
            "MATCH (n) RETURN n.uid AS uid, labels(n)[0] AS label, "
            "properties(n) AS props"
        )
        return [_node(uid, label, props) for uid, label, props in rows]

    def all_edges(self) -> list[dict]:
        rows = self._rows(
            "MATCH (a)-[r]->(b) RETURN a.uid AS src, type(r) AS rel, b.uid AS dst, properties(r) AS props"
        )
        return [
            {"src": s, "rel": r, "dst": d, "props": p or {}}
            for s, r, d, p in rows
        ]

    def search_text(self, text: str, limit: int = 25) -> list[dict]:
        conds = " OR ".join(
            f"toLower(coalesce(n.{p}, '')) CONTAINS $q" for p in TEXT_PROPS
        )
        rows = self._rows(
            f"MATCH (n) WHERE {conds} RETURN n.uid AS uid, "
            "labels(n)[0] AS label, properties(n) AS props LIMIT $limit",
            {"q": text.lower(), "limit": limit},
        )
        return [_node(uid, label, props) for uid, label, props in rows]


# ----------------------------------------------------------------------
# In-memory backend (tests + offline development ONLY)
# ----------------------------------------------------------------------
class MemoryBackend(GraphBackend):
    """Pure-Python graph with the same interface as FalkorDBBackend.

    Supports JSON snapshot save/load so separate processes can share state in
    environments with no FalkorDB server (the demo scripts use this; the UI
    labels it as offline dev mode).
    """

    name = "memory"

    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self._edge_keys: set[tuple[str, str, str]] = set()

    def clear(self) -> None:
        self.nodes.clear()
        self.edges.clear()
        self._edge_keys.clear()

    def merge_node(self, label: str, uid: str, props: dict) -> dict:
        if uid in self.nodes:
            self.nodes[uid]["props"].update(props)
            self.nodes[uid]["props"]["uid"] = uid
            return self.nodes[uid]
        node = _node(uid, label, props)
        self.nodes[uid] = node
        return node

    def merge_edge(self, src_uid: str, rel: str, dst_uid: str, props: dict | None = None) -> None:
        if rel not in REL_TYPES:
            raise ValueError(f"relationship type not in schema: {rel}")
        key = (src_uid, rel, dst_uid)
        if key in self._edge_keys:
            for e in self.edges:
                if (e["src"], e["rel"], e["dst"]) == key:
                    e["props"].update(props or {})
                    return
        self._edge_keys.add(key)
        self.edges.append({"src": src_uid, "rel": rel, "dst": dst_uid, "props": dict(props or {})})

    def set_props(self, uid: str, props: dict) -> None:
        if uid in self.nodes:
            self.nodes[uid]["props"].update(props)

    def get_node(self, uid: str) -> dict | None:
        return self.nodes.get(uid)

    def find_nodes(self, label: str | None = None, **filters) -> list[dict]:
        out = []
        for n in self.nodes.values():
            if label and n["label"] != label:
                continue
            if all(n["props"].get(k) == v for k, v in filters.items()):
                out.append(n)
        return out

    def _adj(self, uid: str, rel: str | None, direction: str):
        for e in self.edges:
            if rel and e["rel"] != rel:
                continue
            if direction == "out" and e["src"] == uid:
                yield e, e["dst"]
            elif direction == "in" and e["dst"] == uid:
                yield e, e["src"]
            elif direction == "both" and e["src"] == uid:
                yield e, e["dst"]
            elif direction == "both" and e["dst"] == uid:
                yield e, e["src"]

    def neighbors(self, uid: str, rel: str | None = None, direction: str = "out") -> list[tuple[dict, dict]]:
        return [
            (e["props"], self.nodes[other])
            for e, other in self._adj(uid, rel, direction)
            if other in self.nodes
        ]

    def traverse(self, start_uid: str, steps: list[tuple[str, str]]) -> list[dict]:
        if start_uid not in self.nodes:
            return []
        frontier = [{"nodes": [self.nodes[start_uid]], "rels": []}]
        for rel, direction in steps:
            nxt = []
            for path in frontier:
                last = path["nodes"][-1]["uid"]
                for e, other in self._adj(last, rel, direction):
                    if other in self.nodes:
                        nxt.append({
                            "nodes": path["nodes"] + [self.nodes[other]],
                            "rels": path["rels"] + [e["rel"]],
                        })
            frontier = nxt
            if not frontier:
                break
        return frontier

    def all_nodes(self) -> list[dict]:
        return list(self.nodes.values())

    def all_edges(self) -> list[dict]:
        return [dict(e) for e in self.edges]

    def search_text(self, text: str, limit: int = 25) -> list[dict]:
        q = text.lower()
        out = []
        for n in self.nodes.values():
            hay = " ".join(str(n["props"].get(p, "")) for p in TEXT_PROPS).lower()
            if q in hay:
                out.append(n)
                if len(out) >= limit:
                    break
        return out

    # -- snapshot persistence (dev/demo across processes) ------------------
    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump({"nodes": list(self.nodes.values()), "edges": self.edges}, f)

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self.clear()
        for n in data["nodes"]:
            self.nodes[n["uid"]] = n
        for e in data["edges"]:
            self.edges.append(e)
            self._edge_keys.add((e["src"], e["rel"], e["dst"]))


def backend_for_tenant(cfg, tenant: str) -> GraphBackend:
    """The single construction point for backends."""
    if cfg.backend == "falkordb":
        return FalkorDBBackend.connect(cfg, tenant)
    return MemoryBackend()


def snapshot_path(cfg, tenant: str) -> str:
    return os.path.join(cfg.snapshot_dir, f"{tenant}.snapshot.json")
