from crew_memory import synthetic


def test_counts_and_shape():
    ds = synthetic.generate()
    assert len(ds["people"]) == 48
    assert len(ds["teams"]) == 6
    assert len(ds["projects"]) == 8
    assert len(ds["topics"]) == 12
    assert len(ds["decisions"]) == 8
    assert len(ds["tickets"]) == 48
    artifacts = (len(ds["documents"]) + len(ds["tickets"])
                 + len(ds["decisions"]) + len(ds["chats"]))
    assert artifacts >= 100, artifacts


def test_deterministic():
    a = synthetic.public_dataset(synthetic.generate())
    b = synthetic.public_dataset(synthetic.generate(synthetic.SEED))
    assert a == b


def test_referential_integrity():
    ds = synthetic.generate()
    people = {p["name"] for p in ds["people"]}
    projects = {p["name"] for p in ds["projects"]}
    docs = {d["title"] for d in ds["documents"]}
    for p in ds["projects"]:
        assert p["owner"] in people
        assert set(p["members"]) <= people
    for d in ds["decisions"]:
        assert d["decider"] in people
        assert d["project"] in projects
        assert d["doc"] in docs
    for t in ds["tickets"]:
        assert t["assignee"] in people and t["resolver"] in people
        assert t["project"] in projects
