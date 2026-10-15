from crew_memory.graphdb import MemoryBackend, backend_for_tenant
from crew_memory.config import Config
from crew_memory import ingest


def test_ingest_counts(be):
    assert len(be.find_nodes("Person")) == 48
    assert len(be.find_nodes("Project")) == 8
    assert len(be.find_nodes("Decision")) == 8
    assert be.node_count() > 180
    assert be.edge_count() > 500


def test_company_marked_synthetic(be):
    company = be.find_nodes("Company")
    assert len(company) == 1
    assert company[0]["props"]["synthetic"] is True


def test_decision_traceability(be):
    dec = be.find_nodes("Decision", title="Adopt usage-based pricing for Atlas")
    assert len(dec) == 1
    by = be.traverse(dec[0]["uid"], [("MADE_BY", "out")])
    assert by and by[0]["nodes"][-1]["props"]["name"] == "Priya Nair"
    doc = be.traverse(dec[0]["uid"], [("DOCUMENTED_IN", "out")])
    assert doc and doc[0]["nodes"][-1]["props"]["title"] == "Atlas Pricing Analysis"


def test_expertise_derived_with_evidence(be):
    priya = be.get_node("person:priya-nair")
    edges = [(e, n) for e, n in be.neighbors(priya["uid"], "KNOWS_ABOUT", "out")]
    by_topic = {n["props"]["name"]: e for e, n in edges}
    assert by_topic["Payments"]["strength"] == 5
    assert by_topic["Payments"]["evidence"] >= 1


def test_tenant_isolation():
    cfg = Config(backend="memory")
    a = backend_for_tenant(cfg, "tenant-a")
    b = backend_for_tenant(cfg, "tenant-b")
    assert a is not b
    ingest.ingest_company(a)
    assert a.node_count() > 0
    assert b.node_count() == 0  # tenant B's graph is structurally separate
