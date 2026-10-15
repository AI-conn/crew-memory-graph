"""Benchmark runner: scores the Q&A engine against frozen ground-truth
expectations (questions.json), derived from the seeded synthetic dataset.

Checks per question: the engine answered, every expected string appears, an
optional ordering pair is respected, and at least one evidence path reaches
the required node count (the multi-hop proof).

Usage: python benchmark/run_benchmark.py
Backend from env: default in-memory dev backend; set APP_GRAPH_BACKEND=
falkordb + FALKORDB_* to score against a live FalkorDB.
Exits non-zero if any question fails.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from crew_memory import agents, ingest, qa
from crew_memory.config import Config
from crew_memory.graphdb import backend_for_tenant
from crew_memory.memory import MemoryService


def check(res: dict, spec: dict) -> list[str]:
    problems = []
    if not res.get("answered"):
        problems.append("engine declined to answer")
    ans = res.get("answer", "")
    for needle in spec.get("contains", []):
        if needle not in ans:
            problems.append(f"missing {needle!r}")
    before = spec.get("before")
    if before and all(b in ans for b in before):
        if ans.index(before[0]) > ans.index(before[1]):
            problems.append(f"ordering: {before[0]!r} should precede {before[1]!r}")
    longest = max((len(p["nodes"]) for p in res.get("evidence", [])), default=0)
    if longest < spec.get("min_path_nodes", 0):
        problems.append(f"longest evidence path {longest} nodes < required "
                        f"{spec.get('min_path_nodes')}")
    return problems


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    specs = json.load(open(os.path.join(here, "questions.json")))
    cfg = Config.from_env()
    be = backend_for_tenant(cfg, "benchmark")
    ingest.ingest_company(be)
    MemoryService(be)
    print(f"Backend: {be.name} | nodes: {be.node_count()} | edges: {be.edge_count()}")

    results = []
    taught = False
    for spec in specs:
        if spec.get("needs_teach") and not taught:
            agents.run_session1(be)
            taught = True
        res = qa.answer_question(be, spec["question"], memory=MemoryService(be))
        problems = check(res, spec)
        results.append((spec, problems))
        status = "PASS" if not problems else "FAIL"
        print(f"[{status}] {spec['id']} ({spec['hops']}-hop) {spec['question']}")
        for p in problems:
            print(f"       - {p}")

    passed = sum(1 for _, probs in results if not probs)
    multi = [r for r in results if r[0]["hops"] >= 2]
    multi_passed = sum(1 for s, probs in multi if not probs)
    print(f"\nSCORE: {passed}/{len(results)} questions passed "
          f"({multi_passed}/{len(multi)} multi-hop)")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
