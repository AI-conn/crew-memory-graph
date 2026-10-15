"""Entry point: python run.py  (PORT env, default 7860)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crew_memory.config import Config
from crew_memory.server import create_app

if __name__ == "__main__":
    cfg = Config.from_env()
    create_app(cfg).run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
