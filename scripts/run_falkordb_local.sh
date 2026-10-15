#!/usr/bin/env bash
# One-command FalkorDB for the demo environment (any machine with Docker),
# then verify the whole system against the live server.
set -euo pipefail

docker run -d --name crewmem-falkordb -p 6379:6379 falkordb/falkordb:latest
echo "Waiting for FalkorDB..."
for i in $(seq 1 30); do
  if docker exec crewmem-falkordb redis-cli ping >/dev/null 2>&1; then break; fi
  sleep 1
done

cd "$(dirname "$0")/.."
export APP_GRAPH_BACKEND=falkordb FALKORDB_HOST=localhost FALKORDB_PORT=6379

python -m pytest tests/test_falkor_integration.py -v   # live ingest + QA + handoff
python benchmark/run_benchmark.py                       # scored against FalkorDB
python scripts/seed_demo.py                             # seed the demo tenant
echo "Now start the UI with the same env:  python run.py"
