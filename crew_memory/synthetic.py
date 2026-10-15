"""Synthetic company dataset: 'Meridian Labs'.

Procedurally generated from a fixed seed around a curated core. The curated
core (project owners, key decisions and their rationales, headline expertise)
is fixed by hand so benchmark questions have exact ground truth; the fill
(extra tickets, chats, docs) is seeded-random but deterministic.

THIS DATA IS SYNTHETIC. It is labeled as such in the UI and README. No real
company, person, or metric is represented.
"""
from __future__ import annotations

import random
import re

SEED = 20261015


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


TEAMS = [
    ("Platform Engineering", "Core infrastructure, billing and API platforms."),
    ("Product Engineering", "Customer-facing product features and the mobile app."),
    ("Data and ML", "Search, ranking, analytics and data pipelines."),
    ("Customer Experience", "Onboarding, support tooling and success workflows."),
    ("Design", "Product design and the design system."),
    ("Operations", "Security, compliance, IT and business operations."),
]

# name, team, role
PEOPLE = [
    ("Priya Nair", "Platform Engineering", "Staff Engineer, Billing"),
    ("Tomás Rivera", "Platform Engineering", "Principal Engineer, API Platform"),
    ("Lena Fischer", "Platform Engineering", "Senior Engineer"),
    ("Raj Patel", "Platform Engineering", "Engineer"),
    ("Marta Kowalska", "Platform Engineering", "Engineer"),
    ("Henrik Lund", "Platform Engineering", "Site Reliability Engineer"),
    ("Grace Liu", "Platform Engineering", "Engineering Manager"),
    ("Omar Haddad", "Platform Engineering", "Engineer"),
    ("Daniel Kim", "Data and ML", "ML Lead"),
    ("Aisha Bello", "Data and ML", "Data Engineering Lead"),
    ("Victor Chen", "Data and ML", "ML Engineer"),
    ("Ingrid Johansson", "Data and ML", "Data Scientist"),
    ("Sam Whitfield", "Data and ML", "Data Engineer"),
    ("Noor Alami", "Data and ML", "ML Engineer"),
    ("Petra Novak", "Data and ML", "Analytics Engineer"),
    ("Sofia Marino", "Product Engineering", "Senior Product Engineer"),
    ("James O'Neill", "Product Engineering", "Engineer"),
    ("Yuki Tanaka", "Product Engineering", "Engineer"),
    ("Carlos Mendoza", "Product Engineering", "Engineer"),
    ("Anna Braun", "Product Engineering", "Engineering Manager"),
    ("Felix Wagner", "Product Engineering", "Engineer"),
    ("Hana Kimura", "Product Engineering", "Engineer"),
    ("Diego Fuentes", "Product Engineering", "Engineer"),
    ("Marcus Webb", "Customer Experience", "CX Lead"),
    ("Elena Petrova", "Customer Experience", "Onboarding Specialist"),
    ("Tom Becker", "Customer Experience", "Support Engineer"),
    ("Ruth Mbeki", "Customer Experience", "Customer Success Manager"),
    ("Anders Lindqvist", "Customer Experience", "Support Engineer"),
    ("Keiko Mori", "Customer Experience", "Onboarding Specialist"),
    ("Paul Girard", "Customer Experience", "CX Manager"),
    ("June Park", "Design", "Design Lead"),
    ("Oliver Grant", "Design", "Product Designer"),
    ("Mia Sørensen", "Design", "Product Designer"),
    ("Lucas Meyer", "Design", "UX Researcher"),
    ("Farah Khan", "Design", "Design Systems Designer"),
    ("Ben Achieng", "Design", "Product Designer"),
    ("Clara Dubois", "Design", "UX Writer"),
    ("David Osei", "Operations", "Security Lead"),
    ("Sara Lindholm", "Operations", "Compliance Manager"),
    ("Mike Torres", "Operations", "IT Manager"),
    ("Nina Volkov", "Operations", "Security Engineer"),
    ("Chris Doyle", "Operations", "Operations Analyst"),
    ("Amina Diallo", "Operations", "Procurement Lead"),
    ("Leo Fischer", "Operations", "Security Engineer"),
    ("Emma Wilson", "Operations", "Office Manager"),
    ("Ken Watanabe", "Operations", "Compliance Analyst"),
    ("Rosa Jiménez", "Operations", "IT Support Specialist"),
    ("Adam Novak", "Operations", "Operations Manager"),
]

TOPICS = [
    "Payments", "Billing", "Search Ranking", "Machine Learning",
    "Mobile UX", "Onboarding", "Analytics", "Data Pipelines",
    "API Design", "Infrastructure", "Security", "Accessibility",
]

# name, team, owner, summary, [topics]
PROJECTS = [
    ("Atlas Billing Platform", "Platform Engineering", "Priya Nair",
     "Usage-based billing, invoicing and payments for all Meridian products.",
     ["Payments", "Billing"]),
    ("Orion Search", "Data and ML", "Daniel Kim",
     "Product search and ranking across the catalogue.",
     ["Search Ranking", "Machine Learning"]),
    ("Beacon Mobile App", "Product Engineering", "Sofia Marino",
     "The Beacon iOS and Android app.",
     ["Mobile UX", "Onboarding"]),
    ("Harbor Onboarding", "Customer Experience", "Marcus Webb",
     "New-workspace onboarding flows and activation.",
     ["Onboarding"]),
    ("Pulse Analytics", "Data and ML", "Aisha Bello",
     "Customer-facing analytics dashboards and the event pipeline behind them.",
     ["Analytics", "Data Pipelines"]),
    ("Vertex API Gateway", "Platform Engineering", "Tomás Rivera",
     "The public API gateway, auth and rate limiting.",
     ["API Design", "Infrastructure"]),
    ("Willow Design System", "Design", "June Park",
     "Shared components, tokens and accessibility standards.",
     ["Accessibility"]),
    ("Sentinel Security", "Operations", "David Osei",
     "Tenant security controls: SSO, audit logs and access reviews.",
     ["Security", "Infrastructure"]),
]

PROJECT_DEPS = [
    ("Atlas Billing Platform", "Vertex API Gateway"),
    ("Beacon Mobile App", "Vertex API Gateway"),
    ("Pulse Analytics", "Atlas Billing Platform"),
    ("Harbor Onboarding", "Beacon Mobile App"),
    ("Sentinel Security", "Vertex API Gateway"),
]

# title, project, decider, topic, rationale, documenting doc title
DECISIONS = [
    ("Adopt usage-based pricing for Atlas", "Atlas Billing Platform", "Priya Nair", "Billing",
     "Enterprise cohort churn analysis showed flat tiers priced out high-volume tenants; usage-based pricing matched cost to value and the pilot cohort expanded 3 months in a row.",
     "Atlas Pricing Analysis"),
    ("Move Orion ranking to learning-to-rank", "Orion Search", "Daniel Kim", "Search Ranking",
     "Hand-tuned ranking rules plateaued; offline replay showed the learning-to-rank model lifted top-3 relevance on the labelled query set, and the rules had become unmaintainable.",
     "Orion Ranking Experiment Report"),
    ("Sunset the legacy billing API", "Atlas Billing Platform", "Tomás Rivera", "API Design",
     "The legacy billing API cost two engineer-days per week in maintenance and blocked the Vertex gateway migration; fewer than 4% of calls still used it.",
     "Legacy Billing API Deprecation Plan"),
    ("Require SSO for enterprise tenants", "Sentinel Security", "David Osei", "Security",
     "Two enterprise security reviews failed on password-only auth; SSO with SCIM provisioning was the blocking requirement in both deals.",
     "Enterprise Auth Requirements"),
    ("Rebuild onboarding as a checklist flow", "Harbor Onboarding", "Marcus Webb", "Onboarding",
     "Funnel data showed the wizard flow lost most workspaces at step 3; the checklist prototype let users skip and return, and activation rose in the pilot.",
     "Onboarding Funnel Analysis"),
    ("Adopt WCAG 2.2 AA as the design baseline", "Willow Design System", "June Park", "Accessibility",
     "Accessibility audit found contrast and focus-order failures in core components; fixing them ad hoc per product kept regressing, so the baseline moved into the design system.",
     "Accessibility Audit 2026"),
    ("Stream Pulse events through the Atlas event bus", "Pulse Analytics", "Aisha Bello", "Data Pipelines",
     "Batch imports made dashboards a day stale; the Atlas event bus already carried the same events, so streaming removed a pipeline and the staleness with it.",
     "Pulse Pipeline Review"),
    ("Cap free-tier API rate limits", "Vertex API Gateway", "Tomás Rivera", "Infrastructure",
     "A single free-tier tenant generated a third of gateway traffic during a scrape incident; per-tenant caps protect paying tenants' latency.",
     "Gateway Traffic Incident Review"),
]

DOC_KINDS = ["Spec", "Analysis", "Plan", "Report", "Guide"]


def generate(seed: int = SEED) -> dict:
    rng = random.Random(seed)
    people = [
        {"name": n, "team": t, "role": r, "slug": slugify(n)} for n, t, r in PEOPLE
    ]
    by_name = {p["name"]: p for p in people}
    teams = [{"name": n, "summary": s, "slug": slugify(n)} for n, s in TEAMS]
    topics = [{"name": t, "slug": slugify(t)} for t in TOPICS]
    topic_by_name = {t["name"]: t for t in topics}

    members: dict[str, list[str]] = {t["name"]: [] for t in teams}
    for p in people:
        members[p["team"]].append(p["name"])

    projects = []
    for name, team, owner, summary, tops in PROJECTS:
        crew = [owner] + [m for m in members[team] if m != owner][:3]
        extra_team = rng.choice([t for t in members if t != team])
        crew += rng.sample(members[extra_team], 2)
        projects.append({
            "name": name, "slug": slugify(name), "team": team, "owner": owner,
            "summary": summary, "topics": tops, "members": sorted(set(crew)),
        })
    proj_by_name = {p["name"]: p for p in projects}

    documents, seen_titles = [], set()

    def add_doc(title, author, project, topic, kind, summary):
        if title in seen_titles:
            return
        seen_titles.add(title)
        documents.append({
            "title": title, "slug": slugify(title), "author": author,
            "project": project, "topic": topic, "kind": kind, "summary": summary,
        })

    decisions = []
    for title, proj, decider, topic, rationale, doc_title in DECISIONS:
        add_doc(doc_title, decider, proj, topic, "Analysis",
                f"Documented analysis behind the decision '{title}'.")
        decisions.append({
            "title": title, "slug": slugify(title), "project": proj,
            "decider": decider, "topic": topic, "rationale": rationale,
            "doc": doc_title,
            "date": f"2026-0{rng.randint(1, 9)}-{rng.randint(10, 28)}",
        })

    # Fill documents: project docs authored by crew members.
    doc_templates = [
        ("{p} Architecture Notes", "Spec"),
        ("{p} Launch Checklist", "Guide"),
        ("{p} Quarterly Review", "Report"),
        ("{p} API Contract", "Spec"),
        ("{p} Incident Postmortem", "Report"),
        ("{p} User Research Summary", "Analysis"),
    ]
    for proj in projects:
        for tmpl, kind in rng.sample(doc_templates, 3):
            author = rng.choice(proj["members"])
            topic = rng.choice(proj["topics"])
            title = tmpl.format(p=proj["name"])
            add_doc(title, author, proj["name"], topic, kind,
                    f"{kind} for {proj['name']}, covering {topic.lower()}.")

    tickets = []
    ticket_templates = [
        "Fix {t} edge case in {p}", "Investigate {t} regression in {p}",
        "Improve {t} performance in {p}", "Add {t} audit logging to {p}",
        "Resolve {t} timeout reports in {p}", "Backfill {t} data for {p}",
    ]
    ti = 0
    for proj in projects:
        for _ in range(6):
            tmpl = rng.choice(ticket_templates)
            topic = rng.choice(proj["topics"])
            assignee = rng.choice(proj["members"])
            resolver = rng.choice(proj["members"])
            ti += 1
            tickets.append({
                "title": tmpl.format(t=topic.lower(), p=proj["name"]),
                "slug": f"ticket-{ti}", "project": proj["name"],
                "assignee": assignee, "resolver": resolver,
                "status": rng.choice(["resolved", "resolved", "open", "in_progress"]),
                "topic": topic,
            })

    chats = []
    chat_templates = [
        "{p} standup thread", "{p} launch war-room", "{p} design review thread",
        "{p} incident channel thread",
    ]
    ci = 0
    for proj in projects:
        for tmpl in rng.sample(chat_templates, 2):
            ci += 1
            chats.append({
                "title": tmpl.format(p=proj["name"]), "slug": f"chat-{ci}",
                "project": proj["name"],
                "participants": rng.sample(proj["members"], 3),
                "decision": None,
                "summary": f"Team discussion about {proj['name']}.",
            })
    # A few chats explicitly discuss specific decisions (decision traceability).
    for dec in decisions[:4]:
        ci += 1
        chats.append({
            "title": f"Decision thread: {dec['title']}", "slug": f"chat-{ci}",
            "project": dec["project"],
            "participants": [dec["decider"]] + rng.sample(
                proj_by_name[dec["project"]]["members"], 2),
            "decision": dec["title"],
            "summary": f"Discussion that led to '{dec['title']}'.",
        })

    # Curated expertise floors; ingest adds computed evidence on top.
    expertise = [
        ("Priya Nair", "Payments", 5), ("Priya Nair", "Billing", 5),
        ("Daniel Kim", "Search Ranking", 5), ("Daniel Kim", "Machine Learning", 4),
        ("Sofia Marino", "Mobile UX", 5), ("Sofia Marino", "Onboarding", 3),
        ("Marcus Webb", "Onboarding", 5),
        ("Aisha Bello", "Data Pipelines", 5), ("Aisha Bello", "Analytics", 4),
        ("Tomás Rivera", "API Design", 5), ("Tomás Rivera", "Infrastructure", 4),
        ("June Park", "Accessibility", 5),
        ("David Osei", "Security", 5), ("David Osei", "Infrastructure", 3),
        ("Grace Liu", "Billing", 3), ("Ingrid Johansson", "Analytics", 4),
        ("Victor Chen", "Machine Learning", 4), ("Farah Khan", "Accessibility", 4),
        ("Elena Petrova", "Onboarding", 4), ("Nina Volkov", "Security", 4),
    ]

    return {
        "company": {"name": "Meridian Labs", "synthetic": True},
        "teams": teams, "people": people, "topics": topics,
        "projects": projects, "documents": documents, "decisions": decisions,
        "tickets": tickets, "chats": chats, "expertise": expertise,
        "project_deps": PROJECT_DEPS,
        "_by_name": by_name, "_proj_by_name": proj_by_name,
        "_topic_by_name": topic_by_name,
    }


def public_dataset(ds: dict) -> dict:
    """Dataset without the private lookup indexes (for inspection/tests)."""
    return {k: v for k, v in ds.items() if not k.startswith("_")}
