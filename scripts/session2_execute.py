"""SESSION 2 (run as its own process, after session1_teach.py): a brand-new
Executor boots with empty context, finds the open handoff IN THE GRAPH,
follows its references, answers the handoff question from memory written by
other agents, performs the next plan step, and closes the handoff.

Usage: python scripts/session2_execute.py [tenant]
"""
import sys

from _common import load_backend, persist

from crew_memory import agents


def main():
    tenant = sys.argv[1] if len(sys.argv) > 1 else "meridian"
    cfg, be = load_backend(tenant)
    out = agents.run_session2(be)
    persist(cfg, be, tenant)
    if not out["reports"]:
        print("No open handoffs for the Executor. Run session1_teach.py first.")
        return
    for rep in out["reports"]:
        print("Session 2 — Executor report")
        print(f"  handoff      : {rep['handoff']}")
        print(f"  memory path  : {' -> '.join(rep['memory_path'])}")
        print(f"  question     : {rep['question']}")
        print(f"  answer       : {rep['answer']}")
        print(f"  step done    : {rep['step_done']}")
        print(f"  result filed : {rep['result']}")


if __name__ == "__main__":
    main()
