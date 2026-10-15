"""Shared loader for the demo scripts: build the configured backend for a
tenant, restore its snapshot (memory backend), and persist after mutation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from crew_memory.config import Config
from crew_memory.graphdb import backend_for_tenant, snapshot_path


def load_backend(tenant: str):
    cfg = Config.from_env()
    be = backend_for_tenant(cfg, tenant)
    if cfg.backend == "memory":
        p = snapshot_path(cfg, tenant)
        if os.path.exists(p):
            be.load(p)
    return cfg, be


def persist(cfg, be, tenant: str):
    if cfg.backend == "memory":
        be.save(snapshot_path(cfg, tenant))
