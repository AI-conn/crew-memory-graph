import os

from crew_memory.graphdb import MemoryBackend
from crew_memory.memory import MemoryService


def test_fact_write_read_with_provenance(be):
    mem = MemoryService(be)
    sid = mem.start_session("researcher")
    fid = mem.learn_fact("researcher", sid, "Beacon ships in November.",
                         about=["project:beacon-mobile-app"], kind="decision")
    fact = be.get_node(fid)
    assert fact["props"]["agent"] == "researcher"
    assert fact["props"]["session"] == sid
    assert fact["props"]["layer"] == "semantic"
    about = mem.facts(about_uid="project:beacon-mobile-app")
    assert any(f["uid"] == fid for f in about)


def test_episodes_recorded(be):
    mem = MemoryService(be)
    sid = mem.start_session("planner")
    eps = mem.episodes(session_id=sid)
    assert eps and eps[0]["props"]["kind"] == "session_start"
    assert eps[0]["props"]["layer"] == "episodic"


def test_procedure_steps_and_completion(be):
    mem = MemoryService(be)
    sid = mem.start_session("planner")
    pid = mem.record_procedure("planner", sid, "Plan: X", ["step one", "step two"])
    steps = mem.procedure_steps(pid)
    assert [s["props"]["text"] for s in steps] == ["step one", "step two"]
    mem.mark_step_done(steps[0]["uid"])
    steps = mem.procedure_steps(pid)
    assert steps[0]["props"]["done"] is True
    assert steps[1]["props"]["done"] is False


def test_persistence_across_instances(tmp_path):
    be1 = MemoryBackend()
    mem1 = MemoryService(be1)
    sid = mem1.start_session("researcher")
    fid = mem1.learn_fact("researcher", sid, "Persisted across processes.")
    path = str(tmp_path / "snap.json")
    be1.save(path)

    be2 = MemoryBackend()
    be2.load(path)
    mem2 = MemoryService(be2)  # a "new process" view of the same memory
    assert be2.get_node(fid) is not None
    assert any("Persisted" in f["props"]["text"] for f in mem2.facts())
    assert os.path.exists(path)
