"""Flask app: JSON API + single-page UI for the Crew Memory Graph.

State rule: the server holds NO knowledge. Backends are cached per tenant
purely as connections; every read and write goes to the graph backend
(FalkorDB in deployment; in-memory dev backend locally, snapshot-persisted
and labeled).
"""
from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from . import agents, inference, ingest, qa
from .config import Config
from .graphdb import backend_for_tenant, snapshot_path
from .memory import MemoryService
from .planner import display_name

LAYER_BY_LABEL = {"Fact": "semantic", "Episode": "episodic",
                  "Procedure": "procedural", "Handoff": "episodic"}


def create_app(cfg: Config | None = None) -> Flask:
    cfg = cfg or Config.from_env()
    app = Flask(__name__)
    cache: dict[str, object] = {}

    def get_backend(tenant: str):
        if tenant not in cache:
            be = backend_for_tenant(cfg, tenant)
            if cfg.backend == "memory":
                p = snapshot_path(cfg, tenant)
                if os.path.exists(p):
                    be.load(p)
            cache[tenant] = be
        return cache[tenant]

    def persist(tenant: str):
        if cfg.backend == "memory":
            cache[tenant].save(snapshot_path(cfg, tenant))

    def tenant_of(req) -> str:
        return (req.values.get("tenant") or cfg.default_tenant).strip().lower()

    def ensure_seeded(tenant: str):
        be = get_backend(tenant)
        if be.node_count() == 0:
            ingest.ingest_company(be)
            persist(tenant)
        return be

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def status():
        tenant = tenant_of(request)
        be = ensure_seeded(tenant)
        return jsonify({
            "tenant": tenant,
            "backend": be.name,
            "backend_detail": (
                "FalkorDB Cloud (managed)"
                if be.name == "falkordb" else
                "OFFLINE DEV MODE — in-memory graph (not FalkorDB)"),
            "nodes": be.node_count(), "edges": be.edge_count(),
            "synthetic_data": True,
        })

    @app.get("/api/graph")
    def graph():
        be = ensure_seeded(tenant_of(request))
        nodes = [{"uid": n["uid"], "label": n["label"], "name": display_name(n)}
                 for n in be.all_nodes()]
        edges = [{"src": e["src"], "rel": e["rel"], "dst": e["dst"]}
                 for e in be.all_edges()]
        return jsonify({"nodes": nodes, "edges": edges})

    @app.post("/api/seed")
    def seed():
        tenant = tenant_of(request)
        be = get_backend(tenant)
        counts = ingest.ingest_company(be)
        MemoryService(be)  # re-ensure agent nodes after the clear inside ingest
        persist(tenant)
        return jsonify({"ok": True, "counts": counts})

    @app.post("/api/ask")
    def ask():
        data = request.get_json(force=True)
        tenant = data.get("tenant") or cfg.default_tenant
        be = ensure_seeded(tenant)
        res = qa.answer_question(be, data.get("question", ""),
                                 memory=MemoryService(be))
        return jsonify(res)

    @app.post("/api/ask_llm")
    def ask_llm():
        """Memory-recall answer synthesized by Token Factory inference
        (per-role routing in crew_memory/inference.py): the graph supplies
        the facts, the routed model supplies the reasoning."""
        data = request.get_json(force=True)
        tenant = data.get("tenant") or cfg.default_tenant
        be = ensure_seeded(tenant)
        client = inference.InferenceClient()
        if not client.configured:
            return jsonify({"ok": False, "error":
                            f"{inference.API_KEY_ENV} is not set — "
                            "Token Factory inference is not configured"}), 503
        try:
            res = inference.answer_from_memory(
                be, data.get("question", ""), client=client,
                memory=MemoryService(be))
        except inference.InferenceError as e:
            return jsonify({"ok": False, "error": str(e)}), 502
        return jsonify({"ok": True, **res})

    @app.post("/api/teach")
    def teach():
        data = request.get_json(force=True)
        tenant = data.get("tenant") or cfg.default_tenant
        be = ensure_seeded(tenant)
        researcher = agents.ResearcherAgent(be)
        about = [data["about"]] if data.get("about") else []
        uids = researcher.teach([{"text": data.get("text", ""), "about": about,
                                  "kind": data.get("kind", "fact")}])
        persist(tenant)
        return jsonify({"ok": True, "written": uids})

    @app.post("/api/session1")
    def session1():
        tenant = tenant_of(request)
        be = ensure_seeded(tenant)
        out = agents.run_session1(be)
        persist(tenant)
        return jsonify({"ok": True, **out})

    @app.post("/api/session2")
    def session2():
        tenant = tenant_of(request)
        be = ensure_seeded(tenant)
        out = agents.run_session2(be)
        persist(tenant)
        return jsonify({"ok": True, **out})

    @app.get("/api/handoffs")
    def handoffs():
        be = ensure_seeded(tenant_of(request))
        hs = be.find_nodes("Handoff")
        return jsonify([{
            "uid": h["uid"], "summary": h["props"].get("summary"),
            "question": h["props"].get("question"),
            "status": h["props"].get("status"),
            "from": h["props"].get("from_agent"), "to": h["props"].get("to_agent"),
            "result": h["props"].get("result", ""),
        } for h in hs])

    @app.get("/api/memory")
    def memory():
        tenant = tenant_of(request)
        layer = request.values.get("layer")
        be = ensure_seeded(tenant)
        out = []
        for label in ("Fact", "Episode", "Procedure", "Handoff", "Session"):
            for n in be.find_nodes(label):
                lay = n["props"].get("layer") or LAYER_BY_LABEL.get(label, "episodic")
                if layer and lay != layer:
                    continue
                out.append({"uid": n["uid"], "label": label, "layer": lay,
                            "name": display_name(n),
                            "agent": n["props"].get("agent", ""),
                            "created_at": n["props"].get("created_at", "")})
        return jsonify(out)

    return app


if __name__ == "__main__":
    cfg = Config.from_env()
    create_app(cfg).run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
