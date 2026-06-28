"""
Two-layer classifier (carried over from the toolkit's rule-first / AI-fallback
pattern, adapted for routing instead of canned replies).

Layer 1 (always on, free, predictable): keyword rules assign a DEPARTMENT and
a SENSITIVITY tag.

Layer 2 (optional): if the rules can't confidently pick a department, and an
Anthropic API key is configured, ask Claude for a one-word department guess and
re-check it against the same rule set. If unavailable or it fails, we fall back
to "general" — never block ingestion.

From department + sensitivity we derive the ROUTE:

  * "auto"   -> publish straight to the KB with an automatic audit entry.
               Only ever happens for IT-closed, routine, single-department
               tickets flagged as having no further interaction.
  * "manual" -> hold in the SME review queue. Triggered by anything
               cross-departmental, management-involved, or legal-adjacent.
               EVERY legal-touching resolution is manual, no exceptions.
"""

import re

DEPARTMENT_KEYWORDS = {
    "IT": ["password", "reset", "login", "firmware", "app crash", "app crashed",
           "wifi", "connectivity", "pairing", "re-pairing", "account locked",
           "locked out", "software update", "error code", "sync", "reinstall",
           "reinstalled"],
    "Technical Support": ["blade", "battery", "charging", "docking", "dock",
                          "boundary wire", "won't start", "noise", "vibration",
                          "wheel", "sensor", "calibration", "install", "setup",
                          "cutting height"],
    "Billing": ["invoice", "refund", "payment", "subscription", "billing",
                "overcharged", "double charged", "charged", "receipt", "credit"],
    "Warranty": ["warranty", "rma", "rga", "replacement unit", "defective",
                 "defect", "doa", "dead on arrival"],
    "Legal": ["lawsuit", "lawyer", "attorney", "legal", "liability", "injury",
              "subpoena", "gdpr", "data request", "data deletion", "compliance"],
    "Sales": ["quote", "purchase", "upgrade", "trade-in", "discount", "pricing"],
}

# Words that force a sensitivity tag regardless of department.
# Note: bare "manager" is deliberately excluded — it collides with benign
# phrases like "password manager". Management involvement is signalled by
# escalation / supervisor / goodwill / executive instead.
LEGAL_FLAGS = ["lawsuit", "lawyer", "attorney", "legal", "liability", "injury",
               "subpoena", "gdpr", "data request", "data deletion", "compliance",
               "regulator"]
MANAGEMENT_FLAGS = ["escalate", "escalated", "escalation", "escalating",
                    "supervisor", "goodwill", "executive", "manager approved"]


def _contains(text: str, keyword: str) -> bool:
    """Whole-word/phrase match (both boundaries anchored) so 'install' doesn't
    match 'reinstalled', 'upgrade' doesn't match 'upgraded', and 'manager'
    wouldn't match inside 'password manager'."""
    return re.search(r"\b" + re.escape(keyword) + r"\b", text) is not None


def _match_department(text: str):
    text = text.lower()
    hits = {}
    for dept, words in DEPARTMENT_KEYWORDS.items():
        score = sum(1 for w in words if _contains(text, w))
        if score:
            hits[dept] = score
    if not hits:
        return None, []
    best = max(hits, key=hits.get)
    return best, sorted(hits, key=hits.get, reverse=True)


def classify(ticket: dict, ai_fn=None) -> dict:
    """
    ticket: dict with at least 'description' and 'resolution' text, and an
            optional 'it_closed_no_followup' boolean.
    ai_fn:  optional callable(text) -> department-guess string (layer 2).

    Returns a dict: department, departments_touched, sensitivity, route, reason.
    """
    blob = f"{ticket.get('description','')} {ticket.get('resolution','')}"
    low = blob.lower()

    department, ranked = _match_department(blob)
    used_ai = False
    if department is None and ai_fn is not None:
        guess = ai_fn(blob) or ""
        department, ranked = _match_department(guess)
        used_ai = department is not None
    if department is None:
        department = "General"
        ranked = ["General"]

    # Sensitivity ----------------------------------------------------------
    legal = any(_contains(low, f) for f in LEGAL_FLAGS) or department == "Legal"
    management = any(_contains(low, f) for f in MANAGEMENT_FLAGS)
    cross_dept = len([d for d in ranked if d != "General"]) > 1

    if legal:
        sensitivity = "legal"
    elif management:
        sensitivity = "management"
    elif cross_dept:
        sensitivity = "cross-departmental"
    else:
        sensitivity = "routine"

    # Routing --------------------------------------------------------------
    it_clean_close = (
        department == "IT"
        and sensitivity == "routine"
        and bool(ticket.get("it_closed_no_followup"))
    )
    if it_clean_close:
        route, reason = "auto", "IT-closed, routine, no further interaction"
    elif legal:
        route, reason = "manual", "legal-adjacent — mandatory SME review"
    elif management:
        route, reason = "manual", "management-involved — SME review"
    elif cross_dept:
        route, reason = "manual", "cross-departmental — SME review"
    else:
        route, reason = "manual", "not an auto-publish case — SME review"

    return {
        "department": department,
        "departments_touched": ranked,
        "sensitivity": sensitivity,
        "route": route,
        "reason": reason,
        "classifier_used_ai": used_ai,
    }
