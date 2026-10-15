"""The FalkorDB backend cannot execute on this VM (no server), so its Cypher
is verified here as generated strings + parameter discipline, and its result
parsing is exercised against a recording fake graph client. The same
behavioral suite runs live in test_falkor_integration.py when a server exists.
"""
import pytest

from crew_memory.graphdb import FalkorDBBackend


class FakeResult:
    def __init__(self, rows):
        self.result_set = rows


class FakeGraph:
    def __init__(self):
        self.queries = []
        self.nodes = {
            "person:ada": ("Person", {"uid": "person:ada", "name": "Ada"}),
            "project:atlas": ("Project", {"uid": "project:atlas", "name": "Atlas"}),
        }

    def query(self, cypher, params=None):
        params = params or {}
        self.queries.append((cypher, params))
        if "nodes(path)" in cypher:
            return FakeResult([[["person:ada", "project:atlas"], ["OWNS"]]])
        if "n.uid IN $uids" in cypher:
            return FakeResult([[u, *self.nodes[u]] for u in params["uids"]])
        if "labels(n)[0]" in cypher:
            label, props = self.nodes[params["uid"]]
            return FakeResult([[label, props]])
        return FakeResult([])


def test_merge_node_cypher_uses_params():
    cypher = FalkorDBBackend.cypher_merge_node("Person")
    assert cypher.startswith("MERGE (n:Person {uid: $uid})")
    assert "$props" in cypher  # values are parameters, never interpolated


def test_traverse_cypher_pattern_and_whitelist():
    cypher = FalkorDBBackend.cypher_traverse([("OWNS", "in"), ("PART_OF", "out")])
    assert "<-[r0:OWNS]-(n1)" in cypher
    assert "-[r1:PART_OF]->(n2)" in cypher
    with pytest.raises(ValueError):
        FalkorDBBackend.cypher_traverse([("DROP_EVERYTHING", "out")])
    with pytest.raises(ValueError):
        FalkorDBBackend.cypher_merge_edge("NOT_A_REL")


def test_backend_against_fake_client():
    be = FalkorDBBackend(FakeGraph())
    node = be.get_node("person:ada")
    assert node["label"] == "Person" and node["props"]["name"] == "Ada"
    paths = be.traverse("person:ada", [("OWNS", "in")])
    assert len(paths) == 1
    assert [n["uid"] for n in paths[0]["nodes"]] == ["person:ada", "project:atlas"]
    assert paths[0]["rels"] == ["OWNS"]
    be.merge_node("Person", "person:grace", {"name": "Grace"})
    cypher, params = be.g.queries[-1]
    assert params == {"uid": "person:grace",
                      "props": {"name": "Grace", "uid": "person:grace"}}
