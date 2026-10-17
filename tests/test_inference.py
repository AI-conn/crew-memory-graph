"""Token Factory inference: per-role routing + Planner fallback.

All tests run against a fake transport — no network, no API key. The live
path was verified separately (helper smokes: Nemotron-3-Ultra on
2026-10-15 and Nemotron-3-Nano on 2026-10-16, both HTTP 200 with correct
replies; the everyday role was re-seated to Nano on 2026-10-16).
"""
import pytest

from crew_memory import agents, inference

NEMOTRON = "nvidia/Nemotron-3-Ultra-550b-a55b"
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


class FakeTransport:
    """Records calls; replies with a canned OpenAI-shaped response, or
    raises InferenceError for models in `fail_models`."""

    def __init__(self, fail_models=()):
        self.calls = []
        self.fail_models = set(fail_models)

    def __call__(self, url, payload, api_key, timeout):
        self.calls.append({"url": url, "payload": payload, "api_key": api_key})
        if payload["model"] in self.fail_models:
            raise inference.InferenceError(f"boom for {payload['model']}")
        return {"choices": [{"message": {
                    "content": f"answer from {payload['model']}"}}],
                "usage": {"total_tokens": 42}}


def make_client(transport):
    return inference.InferenceClient(api_key="test-key", transport=transport)


def test_planner_role_routes_to_nemotron():
    t = FakeTransport()
    res = make_client(t).chat("planner", [{"role": "user", "content": "hi"}])
    assert t.calls[0]["url"] == \
        "https://api.tokenfactory.nebius.com/v1/chat/completions"
    assert t.calls[0]["payload"]["model"] == NEMOTRON
    assert t.calls[0]["api_key"] == "test-key"  # key reaches the transport only
    assert res["model"] == NEMOTRON and res["role"] == "planner"
    assert res["content"] == f"answer from {NEMOTRON}"


@pytest.mark.parametrize("role", ["researcher", "executor"])
def test_everyday_roles_route_to_glm(role):
    t = FakeTransport()
    res = make_client(t).chat(role, [{"role": "user", "content": "hi"}])
    assert t.calls[0]["payload"]["model"] == NANO
    assert res["model"] == NANO and res["role"] == role


def test_unknown_role_rejected():
    with pytest.raises(inference.InferenceError):
        make_client(FakeTransport()).chat("captain",
                                          [{"role": "user", "content": "hi"}])


def test_missing_key_raises_and_names_the_env_var():
    client = inference.InferenceClient(api_key="", transport=FakeTransport())
    assert client.configured is False
    with pytest.raises(inference.InferenceError) as exc:
        client.chat("planner", [{"role": "user", "content": "hi"}])
    assert inference.API_KEY_ENV in str(exc.value)


def test_answer_from_memory_uses_planner(be):
    agents.run_session1(be)
    t = FakeTransport()
    res = inference.answer_from_memory(be, agents.DEMO_QUESTION,
                                       client=make_client(t))
    assert res["answered"] and res["fallback"] is False
    assert res["role"] == "planner" and res["model"] == NEMOTRON
    assert any("November 18" in f for f in res["facts"])  # graph facts in prompt
    sent = t.calls[0]["payload"]["messages"][1]["content"]
    assert "November 18" in sent and agents.DEMO_QUESTION in sent


def test_answer_from_memory_falls_back_when_planner_fails(be):
    agents.run_session1(be)
    t = FakeTransport(fail_models={NEMOTRON})
    res = inference.answer_from_memory(be, agents.DEMO_QUESTION,
                                       client=make_client(t))
    assert res["answered"] and res["fallback"] is True
    assert res["role"] == "researcher" and res["model"] == NANO
    assert [c["payload"]["model"] for c in t.calls] == [NEMOTRON, NANO]


def test_answer_from_memory_no_facts_makes_no_call(empty_be):
    t = FakeTransport()
    res = inference.answer_from_memory(empty_be, "anything at all?",
                                       client=make_client(t))
    assert res["answered"] is False and res["model"] is None
    assert t.calls == []  # no facts, no API spend
