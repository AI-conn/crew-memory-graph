"""Live FalkorDB integration suite — the same behaviors the memory-backend
tests assert, run against a real FalkorDB server.

Skipped unless FALKORDB_HOST is set. To run it in the demo environment:

    docker run -p 6379:6379 falkordb/falkordb:latest      # or FalkorDB Cloud
    APP_GRAPH_BACKEND=falkordb FALKORDB_HOST=localhost \
        pytest tests/test_falkor_integration.py
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("FALKORDB_HOST"),
    reason="FALKORDB_HOST not set — no live FalkorDB server available",
)

from crew_memory import agents, ingest, qa
from crew_memory.config import Config
from crew_memory.graphdb import FalkorDBBackend


@pytest.fixture()
def fbe():
    cfg = Config.from_env()
    cfg.backend = "falkordb"
    be = FalkorDBBackend.connect(cfg, "integration-test")
    ingest.ingest_company(be)
    yield be
    be.clear()


def test_live_ingest_and_qa(fbe):
    assert len(fbe.find_nodes("Person")) == 48
    r = qa.answer_question(fbe, "Who owns the Atlas Billing Platform?")
    assert "Priya Nair" in r["answer"] and r["evidence"]


def test_live_cross_agent_handoff(fbe):
    agents.run_session1(fbe)
    out = agents.run_session2(fbe)
    assert out["reports"] and "November 18" in out["reports"][0]["answer"]
