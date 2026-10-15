"""SESSION 1 (run as its own process): the Researcher is taught a briefing,
the Planner plans and files a handoff to the Executor. Then this process exits.
Everything it knew is in the graph — run session2_execute.py next, in a fresh
process, to watch a different agent act on it.

Usage: python scripts/session1_teach.py [tenant]
"""
import sys

from _common import load_backend, persist

from crew_memory import agents


def main():
    tenant = sys.argv[1] if len(sys.argv) > 1 else "meridian"
    cfg, be = load_backend(tenant)
    out = agents.run_session1(be)
    persist(cfg, be, tenant)
    print("Session 1 complete.")
    print(f"  facts written : {len(out['facts'])}")
    print(f"  procedure     : {out['procedure']}")
    print(f"  handoff       : {out['handoff']} (open, addressed to Executor)")
    print("This process now exits. Session 2 starts cold.")


if __name__ == "__main__":
    main()
