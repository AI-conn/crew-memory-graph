# Crew Memory Graph — Design

**Event:** Graph Hacks: Context for AI Agents (WeMakeDevs × FalkorDB). Rules: `rules-snapshot.md` in this folder.
**Deadline:** Sun Oct 18, 2026, 8:29 AM HST. **Build cap:** 2 build-days (the entrant). **Build window:** all code here is new, written in-window.
**Tracks entered with this one project (multi-track explicitly allowed):**
- **Track 02 — Agent Memory and Coordination** (concept home)
- **Track 03 — Company Brain** (entered for the Track 03 prize: M6 Mac Mini)

## 1. What it is

A three-agent crew — **Planner, Researcher, Executor** — whose shared brain is a single
FalkorDB graph per tenant. The crew never passes context through prompts alone: everything it
learns, decides, plans, and hands off is written into the graph, and everything it later does
is read back out of the graph by traversal. Remove FalkorDB and the crew has no memory, no
shared state, and no company knowledge — the graph is load-bearing by construction (the
organizers' own test for the mandatory-tech rule).

The graph carries three memory layers:

| Layer | Contents | Example nodes |
|---|---|---|
| **Episodic** | What happened: sessions, actions, observations, questions asked | `Session`, `Episode`, `Handoff` |
| **Semantic** | What is true: the company — people, teams, projects, documents, tickets, decisions, topics — plus facts the crew has learned | `Person`, `Team`, `Project`, `Document`, `Ticket`, `Decision`, `Topic`, `Fact` |
| **Procedural** | How we do things: reusable workflows the crew records and replays | `Procedure`, `Step` |

## 2. Demo spine

1. **Session 1 (process A):** the Researcher is *taught* a project briefing (facts + a decision
   and its rationale). The Planner turns a goal into a step plan. Both write to the graph.
   The Planner files a **Handoff** to the Executor referencing the exact memory nodes.
2. **Session 2 (process B — fresh process, empty prompt context):** the Executor boots, reads
   its open Handoffs from the graph, follows the referenced memory nodes, and **answers
   questions and carries out the next plan step using only what Session 1 wrote**. The UI
   renders the memory path it traversed — the proof is the path.

Company Q&A runs on the same graph: the semantic layer is seeded with a synthetic company
(48 people, 6 teams, 8 projects, 120+ docs/tickets/decisions/chat threads, procedurally
generated from a fixed seed and **labeled synthetic in the UI**). Questions like
*who owns X?*, *who decided Y, and why?*, *who knows about Z?* are answered by graph
traversal, and every answer ships with its **evidence path** — the actual chain of nodes and
relationships the answer came from, rendered in the UI and returned by the API.

## 3. Architecture

```
                 ┌──────────────────────────────────────────────┐
  Browser UI ───▶│ Flask app (server.py)                        │
                 │  /api/ask  /api/teach  /api/handoffs         │
                 │  /api/graph  /api/memory  /api/status        │
                 └───────┬──────────────────┬───────────────────┘
                         │                  │
                 ┌───────▼───────┐  ┌───────▼────────┐
                 │ Crew agents   │  │ Query planner  │  pattern-based NL → traversal plan
                 │ Planner       │  │ (planner.py)   │  (deterministic core; no API key
                 │ Researcher    │  │ Q&A (qa.py)    │   needed; optional LLM hook unused
                 │ Executor      │  └───────┬────────┘   by default)
                 └───────┬───────┘          │
                 ┌───────▼──────────────────▼───────────────────┐
                 │ MemoryService (memory.py)                    │
                 │ episodic / semantic / procedural read+write, │
                 │ handoffs, provenance on every write          │
                 └───────┬──────────────────────────────────────┘
                 ┌───────▼──────────────────────────────────────┐
                 │ GraphBackend (graphdb.py) — ONE interface    │
                 │  • FalkorDBBackend — real Cypher via the     │
                 │    official `falkordb` Python client         │
                 │  • MemoryBackend — in-memory dev/test        │
                 │    backend (file-snapshot persistence),      │
                 │    used by tests and offline dev ONLY, and   │
                 │    labeled as such wherever it appears       │
                 └───────┬──────────────────────────────────────┘
                         │ env: FALKORDB_HOST/PORT/USER/PASS
                 ┌───────▼──────────────────────────────────────┐
                 │ FalkorDB (Cloud free tier for the hosted     │
                 │ demo; self-host via one docker command)      │
                 │ One graph per tenant: crewmem_<tenant>       │
                 └──────────────────────────────────────────────┘
```

**Why a backend interface instead of hard-coding the client everywhere:** the build VM has no
Docker and no FalkorDB server, so the FalkorDB path cannot be executed here (stated honestly in
the README). The interface keeps every Cypher statement in one file (`graphdb.py`), where the
generated Cypher is unit-tested as strings, and an integration test-suite runs the *same* tests
against a live FalkorDB when `FALKORDB_HOST` is set (skipped, with reason, when it is not).
Tenant separation is by **separate FalkorDB graphs**, not a property filter — isolation is
structural, and a test proves tenant B cannot see tenant A's nodes on either backend.

## 4. Graph schema (semantic layer core)

- `(Person)-[:MEMBER_OF]->(Team)`, `(Person)-[:WORKS_ON {role}]->(Project)`
- `(Person)-[:OWNS]->(Project|Document)`, `(Person)-[:AUTHORED]->(Document)`
- `(Project)-[:HAS_DECISION]->(Decision)`, `(Decision)-[:MADE_BY]->(Person)`,
  `(Decision)-[:DOCUMENTED_IN]->(Document)`, `(Decision)-[:ABOUT]->(Topic)`
- `(Person)-[:KNOWS_ABOUT {strength, evidence}]->(Topic)` — strength derived at ingest from
  authored docs, resolved tickets, and decisions made; the *evidence* is real graph paths.
- `(Ticket)-[:FOR_PROJECT]->(Project)`, `(Ticket)-[:ASSIGNED_TO|RESOLVED_BY]->(Person)`
- `(ChatThread)-[:DISCUSSES]->(Project|Decision)`, `(Document)-[:REFERENCES]->(Decision|Project)`
- `(Project)-[:DEPENDS_ON]->(Project)`
- Memory: `(Agent)-[:WROTE]->(Fact|Episode|Procedure)`, `(Fact)-[:ABOUT]->(entity)`,
  `(Handoff)-[:FROM_AGENT|:TO_AGENT]->(Agent)`, `(Handoff)-[:REFERENCES]->(memory node)`,
  `(Episode)-[:IN_SESSION]->(Session)`, every memory node carries `agent`, `session_id`,
  `created_at`, and `source` properties (provenance).

## 5. Query planner (deterministic core)

Pattern intents, each compiling to a named traversal plan executed by the backend:
`who_owns`, `who_decided`, `why_decided`, `who_knows`, `who_works_on`, `team_of`,
`decisions_about`, `depends_on`, `what_is`, `recall_memory` ("what did we learn about X"),
`open_handoffs`. Entities are resolved against the graph's own names/titles (longest-match,
case-insensitive), so the planner works on any tenant's data with no retraining and no API key.
Every plan returns rows **plus** the evidence path(s) that produced them; the answer composer
cites the path in text form and the API returns it as a subgraph for visualization.

## 6. Priority order under the 2-day cap

1. FalkorDB-central memory write/read across sessions + per-tenant graphs. ✅ spine
2. Handoff demo (agent B acts on agent A's memory, fresh process). ✅ spine
3. Company-knowledge Q&A with evidence paths (Track 03 surface). ✅
4. UI polish. (As far as time allows; shrink this first, never 1–2.)

## 7. Honesty rules for this build

- Synthetic dataset is labeled synthetic in the UI and README. No invented metrics anywhere;
  benchmark numbers in the README are the real output of `benchmark/run_benchmark.py`.
- If FalkorDB is not connected, the UI shows a visible **"Offline dev mode — in-memory graph
  (not FalkorDB)"** banner; it never pretends the dev backend is FalkorDB.
- Executor "actions" are workflow artifacts recorded in the graph (drafts, tickets, plan
  steps) — real inside the system, never described as external-world actions.
- Live-FalkorDB verification status is stated in the README's state section, not implied.

## 8. Remaining-to-submission (known follow-ups, not part of this build)

- Point the host at the FalkorDB Cloud free-tier instance (`FALKORDB_*` env) and run the
  integration suite against it (one command) — turns the FalkorDB path from Cypher-verified to live-verified.
- Host the demo (HF Spaces or any host that can reach FalkorDB Cloud); record demo video if
  the live deployment fails (rules: live preferred, else full local setup + video).
- WeMakeDevs registration/submission panel (handled separately).

