# Graph Hacks Submission — Crew Memory Graph

**Project:** Crew Memory Graph
**Tracks:** Track 02 — Agent Memory and Coordination · Track 03 — Company Brain
**Stack:** Python · FalkorDB (Cypher) · Flask · vanilla JS/SVG visualization

## The problem

Multi-agent systems today pass context through prompts: long, lossy, and gone when the process
ends. Agent A learns something on Monday; agent B, in a new session on Tuesday, knows none of
it. And inside companies, the knowledge agents need — who owns what, who decided what and why,
who actually knows a topic — is scattered across docs, tickets, and chat threads that no agent
can traverse. Keyword search finds words; it cannot follow the chain
*project → decision → decider → source document* that makes an answer trustworthy.

## The solution

Give the crew **one shared brain that is a graph**. A Planner, a Researcher, and an Executor
work over a single FalkorDB graph per tenant, organized in three memory layers:

- **Episodic** — sessions, episodes, and handoffs: what happened, in order, with provenance.
- **Semantic** — the company itself (people, teams, projects, documents, tickets, decisions,
  topics, chat threads) plus every fact the crew learns, linked to the entities it is about.
- **Procedural** — plans and workflows as step graphs the crew records and replays.

Agents are stateless by design. A new agent process boots empty and works purely by traversal:
it finds its open handoffs, follows their `REFERENCES` edges to the memory other agents wrote,
answers and acts from that memory, and writes its results back as new episodes. The graph is
not a sidecar — remove FalkorDB and the crew has no memory, no shared state, and no company
knowledge at all.

## How FalkorDB is used (central, load-bearing)

- **All state is the graph.** Memory writes/reads, handoffs, plans, and company Q&A are
  Cypher traversals through one data-access layer (`crew_memory/graphdb.py`); values are
  always query parameters, relationship types are schema-whitelisted.
- **One graph per tenant** (`crewmem_<tenant>`) — isolation is structural.
- **Evidence paths are query results, not decorations:** decision answers compose
  `Project —HAS_DECISION→ Decision —MADE_BY→ Person` and `—DOCUMENTED_IN→ Document` chains;
  dependency answers return multi-hop `DEPENDS_ON` chains.
- **Expertise is derived by the graph:** `KNOWS_ABOUT` strength is computed at ingest from
  authored documents, decisions made, and tickets resolved, with the supporting artifacts
  kept reachable as paths.

## Track 02 — Agent Memory and Coordination (how we address the brief)

- *Episodic, semantic, and procedural memory* — three explicit layers, separate node families,
  one graph (see the memory-layer browser in the UI).
- *Persistent conversation history* — sessions and episodes are graph nodes with provenance
  (agent, session, timestamp, source); a fresh process reads the full history by traversal.
- *Shared state and handoffs between agents* — the demo's spine: Session 1's Researcher and
  Planner write a briefing, a plan, and a handoff; Session 2's Executor — a different agent in
  a different process — answers the handoff's question from that memory and performs the next
  plan step. No prompt ever carries the context.
- *Separate memory per user or tenant* — separate FalkorDB graphs per tenant, with a test
  proving tenant B sees none of tenant A's memory.
- *Memory that updates over time* — handoffs open and close, plan steps complete, new facts
  attach to entities; recall reflects the latest state because it is queried, not copied.

## Track 03 — Company Brain (how we address the brief)

- *Knowledge from docs, tickets, and chats in one graph* — the seeded company carries
  32 documents, 48 tickets, 20 chat threads, and 8 decisions, all interconnected with the
  48 people, 6 teams, and 8 projects they belong to.
- *Who owns what and who knows what* — `OWNS`, `WORKS_ON`, and derived `KNOWS_ABOUT`
  traversals; "who knows about data pipelines?" returns a strength-ranked answer with the
  supporting artifacts behind each name.
- *Tracing decisions back to their source* — every decision links to its decider, its
  rationale, its documenting document, and the chat threads that discussed it; "why did we
  decide…?" returns the whole chain.
- *Answers with clear sources* — every answer ships its evidence path (also returned via the
  API as a subgraph and highlighted in the visualization).
- *Keeping knowledge current* — the crew keeps learning into the same graph: teach it a fact
  in the UI and "what did the crew learn about X?" answers from memory immediately.

## Demo script (for judges, ~3 minutes)

1. Open the app. Note the graph: ~180 nodes of one company, plus three agents.
2. Ask: *"Why did we decide to adopt usage-based pricing for Atlas?"* — watch the answer and
   the highlighted evidence chain (project → decision → decider → source document).
3. Ask: *"Who knows about data pipelines?"* and *"What does Pulse Analytics depend on?"*
4. Click **Session 1**: the Researcher learns a launch briefing; the Planner plans and files
   a handoff. Inspect the Handoffs card and the memory layers.
5. Click **Session 2**: a fresh Executor answers *"When is the Beacon launch, and how large is
   the beta cohort?"* — from Session 1's graph memory — performs the first plan step, and
   closes the handoff. The log shows the exact memory path traversed.
6. Teach the crew a new fact in the UI, then ask what it learned.

## Verification (measured, reproducible)

- 25 unit tests pass; 2 live-FalkorDB integration tests are env-gated (see README state
  section for the honest verification status of the FalkorDB path in this build environment).
- A frozen benchmark of 14 questions (8 multi-hop, checked by evidence-path length) scores
  **14/14** via `benchmark/run_benchmark.py`.
- Headless proof: `scripts/session1_teach.py` and `scripts/session2_execute.py` are separate
  processes; the second starts cold and acts only on graph state.

## What was built in-window

All of it: the graph schema and data-access layer, the synthetic-company generator, ingestion
with derived expertise, the memory service, the three agents and handoff protocol, the
deterministic query planner, the Q&A engine, the web UI with graph visualization, the test
suite, and the benchmark. General libraries only (Flask, the official FalkorDB client, pytest).

## On AI assistance

Built with an AI coding assistant, as the event rules expressly allow. The architecture, the
graph schema, the honesty constraints (synthetic data labeled, dev backend labeled, no
invented metrics), and every verification step are the entrant's design and responsibility —
and this document's claims are limited to what the test suite and benchmark actually measure.

## What's next

FalkorDB Cloud deployment for the hosted demo, an MCP tool surface over the same traversal
plans (Track 01's pattern), and ingestion connectors for real doc/ticket/chat sources behind
the same schema.
