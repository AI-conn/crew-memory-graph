"""MemoryService — the crew's read/write API over the three memory layers.

Every write carries provenance (agent, session, timestamp, source). Nothing an
agent "knows" lives in its process memory: sessions are cheap wrappers; the
graph is the state. A new MemoryService over the same backend — in a new
process — sees everything previous sessions wrote. That property is the
product, and it is what the handoff demo and the tests exercise.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

AGENTS = {
    "planner": {"name": "Planner", "role": "Decomposes goals into plans and files handoffs."},
    "researcher": {"name": "Researcher", "role": "Investigates and records facts and decisions."},
    "executor": {"name": "Executor", "role": "Carries out plan steps and reports results."},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uid(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:12]}"


# Ingest-side marker stripping (gate fix F-3c, 2026-10-16). Taught fact
# text later reaches an LLM prompt; instruction-shaped markers planted in
# it ("SYSTEM NOTICE:", "[SYSTEM]", "### System:", ...) were the P3
# probe's elevation vector. Stripping is deliberately narrow: it removes
# the marker tokens only, at line starts, and keeps the remaining text as
# an ordinary claim. It is one layer of F-3, not a sanitizer promise —
# the write gate (F-3a) and the prompt framing (F-3b) carry the rest.
_INSTRUCTION_MARKERS = re.compile(
    r"(?im)^[ \t]*(?:"
    r"#{1,6}[ \t]*system[ \t]*[:\-]?|"
    r"\[(?:system|sys)\][ \t]*[:\-]?|"
    r"<<\/?SYS>>[ \t]*|"
    r"system[ \t]+notice[ \t]*[:\-]|"
    r"system[ \t]*[:\-]"
    r")[ \t]*")


def sanitize_fact_text(text: str) -> str:
    """Remove instruction-shaped leading markers from taught fact text."""
    return _INSTRUCTION_MARKERS.sub("", text or "")


class MemoryService:
    def __init__(self, be):
        self.be = be
        for aid, meta in AGENTS.items():
            be.merge_node("Agent", f"agent:{aid}", {"name": meta["name"], "role": meta["role"]})

    # -- sessions / episodic --------------------------------------------
    def start_session(self, agent_id: str) -> str:
        sid = _uid("session")
        self.be.merge_node("Session", sid, {
            "agent": agent_id, "started_at": _now(), "kind": "session"})
        self.be.merge_edge(f"agent:{agent_id}", "WROTE", sid)
        self.log_episode(agent_id, sid, "session_start",
                         f"{AGENTS[agent_id]['name']} session started.")
        return sid

    def log_episode(self, agent_id: str, session_id: str, kind: str, text: str,
                    about: list[str] | None = None) -> str:
        eid = _uid("episode")
        self.be.merge_node("Episode", eid, {
            "kind": kind, "text": text, "agent": agent_id,
            "session": session_id, "created_at": _now(), "layer": "episodic"})
        self.be.merge_edge(eid, "IN_SESSION", session_id)
        self.be.merge_edge(f"agent:{agent_id}", "WROTE", eid)
        for a in about or []:
            self.be.merge_edge(eid, "ABOUT", a)
        return eid

    def episodes(self, session_id: str | None = None) -> list[dict]:
        # The session filter is pushed into the backend query (server-side
        # WHERE on the graph backend) instead of fetching every episode and
        # filtering in Python. Same result set, far fewer rows moved.
        if session_id:
            eps = self.be.find_nodes("Episode", session=session_id)
        else:
            eps = self.be.find_nodes("Episode")
        return sorted(eps, key=lambda e: e["props"].get("created_at", ""))

    # -- semantic memory (learned facts) ---------------------------------
    def learn_fact(self, agent_id: str, session_id: str, text: str,
                   about: list[str] | None = None, kind: str = "fact",
                   source: str = "briefing") -> str:
        fid = _uid("fact")
        self.be.merge_node("Fact", fid, {
            "text": sanitize_fact_text(text), "kind": kind,
            "agent": agent_id, "session": session_id,
            "source": source, "created_at": _now(), "layer": "semantic"})
        self.be.merge_edge(f"agent:{agent_id}", "WROTE", fid)
        self.be.merge_edge(fid, "LEARNED_IN", session_id)
        for a in about or []:
            self.be.merge_edge(fid, "ABOUT", a)
        return fid

    def facts(self, about_uid: str | None = None) -> list[dict]:
        if about_uid is None:
            return self.be.find_nodes("Fact")
        return [n for _, n in self.be.neighbors(about_uid, "ABOUT", "in")]

    # -- procedural memory -------------------------------------------------
    def record_procedure(self, agent_id: str, session_id: str, name: str,
                         steps: list[str], trigger: str = "") -> str:
        pid = _uid("procedure")
        self.be.merge_node("Procedure", pid, {
            "title": name, "name": name, "trigger": trigger, "agent": agent_id,
            "created_at": _now(), "layer": "procedural", "step_count": len(steps)})
        self.be.merge_edge(f"agent:{agent_id}", "WROTE", pid)
        prev = None
        for i, s in enumerate(steps):
            sid = f"{pid}:step-{i + 1}"
            self.be.merge_node("Step", sid, {"text": s, "order": i + 1, "done": False})
            self.be.merge_edge(pid, "HAS_STEP", sid)
            if prev:
                self.be.merge_edge(prev, "NEXT_STEP", sid)
            prev = sid
        return pid

    def procedures(self) -> list[dict]:
        return self.be.find_nodes("Procedure")

    def procedure_steps(self, procedure_uid: str) -> list[dict]:
        steps = [n for _, n in self.be.neighbors(procedure_uid, "HAS_STEP", "out")]
        return sorted(steps, key=lambda s: s["props"].get("order", 0))

    def mark_step_done(self, step_uid: str) -> None:
        self.be.set_props(step_uid, {"done": True})

    # -- handoffs ------------------------------------------------------------
    def create_handoff(self, from_agent: str, to_agent: str, session_id: str,
                       summary: str, references: list[str],
                       question: str | None = None) -> str:
        hid = _uid("handoff")
        self.be.merge_node("Handoff", hid, {
            "summary": summary, "question": question or "", "status": "open",
            "from_agent": from_agent, "to_agent": to_agent,
            "created_at": _now(), "layer": "episodic"})
        self.be.merge_edge(hid, "FROM_AGENT", f"agent:{from_agent}")
        self.be.merge_edge(hid, "TO_AGENT", f"agent:{to_agent}")
        self.be.merge_edge(f"agent:{from_agent}", "WROTE", hid)
        for r in references:
            self.be.merge_edge(hid, "REFERENCES", r)
        self.log_episode(from_agent, session_id, "handoff_created",
                         f"Handoff to {to_agent}: {summary}", about=references)
        return hid

    def open_handoffs(self, agent_id: str) -> list[dict]:
        # Both filters ride the backend query (was: status in the query,
        # to_agent filtered in Python over every open handoff).
        return self.be.find_nodes("Handoff", status="open", to_agent=agent_id)

    def complete_handoff(self, handoff_uid: str, by_agent: str, session_id: str,
                         result_text: str) -> None:
        self.be.set_props(handoff_uid, {"status": "done", "result": result_text})
        self.log_episode(by_agent, session_id, "handoff_completed",
                         f"Handoff completed: {result_text}", about=[handoff_uid])

    def handoff_context(self, handoff_uid: str) -> dict:
        """Everything the receiving agent needs, gathered by traversal only:
        the handoff, the memory nodes it references, and each reference's
        one-hop neighborhood (the entities the memory is about)."""
        h = self.be.get_node(handoff_uid)
        refs = [n for _, n in self.be.neighbors(handoff_uid, "REFERENCES", "out")]
        paths = self.be.traverse(handoff_uid, [("REFERENCES", "out")])
        neighborhood = {}
        for r in refs:
            for _, n in self.be.neighbors(r["uid"], None, "both"):
                neighborhood[n["uid"]] = n
        return {"handoff": h, "references": refs, "paths": paths,
                "neighborhood": list(neighborhood.values())}

    # -- recall ----------------------------------------------------------------
    def recall(self, text: str) -> list[dict]:
        """Facts whose text or ABOUT-entities match the query terms.

        Match semantics are unchanged, but the ABOUT lookup no longer runs
        per fact (the old shape was one neighbors call per fact in the
        graph — an N+1 against a hosted backend). Facts that already match
        on their own text never trigger it; the rest resolve their ABOUT
        names in one bulk pass (see _about_names).
        """
        q = text.lower()
        terms = [t for t in q.split() if len(t) > 3]
        facts = self.be.find_nodes("Fact")
        matched: set[str] = set()
        pending = []
        for f in facts:
            hay = f["props"].get("text", "").lower()
            if q in hay or any(t in hay for t in terms):
                matched.add(f["uid"])
            else:
                pending.append(f)
        if pending:
            names = self._about_names([f["uid"] for f in pending])
            for f in pending:
                if any(q in a.lower() for a in names.get(f["uid"], [])):
                    matched.add(f["uid"])
        return [f for f in facts if f["uid"] in matched]

    def _about_names(self, fact_uids: list[str]) -> dict[str, list[str]]:
        """{fact_uid: [ABOUT-target display names]} in two backend calls:
        one all_edges pass for the ABOUT edges of the given facts, one
        all_nodes pass to resolve the target names."""
        want = set(fact_uids)
        targets: dict[str, list[str]] = {}
        for e in self.be.all_edges():
            if e["rel"] == "ABOUT" and e["src"] in want:
                targets.setdefault(e["src"], []).append(e["dst"])
        if not targets:
            return {}
        nodes = {n["uid"]: n for n in self.be.all_nodes()}
        return {
            src: [
                (nodes[d]["props"].get("name") or nodes[d]["props"].get("title") or "")
                for d in dsts if d in nodes
            ]
            for src, dsts in targets.items()
        }
