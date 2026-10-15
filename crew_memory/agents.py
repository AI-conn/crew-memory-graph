"""The crew: Planner, Researcher, Executor.

Agents are thin. They hold no state of their own — every fact, plan, and
handoff lives in the graph via MemoryService. Any agent can be constructed in
a fresh process and pick up exactly where another left off, which is what the
session-1/session-2 demo proves.
"""
from __future__ import annotations

from . import qa
from .memory import MemoryService


class CrewAgent:
    def __init__(self, be, agent_id: str):
        self.be = be
        self.agent_id = agent_id
        self.memory = MemoryService(be)
        self.session_id: str | None = None

    def boot(self) -> str:
        self.session_id = self.memory.start_session(self.agent_id)
        return self.session_id


class ResearcherAgent(CrewAgent):
    def __init__(self, be):
        super().__init__(be, "researcher")

    def teach(self, items: list[dict]) -> list[str]:
        """Record a briefing: items = [{text, about: [uid,...], kind}]."""
        if not self.session_id:
            self.boot()
        written = []
        for it in items:
            fid = self.memory.learn_fact(
                self.agent_id, self.session_id, it["text"],
                about=it.get("about", []), kind=it.get("kind", "fact"),
                source=it.get("source", "briefing"))
            written.append(fid)
        return written

    def answer(self, question: str) -> dict:
        return qa.answer_question(self.be, question, memory=self.memory)


class PlannerAgent(CrewAgent):
    def __init__(self, be):
        super().__init__(be, "planner")

    def make_plan(self, goal: str, steps: list[str], about: list[str] | None = None) -> str:
        if not self.session_id:
            self.boot()
        pid = self.memory.record_procedure(
            self.agent_id, self.session_id, name=f"Plan: {goal}",
            steps=steps, trigger=goal)
        self.memory.log_episode(self.agent_id, self.session_id, "plan_created",
                                f"Plan created for goal: {goal}", about=about or [])
        return pid

    def file_handoff(self, to_agent: str, summary: str, references: list[str],
                     question: str | None = None) -> str:
        if not self.session_id:
            self.boot()
        return self.memory.create_handoff(
            self.agent_id, to_agent, self.session_id, summary, references,
            question=question)


class ExecutorAgent(CrewAgent):
    def __init__(self, be):
        super().__init__(be, "executor")

    def run_open_handoffs(self) -> list[dict]:
        """Pick up every open handoff addressed to the Executor, USING ONLY
        graph traversal: follow REFERENCES to the memory written by other
        agents, answer the handoff's question from those facts, perform the
        next unfinished step of any referenced procedure, and close the
        handoff with the result. Returns a report per handoff, including the
        memory path actually traversed."""
        if not self.session_id:
            self.boot()
        reports = []
        for h in self.memory.open_handoffs(self.agent_id):
            ctx = self.memory.handoff_context(h["uid"])
            memory_path = [n["uid"] for p in ctx["paths"] for n in p["nodes"]]
            facts = [r for r in ctx["references"] if r["label"] == "Fact"]
            procedures = [r for r in ctx["references"] if r["label"] == "Procedure"]

            answer_text, evidence = "", []
            question = h["props"].get("question")
            if facts:
                # The handoff's referenced facts are its payload — they are
                # what the receiving agent answers from first.
                answer_text = "; ".join(f["props"].get("text", "") for f in facts)
            if question:
                res = qa.answer_question(self.be, question, memory=self.memory)
                evidence = res["evidence"]
                if res.get("answered") and res["answer"] not in answer_text:
                    answer_text = (answer_text + " | Graph context: " + res["answer"]
                                   if answer_text else res["answer"])

            step_done = None
            for proc in procedures:
                for step in self.memory.procedure_steps(proc["uid"]):
                    if not step["props"].get("done"):
                        self.memory.mark_step_done(step["uid"])
                        step_done = step["props"].get("text")
                        break
                if step_done:
                    break

            result = answer_text or h["props"].get("summary", "")
            if step_done:
                result += f" | Step performed: {step_done}"
            self.memory.complete_handoff(h["uid"], self.agent_id, self.session_id, result)
            reports.append({
                "handoff": h["uid"], "question": question, "answer": answer_text,
                "step_done": step_done, "memory_path": memory_path,
                "evidence": evidence, "result": result,
            })
        return reports


# ----------------------------------------------------------------------
# Demo spine (shared by the CLI scripts and the web UI)
# ----------------------------------------------------------------------
DEMO_PROJECT = "project:beacon-mobile-app"

DEMO_BRIEFING = [
    {"text": "Decision: the Beacon Mobile App launch moves to November 18, 2026, "
             "to align with the Harbor onboarding release train.",
     "about": [DEMO_PROJECT], "kind": "decision"},
    {"text": "The Beacon beta cohort is 400 workspaces recruited from the Harbor waitlist.",
     "about": [DEMO_PROJECT], "kind": "fact"},
    {"text": "Beacon launch blocker: the Vertex API gateway rate-limit change must ship "
             "before the beta opens, or mobile clients will be throttled.",
     "about": [DEMO_PROJECT, "project:vertex-api-gateway"], "kind": "fact"},
]

DEMO_GOAL = "Prepare the Beacon Mobile App launch"
DEMO_STEPS = [
    "Draft the launch checklist from the briefing facts",
    "Confirm the beta cohort size with Customer Experience",
    "Schedule the launch review with Sofia Marino",
]
DEMO_QUESTION = "When is the Beacon launch, and how large is the beta cohort?"


def run_session1(be) -> dict:
    """Session 1: Researcher is taught the briefing; Planner plans and hands
    off to the Executor. Everything lands in the graph."""
    researcher = ResearcherAgent(be)
    researcher.boot()
    fact_uids = researcher.teach(DEMO_BRIEFING)

    planner = PlannerAgent(be)
    planner.boot()
    procedure_uid = planner.make_plan(DEMO_GOAL, DEMO_STEPS, about=[DEMO_PROJECT])
    handoff_uid = planner.file_handoff(
        "executor",
        summary=f"{DEMO_GOAL}. Use the briefing facts recorded this session.",
        references=fact_uids + [procedure_uid, DEMO_PROJECT],
        question=DEMO_QUESTION)
    return {"facts": fact_uids, "procedure": procedure_uid,
            "handoff": handoff_uid,
            "researcher_session": researcher.session_id,
            "planner_session": planner.session_id}


def run_session2(be) -> dict:
    """Session 2: a brand-new Executor (new process in the CLI demo) reads the
    handoff from the graph and acts on memory it never saw written."""
    executor = ExecutorAgent(be)
    executor.boot()
    reports = executor.run_open_handoffs()
    return {"executor_session": executor.session_id, "reports": reports}
