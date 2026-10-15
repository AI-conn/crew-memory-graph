"""Seed the synthetic company into a tenant graph.

Usage: python scripts/seed_demo.py [tenant]
Backend comes from env (APP_GRAPH_BACKEND / FALKORDB_*); default is the
in-memory dev backend with a JSON snapshot under data/.
"""
import sys

from _common import load_backend, persist

from crew_memory import ingest
from crew_memory.memory import MemoryService


def main():
    tenant = sys.argv[1] if len(sys.argv) > 1 else "meridian"
    cfg, be = load_backend(tenant)
    counts = ingest.ingest_company(be)
    MemoryService(be)  # ensure crew agent nodes exist
    persist(cfg, be, tenant)
    print(f"Seeded tenant '{tenant}' on backend '{be.name}': {counts}")


if __name__ == "__main__":
    main()
