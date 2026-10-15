"""Query planner — natural language in, traversal plan out.

Deterministic and pattern-based: no LLM, no API key, nothing to hallucinate.
Entities are resolved against the graph's own names and titles (longest-match
wins), so the same planner works for any tenant's graph. The output is a named
intent plus the resolved entity nodes; qa.py executes the intent as graph
traversals and every result carries the path it came from.
"""
from __future__ import annotations

import re

ENTITY_LABELS = ("Person", "Project", "Team", "Topic", "Decision", "Document")

INTENT_PATTERNS = [
    ("why_decided", r"\bwhy\b.*\b(decid|decision|chos|adopt)|\breason(ing)?\b.*\bdecision\b"),
    ("who_decided", r"\bwho\b.*\b(decid|chos|approved|made the decision)"),
    ("who_owns", r"\bwho\b.*\b(owns|own|responsible for|in charge of|leads|lead)\b"),
    ("who_knows", r"\bwho\b.*\b(knows|expert|specialist|can help|ask about)\b"),
    ("who_works_on", r"\bwho\b.*\b(works on|working on|is on|staffed)\b"),
    ("team_of", r"\b(which|what) team\b"),
    ("decisions_about", r"\b(decisions|decided)\b"),
    ("depends_on", r"\bdepend"),
    ("recall_memory", r"\b(learn|learned|remember|taught|briefing)\b"),
    ("what_is", r"\b(what is|tell me about|describe|overview of)\b"),
]


def display_name(node: dict) -> str:
    p = node["props"]
    return p.get("name") or p.get("title") or (p.get("text") or "")[:60] or node["uid"]


class EntityIndex:
    """Name/title → node, built from the live graph (per tenant)."""

    def __init__(self, be):
        self.entries: list[tuple[str, dict]] = []  # (lowercased name, node)
        for label in ENTITY_LABELS:
            for n in be.find_nodes(label):
                name = display_name(n)
                if name:
                    self.entries.append((name.lower(), n))
                    # Short alias: a project's distinctive first word
                    # ("Beacon" for "Beacon Mobile App") — how people
                    # actually refer to projects in questions.
                    if label == "Project":
                        first = name.split()[0].lower()
                        if len(first) >= 4:
                            self.entries.append((first, n))
        self.entries.sort(key=lambda e: -len(e[0]))

    def resolve(self, question: str) -> dict[str, dict]:
        """Best (longest) match per label."""
        q = question.lower()
        found: dict[str, dict] = {}
        for name, node in self.entries:
            if name in q and node["label"] not in found:
                found[node["label"]] = node
        if "Decision" not in found:
            d = self._resolve_decision_by_tokens(q)
            if d:
                found["Decision"] = d
        return found

    def _resolve_decision_by_tokens(self, q: str) -> dict | None:
        qtokens = set(re.findall(r"[a-z]{3,}", q)) - {
            "who", "what", "why", "did", "the", "was", "were", "decide",
            "decided", "decision", "about", "team", "make", "made",
        }
        best, best_score = None, 0
        for name, node in self.entries:
            if node["label"] != "Decision":
                continue
            dtokens = set(re.findall(r"[a-z]{3,}", name))
            score = len(qtokens & dtokens)
            if score > best_score and score >= 2:
                best, best_score = node, score
        return best


def classify(question: str) -> str:
    q = question.lower()
    for intent, pat in INTENT_PATTERNS:
        if re.search(pat, q):
            return intent
    return "what_is"


def plan(be, question: str) -> dict:
    idx = EntityIndex(be)
    entities = idx.resolve(question)
    return {"intent": classify(question), "entities": entities, "question": question}
