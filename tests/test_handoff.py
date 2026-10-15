"""The core claim of the product: agent B, constructed fresh, acts on memory
agent A wrote — with no shared process state."""
from crew_memory import agents
from crew_memory.memory import MemoryService


def test_cross_agent_handoff(be):
    out1 = agents.run_session1(be)
    assert len(out1["facts"]) == 3

    # Fresh agent + fresh service objects: nothing carried in Python state.
    out2 = agents.run_session2(be)
    assert len(out2["reports"]) == 1
    rep = out2["reports"][0]
    assert "November 18" in rep["answer"]
    assert "400 workspaces" in rep["answer"]
    assert rep["step_done"] == "Draft the launch checklist from the briefing facts"
    assert rep["memory_path"][0] == out1["handoff"]
    assert "fact:" in " ".join(rep["memory_path"])

    mem = MemoryService(be)
    assert mem.open_handoffs("executor") == []  # handoff closed by the Executor
    done = be.get_node(out1["handoff"])
    assert done["props"]["status"] == "done"

    steps = mem.procedure_steps(out1["procedure"])
    assert steps[0]["props"]["done"] is True
    assert steps[1]["props"]["done"] is False

    # A second cold run finds nothing to do — state really lives in the graph.
    out3 = agents.run_session2(be)
    assert out3["reports"] == []
