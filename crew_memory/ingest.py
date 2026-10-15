"""Ingestion: build the semantic layer (the company) into a tenant graph.

Expertise (KNOWS_ABOUT) is *derived*, not asserted: curated floors from the
dataset are combined with evidence counted from the graph itself — documents
authored about a topic, decisions made about it, tickets resolved on it.
Each KNOWS_ABOUT edge stores its strength and its evidence count, and the
supporting artifacts stay reachable as graph paths.
"""
from __future__ import annotations

from . import synthetic


def uid(label: str, slug: str) -> str:
    return f"{label.lower()}:{slug}"


def ingest_company(be, ds: dict | None = None, clear: bool = True) -> dict:
    ds = ds or synthetic.generate()
    if clear:
        be.clear()

    be.merge_node("Company", uid("company", synthetic.slugify(ds["company"]["name"])),
                  {"name": ds["company"]["name"], "synthetic": True,
                   "summary": "Synthetic demo company generated for this project."})

    for t in ds["teams"]:
        be.merge_node("Team", uid("team", t["slug"]),
                      {"name": t["name"], "summary": t["summary"]})
        be.merge_edge(uid("team", t["slug"]), "PART_OF",
                      uid("company", synthetic.slugify(ds["company"]["name"])))

    for p in ds["people"]:
        be.merge_node("Person", uid("person", p["slug"]),
                      {"name": p["name"], "role": p["role"]})
        be.merge_edge(uid("person", p["slug"]), "MEMBER_OF", uid("team", synthetic.slugify(p["team"])))

    for t in ds["topics"]:
        be.merge_node("Topic", uid("topic", t["slug"]), {"name": t["name"]})

    for pr in ds["projects"]:
        pu = uid("project", pr["slug"])
        be.merge_node("Project", pu, {"name": pr["name"], "summary": pr["summary"]})
        be.merge_edge(pu, "PART_OF", uid("team", synthetic.slugify(pr["team"])))
        be.merge_edge(uid("person", synthetic.slugify(pr["owner"])), "OWNS", pu)
        for m in pr["members"]:
            role = "owner" if m == pr["owner"] else "contributor"
            be.merge_edge(uid("person", synthetic.slugify(m)), "WORKS_ON", pu, {"role": role})
        for topic in pr["topics"]:
            be.merge_edge(pu, "ABOUT", uid("topic", synthetic.slugify(topic)))

    for a, b in ds["project_deps"]:
        be.merge_edge(uid("project", synthetic.slugify(a)), "DEPENDS_ON",
                      uid("project", synthetic.slugify(b)))

    for d in ds["documents"]:
        du = uid("document", d["slug"])
        be.merge_node("Document", du, {
            "title": d["title"], "kind": d["kind"], "summary": d["summary"]})
        be.merge_edge(uid("person", synthetic.slugify(d["author"])), "AUTHORED", du)
        be.merge_edge(du, "ABOUT", uid("topic", synthetic.slugify(d["topic"])))
        be.merge_edge(du, "REFERENCES", uid("project", synthetic.slugify(d["project"])))

    for dec in ds["decisions"]:
        du = uid("decision", dec["slug"])
        be.merge_node("Decision", du, {
            "title": dec["title"], "rationale": dec["rationale"], "date": dec["date"]})
        pu = uid("project", synthetic.slugify(dec["project"]))
        be.merge_edge(pu, "HAS_DECISION", du)
        be.merge_edge(du, "MADE_BY", uid("person", synthetic.slugify(dec["decider"])))
        be.merge_edge(du, "DOCUMENTED_IN", uid("document", synthetic.slugify(dec["doc"])))
        be.merge_edge(du, "ABOUT", uid("topic", synthetic.slugify(dec["topic"])))

    for t in ds["tickets"]:
        tu = uid("ticket", t["slug"])
        be.merge_node("Ticket", tu, {"title": t["title"], "status": t["status"]})
        pu = uid("project", synthetic.slugify(t["project"]))
        be.merge_edge(tu, "FOR_PROJECT", pu)
        be.merge_edge(tu, "ASSIGNED_TO", uid("person", synthetic.slugify(t["assignee"])))
        if t["status"] == "resolved":
            be.merge_edge(tu, "RESOLVED_BY", uid("person", synthetic.slugify(t["resolver"])))
        be.merge_edge(tu, "ABOUT", uid("topic", synthetic.slugify(t["topic"])))

    for c in ds["chats"]:
        cu = uid("chatthread", c["slug"])
        be.merge_node("ChatThread", cu, {"title": c["title"], "summary": c["summary"]})
        be.merge_edge(cu, "DISCUSSES", uid("project", synthetic.slugify(c["project"])))
        if c.get("decision"):
            be.merge_edge(cu, "DISCUSSES", uid("decision", synthetic.slugify(c["decision"])))
        for part in c["participants"]:
            be.merge_edge(uid("person", synthetic.slugify(part)), "MENTIONS", cu)

    _derive_expertise(be, ds)

    return {
        "nodes": be.node_count(),
        "edges": be.edge_count(),
        "people": len(ds["people"]), "teams": len(ds["teams"]),
        "projects": len(ds["projects"]), "documents": len(ds["documents"]),
        "decisions": len(ds["decisions"]), "tickets": len(ds["tickets"]),
        "chats": len(ds["chats"]),
    }


def _derive_expertise(be, ds: dict) -> None:
    strength: dict[tuple[str, str], int] = {}
    evidence: dict[tuple[str, str], int] = {}

    def bump(person: str, topic: str, pts: int, ev: int = 1):
        key = (person, topic)
        strength[key] = strength.get(key, 0) + pts
        evidence[key] = evidence.get(key, 0) + ev

    for person, topic, floor in ds["expertise"]:
        key = (person, topic)
        strength[key] = max(strength.get(key, 0), floor)
        evidence[key] = evidence.get(key, 0) + 1  # the recorded expertise assertion itself

    for d in ds["documents"]:
        bump(d["author"], d["topic"], 2)
    for dec in ds["decisions"]:
        bump(dec["decider"], dec["topic"], 2)
    for t in ds["tickets"]:
        if t["status"] == "resolved":
            bump(t["resolver"], t["topic"], 1)

    for (person, topic), s in strength.items():
        if s >= 2:
            be.merge_edge(
                uid("person", synthetic.slugify(person)), "KNOWS_ABOUT",
                uid("topic", synthetic.slugify(topic)),
                {"strength": min(s, 5), "evidence": evidence.get((person, topic), 0)},
            )
