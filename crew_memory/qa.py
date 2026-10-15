"""Q&A execution — every intent becomes graph traversals; every answer ships
with the evidence path(s) it came from.

An answer is: text, the resolved intent + entities, evidence paths (chains of
real nodes/edges from the graph), and a subgraph for visualization. If the
graph cannot support an answer, the engine says so instead of guessing.
"""
from __future__ import annotations

from . import planner as pl
from .memory import MemoryService


def _path_view(path: dict) -> dict:
    return {
        "nodes": [
            {"uid": n["uid"], "label": n["label"], "name": pl.display_name(n)}
            for n in path["nodes"]
        ],
        "rels": path["rels"],
    }


def _subgraph(paths: list[dict]) -> dict:
    nodes, edges, seen = [], [], set()
    for p in paths:
        for n in p["nodes"]:
            if n["uid"] not in seen:
                seen.add(n["uid"])
                nodes.append({"uid": n["uid"], "label": n["label"],
                              "name": pl.display_name(n)})
        for i, rel in enumerate(p["rels"]):
            edges.append({"src": p["nodes"][i]["uid"], "rel": rel,
                          "dst": p["nodes"][i + 1]["uid"]})
    return {"nodes": nodes, "edges": edges}


def _result(question, intent, entities, answer, paths, answered=True):
    return {
        "question": question, "intent": intent,
        "entities": [pl.display_name(e) for e in entities.values()],
        "answer": answer, "answered": answered,
        "evidence": [_path_view(p) for p in paths],
        "subgraph": _subgraph(paths),
    }


def _no_answer(question, intent, entities, what):
    return _result(question, intent, entities,
                   f"I don't have graph evidence for {what} yet. "
                   "Try asking about a specific project, decision, topic, or person.",
                   [], answered=False)


def answer_question(be, question: str, memory: MemoryService | None = None) -> dict:
    plan = pl.plan(be, question)
    intent, ent = plan["intent"], plan["entities"]
    proj = ent.get("Project")
    topic = ent.get("Topic")
    dec = ent.get("Decision")
    person = ent.get("Person")

    if intent == "who_owns":
        target = proj or ent.get("Document")
        if not target:
            return _no_answer(question, intent, ent, "an owner")
        paths = be.traverse(target["uid"], [("OWNS", "in")])
        if not paths:
            return _no_answer(question, intent, ent, f"the owner of {pl.display_name(target)}")
        owner = paths[0]["nodes"][-1]
        return _result(question, intent, ent,
                       f"{pl.display_name(owner)} owns {pl.display_name(target)} "
                       f"({owner['props'].get('role', 'owner')}).", paths)

    if intent == "who_works_on":
        if not proj:
            return _no_answer(question, intent, ent, "a project team")
        paths = be.traverse(proj["uid"], [("WORKS_ON", "in")])
        names = [pl.display_name(p["nodes"][-1]) for p in paths]
        return _result(question, intent, ent,
                       f"{len(names)} people work on {pl.display_name(proj)}: "
                       + ", ".join(names) + ".", paths)

    if intent == "team_of":
        target = proj or person
        if not target:
            return _no_answer(question, intent, ent, "a team")
        if target["label"] == "Project":
            paths = be.traverse(target["uid"], [("PART_OF", "out")])
        else:
            paths = be.traverse(target["uid"], [("MEMBER_OF", "out")])
        if not paths:
            return _no_answer(question, intent, ent, "a team")
        team = paths[0]["nodes"][-1]
        return _result(question, intent, ent,
                       f"{pl.display_name(target)} is part of {pl.display_name(team)}.",
                       paths)

    if intent in ("who_decided", "why_decided"):
        if dec is None and proj is not None:
            dpaths = be.traverse(proj["uid"], [("HAS_DECISION", "out")])
            if not dpaths:
                return _no_answer(question, intent, ent, "a decision")
            dec = dpaths[0]["nodes"][-1]
        if dec is None and topic is not None:
            cands = [n for _, n in be.neighbors(topic["uid"], "ABOUT", "in")
                     if n["label"] == "Decision"]
            if cands:
                dec = cands[0]
        if dec is None:
            return _no_answer(question, intent, ent, "a decision")
        by = be.traverse(dec["uid"], [("MADE_BY", "out")])
        doc = be.traverse(dec["uid"], [("DOCUMENTED_IN", "out")])
        src = be.traverse(dec["uid"], [("HAS_DECISION", "in")])
        paths = by + doc + src
        # Compose the full traceability chain as single paths:
        # Project -HAS_DECISION-> Decision -MADE_BY-> Person (and -> Document).
        for sp in src:
            project_node = sp["nodes"][-1]
            for steps, tail in (([("HAS_DECISION", "out"), ("MADE_BY", "out")], "Person"),
                                ([("HAS_DECISION", "out"), ("DOCUMENTED_IN", "out")], "Document")):
                for chain in be.traverse(project_node["uid"], steps):
                    if chain["nodes"][1]["uid"] == dec["uid"] and \
                            chain["nodes"][-1]["label"] == tail:
                        paths.append(chain)
        decider = pl.display_name(by[0]["nodes"][-1]) if by else "unknown"
        if intent == "who_decided":
            text = f"{decider} made the decision '{pl.display_name(dec)}'."
        else:
            text = (f"{decider} decided '{pl.display_name(dec)}'. "
                    f"Rationale recorded in the graph: {dec['props'].get('rationale', '')}")
            if doc:
                text += f" Documented in '{pl.display_name(doc[0]['nodes'][-1])}'."
        return _result(question, intent, ent, text, paths)

    if intent == "who_knows":
        if not topic:
            return _no_answer(question, intent, ent, "a topic expert")
        ranked = []
        for eprops, n in be.neighbors(topic["uid"], "KNOWS_ABOUT", "in"):
            ranked.append((eprops.get("strength", 0), eprops.get("evidence", 0), n))
        if not ranked:
            return _no_answer(question, intent, ent,
                              f"anyone who knows about {pl.display_name(topic)}")
        ranked.sort(key=lambda r: (-r[0], -r[1], pl.display_name(r[2])))
        paths = []
        for _, _, n in ranked[:3]:
            paths.append({"nodes": [n, topic], "rels": ["KNOWS_ABOUT"]})
            doc_paths = be.traverse(n["uid"], [("AUTHORED", "out"), ("ABOUT", "out")])
            for dp in doc_paths:
                if dp["nodes"][-1]["uid"] == topic["uid"]:
                    paths.append(dp)
                    break
        names = ", ".join(
            f"{pl.display_name(n)} (strength {s}, backed by {e} graph record(s))"
            for s, e, n in ranked[:3])
        return _result(question, intent, ent,
                       f"Best people to ask about {pl.display_name(topic)}: {names}.",
                       paths)

    if intent == "decisions_about":
        target = proj or topic
        if not target:
            return _no_answer(question, intent, ent, "decisions")
        if target["label"] == "Project":
            paths = be.traverse(target["uid"], [("HAS_DECISION", "out")])
        else:
            paths = []
            for _, n in be.neighbors(target["uid"], "ABOUT", "in"):
                if n["label"] == "Decision":
                    paths.append({"nodes": [target, n], "rels": ["ABOUT"]})
        if not paths:
            return _no_answer(question, intent, ent,
                              f"decisions about {pl.display_name(target)}")
        titles = [pl.display_name(p["nodes"][-1]) for p in paths]
        return _result(question, intent, ent,
                       f"{len(titles)} decision(s) recorded for "
                       f"{pl.display_name(target)}: " + "; ".join(titles) + ".",
                       paths)

    if intent == "depends_on":
        if not proj:
            return _no_answer(question, intent, ent, "a project")
        fwd = be.traverse(proj["uid"], [("DEPENDS_ON", "out")])
        deep = be.traverse(proj["uid"], [("DEPENDS_ON", "out"), ("DEPENDS_ON", "out")])
        names = [pl.display_name(p["nodes"][-1]) for p in fwd]
        if not names:
            return _result(question, intent, ent,
                           f"{pl.display_name(proj)} has no recorded project dependencies.", [])
        return _result(question, intent, ent,
                       f"{pl.display_name(proj)} depends on: " + ", ".join(names) + ".",
                       fwd + deep)

    if intent == "recall_memory":
        mem = memory or MemoryService(be)
        hits = mem.recall(question)
        if ent:
            for label in ("Project", "Topic", "Decision"):
                if label in ent:
                    for f in mem.facts(about_uid=ent[label]["uid"]):
                        if f not in hits:
                            hits.append(f)
        if not hits:
            return _no_answer(question, intent, ent, "recorded crew memory on that")
        paths = []
        for f in hits:
            about_paths = be.traverse(f["uid"], [("ABOUT", "out")])
            paths.extend(about_paths or [{"nodes": [f], "rels": []}])
        texts = "; ".join(f["props"].get("text", "") for f in hits)
        return _result(question, intent, ent,
                       f"The crew has {len(hits)} recorded memory item(s): {texts}",
                       paths)

    # what_is (default)
    target = proj or topic or person or dec or ent.get("Team") or ent.get("Document")
    if not target:
        return _no_answer(question, intent, ent, "that")
    summary = target["props"].get("summary") or target["props"].get("rationale") or \
        target["props"].get("role") or ""
    paths = []
    if target["label"] == "Project":
        paths = (be.traverse(target["uid"], [("OWNS", "in")])[:1]
                 + be.traverse(target["uid"], [("PART_OF", "out")])[:1]
                 + be.traverse(target["uid"], [("HAS_DECISION", "out")])[:2])
    elif target["label"] == "Person":
        paths = (be.traverse(target["uid"], [("MEMBER_OF", "out")])[:1]
                 + be.traverse(target["uid"], [("WORKS_ON", "out")])[:3])
    text = f"{pl.display_name(target)} ({target['label']}): {summary}"
    return _result(question, intent, ent, text, paths)
