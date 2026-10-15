from crew_memory import planner as pl


def test_classify():
    assert pl.classify("Who owns the Atlas Billing Platform?") == "who_owns"
    assert pl.classify("Who decided to sunset the legacy billing API?") == "who_decided"
    assert pl.classify("Why did we decide to adopt usage-based pricing?") == "why_decided"
    assert pl.classify("Who knows about data pipelines?") == "who_knows"
    assert pl.classify("Who works on Orion Search?") == "who_works_on"
    assert pl.classify("What does Beacon depend on?") == "depends_on"
    assert pl.classify("What did the crew learn about Beacon?") == "recall_memory"


def test_entity_resolution_full_and_alias(be):
    idx = pl.EntityIndex(be)
    found = idx.resolve("Who owns the Atlas Billing Platform?")
    assert found["Project"]["props"]["name"] == "Atlas Billing Platform"
    found = idx.resolve("When is the Beacon launch?")
    assert found["Project"]["props"]["name"] == "Beacon Mobile App"


def test_decision_resolution_by_tokens(be):
    idx = pl.EntityIndex(be)
    found = idx.resolve("Who decided to sunset the legacy billing API?")
    assert found["Decision"]["props"]["title"] == "Sunset the legacy billing API"
