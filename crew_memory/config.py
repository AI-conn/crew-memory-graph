"""Environment-driven configuration.

The graph connection is a single config surface: set APP_GRAPH_BACKEND and the
FALKORDB_* variables to point the whole system at FalkorDB Cloud or a self-hosted
instance. Nothing else in the codebase reads connection details.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    backend: str = "memory"  # "falkordb" | "memory"
    falkor_host: str = "localhost"
    falkor_port: int = 6379
    falkor_username: str | None = None
    falkor_password: str | None = None
    graph_prefix: str = "crewmem"
    default_tenant: str = "meridian"
    snapshot_dir: str = "data"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            backend=os.environ.get("APP_GRAPH_BACKEND", "memory").lower(),
            falkor_host=os.environ.get("FALKORDB_HOST", "localhost"),
            falkor_port=int(os.environ.get("FALKORDB_PORT", "6379")),
            falkor_username=os.environ.get("FALKORDB_USERNAME") or None,
            falkor_password=os.environ.get("FALKORDB_PASSWORD") or None,
            graph_prefix=os.environ.get("GRAPH_PREFIX", "crewmem"),
            default_tenant=os.environ.get("DEFAULT_TENANT", "meridian"),
            snapshot_dir=os.environ.get("SNAPSHOT_DIR", "data"),
        )

    def graph_name(self, tenant: str) -> str:
        return f"{self.graph_prefix}_{tenant}"
