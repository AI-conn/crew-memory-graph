# Crew Memory Graph

**One FalkorDB graph as the shared brain of a multi-agent crew — and the company brain it works in.**

**Live demo:** [https://crew-memory-graph.onrender.com](https://crew-memory-graph.onrender.com)

A three-agent crew (**Planner · Researcher · Executor**) that never passes context through
prompts. Everything the crew learns, plans, decides, and hands off is written into a FalkorDB
graph; everything it later does is read back out by traversal. The same graph's semantic layer
holds the whole company — people, teams, projects, documents, tickets, decisions — so the crew
also answers *"who owns X?"*, *"who decided Y, and why?"*, *"who knows about Z?"* — and shows
the **evidence path** behind every answer.

Built for **Graph Hacks: Context for AI Agents** (WeMakeDevs × FalkorDB), entered in
**Track 02 — Agent Memory and Coordination** and **Track 03 — Company Brain**.

## Live demo

**Live demo:** _deployment URL is added here when the hosted demo goes live — it
deploys against the project's FalkorDB Cloud free-tier instance during the
submission window._ Until the URL lands, the Quickstart below runs the complete
demo locally (same code, same seed data, same two-session handoff), and
`scripts/run_falkordb_local.sh` runs it end-to-end against a real FalkorDB.

## Why the graph is the product (the removal test)

Remove FalkorDB and nothing remains: no memory between sessions, no shared state between
agents, no company knowledge, no evidence paths. Agents are deliberately stateless — a new
agent process boots with an empty context and works purely from what it traverses. State lives
in exactly one place: the graph.

## The three memory layers

| Layer | Question it answers | Nodes |
|---|---|---|
| **Episodic** | What happened? | `Session`, `Episode`, `Handoff` |
| **Semantic** | What is true? | `Person`, `Team`, `Project`, `Document`, `Ticket`, `Decision`, `Topic`, `ChatThread`, learned `Fact`s |
| **Procedural** | How do we do things? | `Procedure`, `Step` |

Every memory write carries provenance: `agent`, `session`, `created_at`, `source`.
One FalkorDB graph **per tenant** (`crewmem_<tenant>`) — tenant isolation is structural
(separate graphs), not a property filter, and a test proves it.

## Graph data model

One FalkorDB graph **per tenant**, named `crewmem_<tenant>` — isolation is a
separate graph, never a filter. Every node carries a `uid` property (its merge
key); every memory write additionally carries provenance properties: `agent`,
`session`, `created_at`, `source`.

**Node labels, by layer:**

| Layer | Labels |
|---|---|
| Episodic | `Session`, `Episode`, `Handoff`, `Agent` |
| Semantic | `Person`, `Team`, `Project`, `Document`, `Ticket`, `Decision`, `Topic`, `ChatThread`, `Fact` |
| Procedural | `Procedure`, `Step` |

**Relationship types (the full schema whitelist — traversals may only use these):**

`MEMBER_OF` · `WORKS_ON {role}` · `OWNS` · `AUTHORED` · `HAS_DECISION` ·
`MADE_BY` · `DOCUMENTED_IN` · `ABOUT` · `KNOWS_ABOUT {strength, evidence}` ·
`FOR_PROJECT` · `ASSIGNED_TO` · `RESOLVED_BY` · `DISCUSSES` · `REFERENCES` ·
`DEPENDS_ON` · `PART_OF` · `WROTE` · `IN_SESSION` · `FROM_AGENT` · `TO_AGENT` ·
`HAS_STEP` · `NEXT_STEP` · `LEARNED_IN` · `MENTIONS`

Core shapes: `(Person)-[:MEMBER_OF]->(Team)`, `(Person)-[:WORKS_ON]->(Project)`,
`(Project)-[:HAS_DECISION]->(Decision)-[:MADE_BY]->(Person)`,
`(Decision)-[:DOCUMENTED_IN]->(Document)`, `(Project)-[:DEPENDS_ON]->(Project)`,
`(Handoff)-[:REFERENCES]->(memory node)`, `(Fact)-[:ABOUT]->(entity)`.

## The demo (the whole pitch in two clicks)

1. **Session 1 — teach & hand off.** The Researcher is taught a launch briefing for the
   Beacon Mobile App (a launch-date decision, the beta cohort size, a blocker). The Planner
   converts it into a step plan (procedural memory) and files a **Handoff** to the Executor
   that *references the exact memory nodes* — no text is passed agent-to-agent.
2. **Session 2 — a fresh Executor acts.** A brand-new agent, empty context, finds the open
   handoff by traversal, follows its `REFERENCES` edges, answers the handoff's question from
   Session 1's memory, performs the next plan step, and closes the handoff with the result —
   all recorded as new episodes. The UI shows the memory path it walked.

The same flow runs headless, as genuinely separate processes:

```bash
python scripts/seed_demo.py        # ingest the synthetic company
python scripts/session1_teach.py   # process A: teach + plan + handoff, then exits
python scripts/session2_execute.py # process B: cold start, acts from the graph alone
```

## Company Q&A with evidence paths

A deterministic, pattern-based query planner (no LLM, no API key, nothing to hallucinate)
resolves entities against the graph's own names and compiles each question into traversals:
`who_owns`, `who_decided`, `why_decided`, `who_knows`, `who_works_on`, `team_of`,
`decisions_about`, `depends_on`, `what_is`, `recall_memory`. Answers cite the actual chain —
e.g. `Pulse Analytics —DEPENDS_ON→ Atlas Billing —DEPENDS_ON→ Vertex API Gateway`, or
`Project —HAS_DECISION→ Decision —MADE_BY→ Person` — rendered in the UI and returned by the API.
Expertise is *derived*, not asserted: `KNOWS_ABOUT` strength is computed from authored
documents, decisions made, and tickets resolved, and each edge keeps its evidence count.

## Dataset

A synthetic mid-size company, **Meridian Labs** (labeled synthetic in the UI): 48 people,
6 teams, 8 projects, 12 topics, 32 documents, 8 decisions with rationales and source docs,
48 tickets, 20 chat threads — 108 artifacts, procedurally generated from a fixed seed around
a hand-fixed core, so questions have exact, checkable ground truth.

## Architecture

```
Browser UI ─▶ Flask API ─▶ Crew agents (Planner / Researcher / Executor)
                        ─▶ Query planner + Q&A (evidence paths)
                        ─▶ MemoryService (episodic / semantic / procedural, handoffs)
                        ─▶ GraphBackend — one interface, all Cypher in graphdb.py
                             • FalkorDBBackend — official `falkordb` client, parameterized Cypher
                             • MemoryBackend — in-memory DEV backend (tests/offline only,
                               snapshot-persisted, labeled wherever it appears)
                        ─▶ FalkorDB — one graph per tenant
```

The backend interface exists for one honest reason: the build machine has no Docker and no
FalkorDB server, so the FalkorDB path is verified by Cypher unit tests (generated statements +
parameter discipline + a recording fake client) and by a live integration suite that runs the
same assertions when a server is present. It is never disguised: if you run the app without
FalkorDB configured, the UI shows an **"Offline dev mode — in-memory graph (not FalkorDB)"**
banner.

## Cypher queries & graph algorithms

All Cypher lives in one module (`crew_memory/graphdb.py`) behind the backend
interface. **Every value is a query parameter**; node labels and relationship
types are interpolated only from the schema whitelist above (they cannot be
parameters in Cypher), and any non-whitelisted type raises before a query is
built.

**Write path — parameterized upserts:**

```cypher
MERGE (n:Label {uid: $uid}) SET n += $props RETURN n.uid
MATCH (a {uid: $src}), (b {uid: $dst})
MERGE (a)-[r:TYPE]->(b) SET r += $props RETURN type(r)
```

**Read path — composed path traversals.** Each question compiles to a list of
`(relationship, direction)` steps; the builder composes one path pattern and
returns the node chain — that chain *is* the answer's evidence path:

```cypher
MATCH path = (n0 {uid: $start})-[r0:HAS_DECISION]->(n1)-[r1:MADE_BY]->(n2)
RETURN [x IN nodes(path) | x.uid] AS uids,
       [r IN relationships(path) | type(r)] AS rels
```

Neighbor lookups (`MATCH (a {uid: $uid})-[r:TYPE]->(b) ...`) and case-folded
text search (`toLower(n.name) CONTAINS $q` over name/title/summary/text/goal)
cover the remaining reads.

**Intent → traversal plans** (deterministic planner, no LLM): `who_owns` →
`OWNS` in-edges; `who_decided` / `why_decided` → `HAS_DECISION` then `MADE_BY`
(and `DOCUMENTED_IN` for the source document); `who_knows` → `KNOWS_ABOUT`
ranked by strength; `depends_on` → repeated `DEPENDS_ON` out-steps;
`recall_memory` → learned `Fact` nodes and their `ABOUT` targets.

**Algorithms:**

- **Derived expertise.** `KNOWS_ABOUT` is computed at ingest, never asserted:
  strength(person, topic) starts from any recorded-assertion floor, then
  **+2 per authored document** on the topic, **+2 per decision made** on it,
  **+1 per resolved ticket** on it. Edges are written only at strength ≥ 2,
  stored strength is capped at 5, and each edge keeps its `evidence` count —
  the number of artifacts behind the claim, all reachable as graph paths.
- **Evidence-path composition.** Answers cite the exact traversal chain
  (e.g. `Pulse Analytics —DEPENDS_ON→ Atlas Billing —DEPENDS_ON→ Vertex API
  Gateway`); the benchmark rejects answers whose evidence path is shorter
  than the question's required hop count.
- **Entity resolution.** Question entities are matched against the graph's own
  names and titles — longest match, case-insensitive — so the planner works on
  any tenant's graph with no retraining and no API key.

## Quickstart

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py            # http://localhost:7860  (auto-seeds the demo company)
```

### Run it on FalkorDB (the real deployment)

Self-hosted, one command (any machine with Docker):

```bash
bash scripts/run_falkordb_local.sh   # starts FalkorDB, runs live integration tests + benchmark, seeds
APP_GRAPH_BACKEND=falkordb FALKORDB_HOST=localhost .venv/bin/python run.py
```

FalkorDB Cloud free tier: create an instance, then set
`APP_GRAPH_BACKEND=falkordb`, `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_USERNAME`,
`FALKORDB_PASSWORD` from your instance page (see `.env.example`). No code changes — the
connection is one config surface.

## Tests & benchmark (measured, reproducible)

```bash
.venv/bin/python -m pytest tests/ -q        # 25 passed, 2 skipped
.venv/bin/python benchmark/run_benchmark.py # SCORE: 14/14 (8/8 multi-hop)
```

- 25 unit tests cover generation, ingestion, expertise derivation, memory layers,
  cross-agent handoff, planner, Q&A, and the FalkorDB Cypher builders. The 2 skipped tests
  are the live-FalkorDB integration suite (`tests/test_falkor_integration.py`), gated on
  `FALKORDB_HOST` because this build VM has no FalkorDB server.
- The benchmark freezes 14 questions with expected answers (8 of them multi-hop, verified by
  minimum evidence-path length) and scores the engine end-to-end. **The numbers above were
  measured on the in-memory dev backend in this environment**; `run_benchmark.py` scores
  against live FalkorDB unchanged when the env points at one.

## Project state (honest)

- ✅ Complete and tested locally: ingestion, memory layers, handoffs, cross-process demo,
  Q&A with evidence paths, web UI, benchmark.
- ✅ **Live:** the app is deployed and live at
  [https://crew-memory-graph.onrender.com](https://crew-memory-graph.onrender.com), backed by
  FalkorDB Cloud.
- ✅ **FalkorDB backend is live:** graph `crewmem_meridian` on FalkorDB Cloud is
  seeded on boot with 186 nodes / 564 edges, and seed-on-boot is idempotent.
- ✅ **Verified live:** `/api/status` on the live site confirms backend "falkordb".
  That confirms the hosted app is running against FalkorDB, not the dev backend.
- Remaining to submission: the demo video, then the entry form — hosted
  deployment on FalkorDB Cloud is complete, as the bullets above confirm.

## AI assistance disclosure

Built with an AI coding assistant, as the Graph Hacks rules expressly allow
(also stated in `SUBMISSION.md`). The architecture, graph schema, honesty
constraints (synthetic data labeled, dev backend labeled, no invented
metrics), and every verification step are the entrant's own design and
responsibility; all claims in this README are limited to what the test suite
and benchmark actually measure.

## Layout

```
crew_memory/  config.py graphdb.py synthetic.py ingest.py memory.py
              planner.py qa.py agents.py server.py templates/index.html
scripts/      seed_demo.py session1_teach.py session2_execute.py run_falkordb_local.sh
benchmark/    questions.json run_benchmark.py
tests/        8 test files (unit, cypher, live-integration)
```
