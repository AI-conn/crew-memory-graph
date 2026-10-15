import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pytest

from crew_memory import ingest
from crew_memory.graphdb import MemoryBackend


@pytest.fixture()
def be():
    backend = MemoryBackend()
    ingest.ingest_company(backend)
    return backend


@pytest.fixture()
def empty_be():
    return MemoryBackend()
