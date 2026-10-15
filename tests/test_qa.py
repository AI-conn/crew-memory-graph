from crew_memory import agents, qa


def test_who_owns_with_evidence(be):
    r = qa.answer_question(be, "Who owns the Atlas Billing Platform?")
    assert r["answered"] and "Priya Nair" in r["answer"]
    assert r["evidence"] and r["evidence"][0]["rels"] == ["OWNS"]


def test_why_decided_shows_rationale_and_source(be):
    r = qa.answer_question(be, "Why did we decide to adopt usage-based pricing for Atlas?")
    assert "flat tiers" in r["answer"]
    assert "Atlas Pricing Analysis" in r["answer"]
    rels = {rel for p in r["evidence"] for rel in p["rels"]}
    assert {"MADE_BY", "DOCUMENTED_IN"} <= rels


def test_who_knows_ranks_by_strength(be):
    r = qa.answer_question(be, "Who knows about data pipelines?")
    assert r["answer"].index("Aisha Bello") < r["answer"].index("Victor Chen")


def test_depends_on_multihop_evidence(be):
    r = qa.answer_question(be, "What does Pulse Analytics depend on?")
    assert "Atlas Billing Platform" in r["answer"]
    assert any(len(p["nodes"]) >= 3 for p in r["evidence"])  # Pulse->Atlas->Vertex


def test_recall_after_teach(be):
    agents.run_session1(be)
    r = qa.answer_question(be, "What did the crew learn about the Beacon Mobile App?")
    assert r["answered"] and "November 18" in r["answer"]


def test_unknown_question_declines(be):
    r = qa.answer_question(be, "What is the cafeteria menu for Friday?")
    assert r["answered"] is False
